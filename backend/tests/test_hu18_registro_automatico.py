from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import hash_contrasena
from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.enums import (
    AccionAuditoria,
    EstadoConvenio,
    EstadoSolicitud,
    OrigenConvenio,
    TipoAliado,
    TipoIdentificacion,
    TipoSolicitante,
)
from backend.models.revision_convenio import RevisionConvenio
from backend.models.rol import Rol
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.schemas.convenio import ConvenioCrearManual
from backend.services import actividades_utilizacion, bitacora
from backend.services.bitacora import (
    ENTIDADES_AUDITADAS,
    asignar_actor,
    describir_accion,
)
from backend.services.convenios import ServicioConvenios
from backend.services.renovaciones import ServicioRenovaciones


def _nuevo_aliado() -> Aliado:
    return Aliado(
        nombre="Universidad aliada",
        tipo=TipoAliado.UNIVERSIDAD.value,
        tipo_identificacion=TipoIdentificacion.NIT.value,
        identificacion=str(900000000 + uuid4().int % 99999999),
        correo="contacto@aliada.example",
        activo=True,
    )


@pytest.fixture
def crear_aliado(db: Session) -> Callable[[], Aliado]:
    def _crear() -> Aliado:
        aliado = _nuevo_aliado()
        db.add(aliado)
        db.commit()
        return aliado

    return _crear


def _bitacora(db: Session, entidad: str, registro_id: int) -> list[Auditoria]:
    return list(
        db.scalars(
            select(Auditoria)
            .where(Auditoria.entidad == entidad, Auditoria.registro_id == registro_id)
            .order_by(Auditoria.id)
        )
    )


def _pendiente(db: Session, convenio_id: int) -> RevisionConvenio:
    return db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )


def test_entidades_auditadas_son_las_acordadas() -> None:
    assert set(ENTIDADES_AUDITADAS.values()) == {
        "aliado",
        "contacto_aliado",
        "usuario",
        "rol",
        "convenio",
        "solicitud",
        "revision_convenio",
        "observacion_revision",
        "documento",
        "proceso_firmas_convenio",
        "firma_convenio",
        "decision_no_renovacion",
        "evaluacion_convenio",
        "actividad_convenio",
        "borrador_convenio",
    }


def test_ningun_modulo_escribe_la_bitacora_a_mano() -> None:
    paquete = Path(bitacora.__file__).parents[1]
    escrituras = [
        str(archivo.relative_to(paquete))
        for archivo in paquete.rglob("*.py")
        if archivo.parent.name != "models"
        and "Auditoria(" in archivo.read_text("utf-8")
    ]

    assert escrituras == []


@pytest.mark.parametrize("rol", [CodigoRol.GESTOR_ORI, CodigoRol.ADMINISTRADOR_ORI])
def test_creacion_manual_audita_una_sola_insercion_incluso_fuera_de_la_api(
    db, crear_usuario, rol
) -> None:
    usuario = crear_usuario(rol)

    convenio = ServicioConvenios(db).crear_manual(
        ConvenioCrearManual(objeto="Cooperación académica"), usuario
    )

    (registro,) = _bitacora(db, "convenio", convenio.id)
    assert registro.accion == AccionAuditoria.INSERT
    assert (registro.usuario_id, registro.rol) == (usuario.id, rol.value)
    assert registro.contexto == "Creó el convenio manualmente"
    assert registro.fecha_hora is not None
    assert registro.campo is None
    assert convenio.origen == OrigenConvenio.MANUAL_ORI.value
    assert convenio.solicitud_id is None
    assert convenio.version_actual == 1


def test_guardar_avance_del_convenio_manual_no_versiona_ni_copia_el_contenido(
    db, client, gestor
) -> None:
    creada = client.post("/api/convenios/manual", json={})
    assert creada.status_code == 201
    convenio_id = creada.json()["id"]
    ruta = f"/api/convenios/{convenio_id}/elaboracion"
    contenido = {
        "type": "doc",
        "content": [{
            "type": "paragraph",
            "content": [{"type": "text", "text": "Contenido reservado del acuerdo"}],
        }],
    }

    guardado = client.patch(ruta, json={"expected_revision": 0, "contenido": contenido})
    assert guardado.status_code == 200
    assert guardado.json()["version_actual"] == 1
    assert guardado.json()["revision_borrador"] == 1
    registros = _bitacora(db, "convenio", convenio_id)
    assert [(r.accion, r.campo) for r in registros] == [(AccionAuditoria.INSERT, None)]
    assert db.scalar(
        select(Auditoria.id).where(
            or_(
                Auditoria.valor_anterior.contains("Contenido reservado"),
                Auditoria.valor_nuevo.contains("Contenido reservado"),
            )
        )
    ) is None

    repetido = client.patch(ruta, json={"expected_revision": 1, "contenido": contenido})
    assert repetido.status_code == 200
    assert repetido.json()["revision_borrador"] == 1
    assert [r.id for r in _bitacora(db, "convenio", convenio_id)] == [
        r.id for r in registros
    ]


@pytest.mark.parametrize("origen", list(OrigenConvenio))
def test_renovar_ambos_origenes_atribuye_toda_la_creacion_al_nuevo_responsable(
    db, crear_usuario, crear_convenio, origen
) -> None:
    autor = crear_usuario(CodigoRol.GESTOR_ORI)
    responsable = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    if origen == OrigenConvenio.MANUAL_ORI:
        padre = ServicioConvenios(db).crear_manual(ConvenioCrearManual(), autor)
    else:
        padre = crear_convenio(autor)
    padre.estado = EstadoConvenio.FINALIZADO.value
    padre.fecha_vencimiento = date(2025, 12, 31)
    db.commit()
    registros_padre = [r.id for r in _bitacora(db, "convenio", padre.id)]

    hijo = ServicioRenovaciones(db).iniciar_renovacion(padre.id, responsable)

    (registro,) = _bitacora(db, "convenio", hijo.id)
    registros = [registro]
    assert hijo.origen == origen.value
    assert hijo.convenio_origen_id == padre.id
    assert hijo.version_actual == 1
    if origen == OrigenConvenio.SOLICITUD:
        assert hijo.solicitud_id != padre.solicitud_id
        (solicitud,) = _bitacora(db, "solicitud", hijo.solicitud_id)
        registros.append(solicitud)
    else:
        assert hijo.solicitud_id is None
    assert {r.accion for r in registros} == {AccionAuditoria.INSERT}
    assert {r.usuario_id for r in registros} == {responsable.id}
    assert {r.rol for r in registros} == {CodigoRol.ADMINISTRADOR_ORI.value}
    assert {r.contexto for r in registros} == {"Inició la renovación del convenio"}
    assert all(r.fecha_hora is not None for r in registros)
    assert [r.id for r in _bitacora(db, "convenio", padre.id)] == registros_padre


def test_crear_registra_la_insercion_con_el_usuario_responsable(
    db, crear_usuario, crear_aliado
) -> None:
    usuario = crear_usuario()
    asignar_actor(db, usuario)

    aliado = crear_aliado()

    registros = _bitacora(db, "aliado", aliado.id)
    assert len(registros) == 1
    assert registros[0].accion == AccionAuditoria.INSERT
    assert registros[0].usuario_id == usuario.id
    assert registros[0].campo is None
    assert registros[0].fecha_hora is not None


def test_editar_por_api_registra_cada_campo_con_el_usuario_de_la_sesion(
    db, client, gestor, crear_aliado
) -> None:
    aliado = crear_aliado()

    respuesta = client.patch(
        f"/api/aliados/{aliado.id}",
        json={"nombre": "Universidad renombrada", "ciudad": "Cali"},
    )

    assert respuesta.status_code == 200
    registros = {r.campo: r for r in _bitacora(db, "aliado", aliado.id)}
    assert set(registros) == {"nombre", "ciudad"}
    assert all(r.usuario_id == gestor.id for r in registros.values())
    assert all(r.accion == AccionAuditoria.UPDATE for r in registros.values())
    assert registros["nombre"].valor_anterior == "Universidad aliada"
    assert registros["nombre"].valor_nuevo == "Universidad renombrada"
    assert registros["ciudad"].valor_anterior is None
    assert registros["ciudad"].valor_nuevo == "Cali"


def test_el_registro_conserva_el_rol_que_tenia_el_usuario_al_actuar(
    db, client, gestor, crear_aliado
) -> None:
    aliado = crear_aliado()
    client.patch(f"/api/aliados/{aliado.id}", json={"nombre": "Universidad renombrada"})

    gestor.rol = db.scalar(select(Rol).where(Rol.codigo == CodigoRol.REVISOR_ORI.value))
    db.commit()

    (registro,) = _bitacora(db, "aliado", aliado.id)
    db.refresh(registro)
    assert registro.rol == CodigoRol.GESTOR_ORI.value


def test_reenviar_el_mismo_valor_no_registra_cambios(
    db, client, gestor, crear_aliado
) -> None:
    aliado = crear_aliado()

    respuesta = client.patch(
        f"/api/aliados/{aliado.id}", json={"nombre": "Universidad aliada"}
    )

    assert respuesta.status_code == 200
    assert _bitacora(db, "aliado", aliado.id) == []


def test_los_registros_anteriores_se_conservan_en_orden(
    db, client, gestor, crear_aliado
) -> None:
    aliado = crear_aliado()

    client.patch(f"/api/aliados/{aliado.id}", json={"nombre": "Primer cambio"})
    client.patch(f"/api/aliados/{aliado.id}", json={"nombre": "Segundo cambio"})

    registros = _bitacora(db, "aliado", aliado.id)
    assert [(r.valor_anterior, r.valor_nuevo) for r in registros] == [
        ("Universidad aliada", "Primer cambio"),
        ("Primer cambio", "Segundo cambio"),
    ]
    assert registros[0].fecha_hora <= registros[1].fecha_hora


def test_eliminar_registra_la_eliminacion(db, crear_usuario, crear_aliado) -> None:
    aliado = crear_aliado()
    aliado_id = aliado.id
    asignar_actor(db, crear_usuario())

    db.delete(aliado)
    db.commit()

    assert [r.accion for r in _bitacora(db, "aliado", aliado_id)] == [
        AccionAuditoria.DELETE
    ]


def test_sin_usuario_autenticado_no_se_registra(db, crear_aliado) -> None:
    aliado = crear_aliado()
    aliado.nombre = "Cambio sin sesión"
    db.commit()

    assert _bitacora(db, "aliado", aliado.id) == []


def test_entidad_no_auditada_no_se_registra(db, crear_usuario) -> None:
    asignar_actor(db, crear_usuario())
    tipo = TipoConvenio(codigo=f"PRUEBA-{uuid4().hex[:8]}", nombre="Tipo de prueba")
    db.add(tipo)
    db.commit()

    assert _bitacora(db, "tipo_convenio", tipo.id) == []


def test_cambio_de_rol_queda_registrado_con_el_administrador(
    db, client, crear_usuario, entrar_como
) -> None:
    administrador = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    gestor = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    rol_anterior_id = gestor.rol_id
    entrar_como(administrador)

    respuesta = client.patch(
        f"/api/usuarios/{gestor.id}/rol", json={"rol": CodigoRol.REVISOR_ORI.value}
    )

    assert respuesta.status_code == 200
    rol_revisor = db.scalar(select(Rol).where(Rol.codigo == CodigoRol.REVISOR_ORI.value))
    (registro,) = [r for r in _bitacora(db, "usuario", gestor.id) if r.campo == "rol_id"]
    assert registro.usuario_id == administrador.id
    assert registro.valor_anterior == str(rol_anterior_id)
    assert registro.valor_nuevo == str(rol_revisor.id)


def test_la_contrasena_se_registra_sin_guardar_su_valor(db, crear_usuario) -> None:
    usuario = crear_usuario()
    hash_anterior = usuario.hash_contrasena
    asignar_actor(db, usuario)

    usuario.hash_contrasena = hash_contrasena("OtraClaveSegura456!")
    db.commit()

    (registro,) = _bitacora(db, "usuario", usuario.id)
    assert registro.campo == "hash_contrasena"
    assert registro.valor_anterior is None
    assert registro.valor_nuevo is None
    assert db.scalar(
        select(Auditoria.id).where(
            or_(
                Auditoria.valor_anterior.in_([hash_anterior, usuario.hash_contrasena]),
                Auditoria.valor_nuevo.in_([hash_anterior, usuario.hash_contrasena]),
            )
        )
    ) is None


def test_observacion_juridica_queda_registrada_con_el_revisor(
    db, client, gestor, revisor, convenio_listo, entrar_como
) -> None:
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    revision_id = client.get(f"/api/convenios/{convenio_listo.id}/revisiones").json()[
        "revisiones"
    ][-1]["id"]
    entrar_como(revisor)

    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{revision_id}/observaciones",
        json={"descripcion": "Precisar el objeto del convenio"},
    )

    assert respuesta.status_code in (200, 201)
    (registro,) = _bitacora(db, "observacion_revision", respuesta.json()["id"])
    assert registro.accion == AccionAuditoria.INSERT
    assert registro.usuario_id == revisor.id
    assert registro.contexto == (
        "Registró una observación en la revisión jurídica 1 de la ronda 1"
    )


def test_la_accion_descrita_acompana_cada_cambio_de_su_transaccion(
    db, crear_usuario, crear_aliado
) -> None:
    usuario = crear_usuario()
    aliado = crear_aliado()

    describir_accion(db, usuario, "Actualizó los datos del aliado")
    aliado.nombre = "Universidad renombrada"
    aliado.ciudad = "Cali"
    db.commit()

    registros = _bitacora(db, "aliado", aliado.id)
    assert {r.campo for r in registros} == {"nombre", "ciudad"}
    assert {r.contexto for r in registros} == {"Actualizó los datos del aliado"}
    assert {r.usuario_id for r in registros} == {usuario.id}


def test_la_accion_descrita_vale_solo_para_su_transaccion(
    db, crear_usuario, crear_aliado
) -> None:
    usuario = crear_usuario()
    aliado = crear_aliado()
    asignar_actor(db, usuario)

    describir_accion(db, usuario, "Renombró el aliado")
    aliado.nombre = "Universidad renombrada"
    db.commit()
    aliado.ciudad = "Cali"
    db.commit()

    registros = {r.campo: r for r in _bitacora(db, "aliado", aliado.id)}
    assert registros["nombre"].contexto == "Renombró el aliado"
    assert registros["ciudad"].contexto is None
    assert registros["ciudad"].usuario_id == usuario.id


def test_fuera_de_una_peticion_la_accion_no_atribuye_cambios_posteriores(
    db, crear_usuario, crear_aliado
) -> None:
    usuario = crear_usuario()
    aliado = crear_aliado()

    describir_accion(db, usuario, "Renombró el aliado")
    aliado.nombre = "Universidad renombrada"
    db.commit()
    aliado.ciudad = "Cali"
    db.commit()

    assert [r.campo for r in _bitacora(db, "aliado", aliado.id)] == ["nombre"]


def test_una_accion_revertida_no_deja_registros(
    db, crear_usuario, crear_aliado
) -> None:
    usuario = crear_usuario()
    aliado = crear_aliado()
    asignar_actor(db, usuario)

    describir_accion(db, usuario, "Acción revertida")
    aliado.nombre = "Cambio revertido"
    db.flush()
    db.rollback()
    aliado.ciudad = "Cali"
    db.commit()

    (registro,) = _bitacora(db, "aliado", aliado.id)
    assert (registro.campo, registro.contexto) == ("ciudad", None)


def test_la_accion_puede_fijar_la_fecha_y_hora_de_sus_registros(
    db, crear_usuario, crear_aliado
) -> None:
    usuario = crear_usuario()
    aliado = crear_aliado()
    instante = datetime(2026, 10, 13, 15, 30, tzinfo=UTC)

    describir_accion(db, usuario, "Renombró el aliado", instante=instante)
    aliado.nombre = "Universidad renombrada"
    db.commit()

    (registro,) = _bitacora(db, "aliado", aliado.id)
    assert registro.fecha_hora == instante


def test_lo_completado_al_crear_un_registro_no_se_registra_como_modificacion(
    db, crear_usuario
) -> None:
    asignar_actor(db, crear_usuario())
    aliado = _nuevo_aliado()
    db.add(aliado)
    db.flush()

    aliado.ciudad = "Cali"
    db.commit()

    assert [r.accion for r in _bitacora(db, "aliado", aliado.id)] == [
        AccionAuditoria.INSERT
    ]


def test_los_valores_json_se_registran_sin_su_contenido(
    db, crear_usuario, gestor, convenio_listo
) -> None:
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    revision = _pendiente(db, convenio_listo.id)
    asignar_actor(db, crear_usuario())

    revision.snapshot_datos = {"objeto": "Objeto distinto"}
    db.commit()

    (registro,) = [
        r
        for r in _bitacora(db, "revision_convenio", revision.id)
        if r.campo == "snapshot_datos"
    ]
    assert (registro.valor_anterior, registro.valor_nuevo) == (None, None)


def test_las_actuaciones_del_solicitante_quedan_registradas(
    db, client, solicitante, entrar_como
) -> None:
    entrar_como(solicitante)

    respuesta = client.post("/api/solicitudes", json={"objeto": "Cooperación académica"})

    assert respuesta.status_code == 201
    (registro,) = _bitacora(db, "solicitud", respuesta.json()["id"])
    assert registro.accion == AccionAuditoria.INSERT
    assert registro.usuario_id == solicitante.id
    assert registro.rol == CodigoRol.SOLICITANTE_INTERNO.value


def test_devolver_una_solicitud_queda_registrado_con_su_accion(
    db, client, gestor, solicitante
) -> None:
    solicitud = SolicitudConvenio(
        consecutivo=f"SOL-{uuid4().hex[:12]}",
        tipo_solicitante=TipoSolicitante.INTERNO.value,
        solicitante_id=solicitante.id,
        objeto="Cooperación académica",
        nombre_aliado_propuesto="Universidad Contraparte",
        estado=EstadoSolicitud.RADICADA.value,
    )
    db.add(solicitud)
    db.commit()

    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/devolver",
        json={"observaciones": "Adjuntar el RUT actualizado"},
    )

    assert respuesta.status_code == 200
    registros = {r.campo: r for r in _bitacora(db, "solicitud", solicitud.id)}
    assert registros["estado"].valor_nuevo == EstadoSolicitud.DEVUELTA.value
    assert registros["observaciones_devolucion"].valor_nuevo == (
        "Adjuntar el RUT actualizado"
    )
    assert {r.contexto for r in registros.values()} == {
        "Devolvió la solicitud al Solicitante para corrección"
    }
    assert {r.usuario_id for r in registros.values()} == {gestor.id}


def test_editar_un_convenio_queda_registrado_con_su_accion(
    db, client, gestor, convenio_listo
) -> None:
    respuesta = client.patch(
        f"/api/convenios/{convenio_listo.id}", json={"objeto": "Objeto ajustado"}
    )

    assert respuesta.status_code == 200
    (registro,) = [
        r for r in _bitacora(db, "convenio", convenio_listo.id) if r.campo == "objeto"
    ]
    assert (registro.valor_anterior, registro.valor_nuevo) == (
        "Objeto inicial del convenio",
        "Objeto ajustado",
    )
    assert registro.contexto == "Editó los datos del convenio"
    assert registro.usuario_id == gestor.id


def test_registrar_una_actividad_de_utilizacion_queda_registrado_con_su_accion(
    db, client, gestor, convenio_listo, monkeypatch
) -> None:
    monkeypatch.setattr(
        actividades_utilizacion, "fecha_actual_dominio", lambda: date(2026, 10, 13)
    )
    convenio_listo.estado = EstadoConvenio.VIGENTE.value
    convenio_listo.fecha_inicio = date(2026, 1, 1)
    convenio_listo.fecha_vencimiento = date(2027, 1, 1)
    db.commit()

    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/actividades-utilizacion",
        json={
            "fecha_ejecucion": "2026-09-15",
            "titulo": "Movilidad académica de dos estudiantes",
            "descripcion": "Intercambio académico durante el semestre 2026-2",
            "responsable_nombre": "Facultad de Ingeniería",
        },
    )

    assert respuesta.status_code == 201
    (registro,) = _bitacora(db, "actividad_convenio", respuesta.json()["id"])
    assert registro.accion == AccionAuditoria.INSERT
    assert registro.usuario_id == gestor.id
    assert registro.contexto == "Registró una actividad de utilización del convenio"


def test_aprobar_la_revision_juridica_queda_registrado_con_la_revision(
    db, client, gestor, revisor, convenio_listo, entrar_como
) -> None:
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    rj1 = _pendiente(db, convenio_listo.id)
    entrar_como(revisor)

    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{rj1.id}/aprobar",
        json={"expected_version": convenio_listo.version_actual},
    )

    assert respuesta.status_code == 200
    descripcion = "Aprobó la revisión jurídica 1 de la ronda 1"
    insercion, *modificaciones = _bitacora(db, "revision_convenio", rj1.id)
    assert insercion.contexto == (
        "Finalizó la elaboración y envió el convenio a revisión jurídica"
    )
    assert insercion.usuario_id == gestor.id
    resultado = next(r for r in modificaciones if r.campo == "resultado")
    assert (resultado.valor_nuevo, resultado.contexto) == ("APROBADA", descripcion)
    assert (resultado.usuario_id, resultado.rol) == (
        revisor.id,
        CodigoRol.REVISOR_ORI.value,
    )
    (rj2,) = _bitacora(db, "revision_convenio", _pendiente(db, convenio_listo.id).id)
    assert (rj2.accion, rj2.contexto) == (AccionAuditoria.INSERT, descripcion)


def test_devolver_la_revision_juridica_queda_registrado_con_la_revision(
    db, client, gestor, revisor, convenio_listo, entrar_como
) -> None:
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    rj1 = _pendiente(db, convenio_listo.id)
    entrar_como(revisor)

    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{rj1.id}/devolver",
        json={
            "expected_version": convenio_listo.version_actual,
            "observaciones": ["Precisar el objeto del convenio"],
        },
    )

    assert respuesta.status_code == 200
    resultado = next(
        r for r in _bitacora(db, "revision_convenio", rj1.id) if r.campo == "resultado"
    )
    assert (resultado.valor_nuevo, resultado.usuario_id) == ("DEVUELTA", revisor.id)
    assert resultado.contexto == (
        "Devolvió la revisión jurídica 1 de la ronda 1 con observaciones"
    )
