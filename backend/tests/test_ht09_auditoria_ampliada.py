"""HT-09: completar la información y autoría de la bitácora de auditoría.

Cubre lo que agrega HT-09 sobre la bitácora de HU-18: evento, etapa, versión
y responsable estructurados, y la distinción entre ejecución humana y
automática sin usuarios ficticios.
"""

from collections.abc import Callable
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.borrador_convenio import BorradorConvenio
from backend.models.enums import TipoAliado, TipoIdentificacion
from backend.models.firma_convenio import FirmaConvenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.invitacion_revision_contraparte import InvitacionRevisionContraparte
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.schemas.convenio import (
    ConvenioElaboracionActualizar,
    RevisionContenidoGuardar,
)
from backend.schemas.solicitud import SolicitudCamposEditables
from backend.services import bitacora
from backend.services.bitacora import (
    asignar_actor,
    describir_accion,
    describir_accion_automatica,
    describir_cambios_automaticos,
)
from backend.services.convenios import ServicioConvenios, contexto_auditoria
from backend.services.solicitudes import CAMPOS_CON_FORMATO, ServicioSolicitudes

URL_AUDITORIA = "/api/auditoria"


@pytest.fixture
def administrador(crear_usuario, entrar_como) -> Usuario:
    usuario = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    entrar_como(usuario)
    return usuario


@pytest.fixture
def crear_aliado(db: Session) -> Callable[[], Aliado]:
    def _crear() -> Aliado:
        aliado = Aliado(
            nombre="Universidad aliada HT-09",
            tipo=TipoAliado.UNIVERSIDAD.value,
            tipo_identificacion=TipoIdentificacion.NIT.value,
            identificacion=uuid4().hex,
            activo=True,
        )
        db.add(aliado)
        db.commit()
        db.refresh(aliado)
        return aliado

    return _crear


def _ultima_fila(db: Session, entidad: str, registro_id: int) -> Auditoria:
    return db.scalars(
        select(Auditoria)
        .where(Auditoria.entidad == entidad, Auditoria.registro_id == registro_id)
        .order_by(Auditoria.id.desc())
    ).first()


# ---- CA-01: etapa y versión estructuradas ----------------------------------


def test_evento_etapa_y_version_quedan_estructurados(
    db: Session, gestor: Usuario, crear_aliado
) -> None:
    aliado = crear_aliado()
    describir_accion(
        db,
        gestor,
        "Actualizó el aliado",
        evento="ALIADO_EDITADO",
        etapa="ELABORACION",
        version=3,
    )
    aliado.nombre = "Nuevo nombre"
    db.commit()

    fila = _ultima_fila(db, "aliado", aliado.id)
    assert fila.evento == "ALIADO_EDITADO"
    assert fila.etapa == "ELABORACION"
    assert fila.version == 3
    # No depende solamente del texto libre de contexto.
    assert fila.contexto == "Actualizó el aliado"


# ---- CA-02/CA-03: originador humano vs. ejecución automática --------------


def test_accion_humana_conserva_usuario_y_rol(
    db: Session, gestor: Usuario, crear_aliado
) -> None:
    aliado = crear_aliado()
    describir_accion(db, gestor, "Actualizó el aliado", evento="ALIADO_EDITADO")
    aliado.nombre = "Otro nombre"
    db.commit()

    fila = _ultima_fila(db, "aliado", aliado.id)
    assert fila.usuario_id == gestor.id
    assert fila.rol == gestor.rol.codigo
    assert fila.ejecucion == "HUMANA"


def test_proceso_automatico_no_usa_usuario_ficticio(
    db: Session, gestor: Usuario, crear_aliado
) -> None:
    total_usuarios_antes = db.scalar(select(func.count()).select_from(Usuario))
    aliado = crear_aliado()
    asignar_actor(db, gestor)
    describir_accion_automatica(
        db, "Concilió el estado del aliado", evento="ALIADO_CONCILIADO"
    )
    aliado.activo = False
    db.commit()

    fila = _ultima_fila(db, "aliado", aliado.id)
    assert fila.usuario_id is None
    assert fila.rol is None
    assert fila.ejecucion == "AUTOMATICA"
    assert fila.evento == "ALIADO_CONCILIADO"
    # El proceso automático no creó ningún usuario para representarse.
    total_usuarios_despues = db.scalar(select(func.count()).select_from(Usuario))
    assert total_usuarios_despues == total_usuarios_antes


def test_el_cambio_del_usuario_de_la_sesion_sin_accion_descrita_es_humano(
    db: Session, gestor: Usuario, crear_aliado
) -> None:
    """El actor de la sesión solo se asigna con el usuario autenticado de la
    petición: su cambio es humano aunque no declare un evento de negocio."""
    aliado = crear_aliado()
    asignar_actor(db, gestor)
    aliado.nombre = "Cambio sin describir_accion"
    db.commit()

    fila = _ultima_fila(db, "aliado", aliado.id)
    assert fila.usuario_id == gestor.id
    assert fila.ejecucion == "HUMANA"
    assert fila.evento is None


# ---- CA-04: responsable de negocio distinto del originador -----------------


def test_responsable_de_negocio_es_distinto_del_originador(
    db: Session, gestor: Usuario, crear_usuario, crear_aliado
) -> None:
    otro = crear_usuario()
    aliado = crear_aliado()
    describir_accion(
        db,
        gestor,
        "Actualizó el aliado en nombre de otro responsable",
        evento="ALIADO_EDITADO",
        responsable_id=otro.id,
    )
    aliado.nombre = "Nombre con responsable distinto"
    db.commit()

    fila = _ultima_fila(db, "aliado", aliado.id)
    assert fila.usuario_id == gestor.id
    assert fila.responsable_id == otro.id
    assert fila.usuario_id != fila.responsable_id


# ---- CA-05: contexto funcional de acciones ya existentes -------------------


def test_editar_convenio_registra_evento_etapa_version_y_responsable(
    db: Session, gestor: Usuario, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    etapa_esperada = convenio.etapa_actual.codigo
    version_esperada = convenio.version_actual

    ServicioConvenios(db).actualizar(
        convenio.id,
        ConvenioElaboracionActualizar(objeto="Objeto editado por HT-09"),
        gestor,
    )

    fila = _ultima_fila(db, "convenio", convenio.id)
    assert fila.evento == "CONVENIO_EDITADO"
    assert fila.etapa == etapa_esperada
    assert fila.version == version_esperada
    assert fila.responsable_id == convenio.creado_por_id
    assert fila.ejecucion == "HUMANA"


# ---- CA-06: la API expone los campos nuevos --------------------------------


def test_api_auditoria_expone_los_campos_de_ht09(
    client, gestor, administrador, crear_aliado, db
) -> None:
    aliado = crear_aliado()
    describir_accion(
        db,
        gestor,
        "Actualizó el aliado",
        evento="ALIADO_EDITADO",
        etapa="ELABORACION",
        version=1,
    )
    aliado.nombre = "Visible por la API"
    db.commit()

    respuesta = client.get(
        URL_AUDITORIA, params={"entidad": "aliado", "registro_id": aliado.id}
    )
    assert respuesta.status_code == 200
    (item,) = respuesta.json()["items"]
    assert item["evento"] == "ALIADO_EDITADO"
    assert item["etapa"] == "ELABORACION"
    assert item["version"] == 1
    assert item["ejecucion"] == "HUMANA"
    assert item["usuario"]["id"] == gestor.id


def test_api_auditoria_muestra_null_para_proceso_automatico(
    client, administrador, crear_aliado, db
) -> None:
    aliado = crear_aliado()
    describir_accion_automatica(db, "Concilió el aliado", evento="ALIADO_CONCILIADO")
    aliado.activo = False
    db.commit()

    respuesta = client.get(
        URL_AUDITORIA, params={"entidad": "aliado", "registro_id": aliado.id}
    )
    assert respuesta.status_code == 200
    (item,) = respuesta.json()["items"]
    assert item["usuario"] is None
    assert item["ejecucion"] == "AUTOMATICA"
    assert item["evento"] == "ALIADO_CONCILIADO"


# ---- CA-07: compatibilidad con registros históricos ------------------------


def test_registro_historico_sin_campos_nuevos_se_lee_sin_error(
    client, gestor, administrador, db
) -> None:
    """Simula un registro insertado antes de HT-09: evento/etapa/version/
    ejecucion/responsable_id nulos. No se completan retroactivamente."""
    fila = Auditoria(
        usuario_id=gestor.id,
        rol=gestor.rol.codigo,
        entidad="convenio",
        registro_id=999999,
        accion="UPDATE",
        campo="objeto",
        valor_anterior="antes",
        valor_nuevo="después",
        contexto="Editó el convenio (histórico, previo a HT-09)",
    )
    db.add(fila)
    db.commit()

    respuesta = client.get(
        URL_AUDITORIA, params={"entidad": "convenio", "registro_id": 999999}
    )
    assert respuesta.status_code == 200
    (item,) = respuesta.json()["items"]
    assert item["evento"] is None
    assert item["etapa"] is None
    assert item["version"] is None
    assert item["ejecucion"] is None
    assert item["responsable"] is None


# ---- CA-08: integridad de la base ------------------------------------------


def test_bd_rechaza_ejecucion_automatica_sin_usuario_ni_marca(
    db: Session, gestor: Usuario
) -> None:
    """ck_auditoria_usuario_o_automatica: toda fila sin usuario_id debe
    declararse explícitamente AUTOMATICA; no puede quedar sin ninguno."""
    db.add(
        Auditoria(
            usuario_id=None,
            entidad="convenio",
            registro_id=1,
            accion="UPDATE",
            contexto="Fila inválida: sin usuario y sin ejecución automática",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_bd_rechaza_valor_de_ejecucion_invalido(db: Session, gestor: Usuario) -> None:
    db.add(
        Auditoria(
            usuario_id=gestor.id,
            rol=gestor.rol.codigo,
            entidad="convenio",
            registro_id=1,
            accion="UPDATE",
            ejecucion="NO_EXISTE",
            contexto="Fila inválida: ejecución fuera de catálogo",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_automatica_con_usuario_no_viola_la_restriccion(
    db: Session, gestor: Usuario
) -> None:
    """El CHECK solo exige usuario_id o AUTOMATICA; un proceso automático
    que sí conoce el usuario originador (por ejemplo, uno disparado por una
    acción suya) no está prohibido."""
    db.add(
        Auditoria(
            usuario_id=gestor.id,
            rol=gestor.rol.codigo,
            entidad="convenio",
            registro_id=1,
            accion="UPDATE",
            ejecucion="AUTOMATICA",
            contexto="Proceso automático que conserva el usuario originador",
        )
    )
    db.commit()


@pytest.fixture
def solicitud_para_radicar(client, db, solicitante, entrar_como, id_colombia):
    entrar_como(solicitante)
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    # Texto genérico solo en los campos sin reglas de formato (HT-14).
    datos = {
        campo: f"Valor de {campo}"
        for campo in SolicitudCamposEditables.model_fields
        if campo not in CAMPOS_CON_FORMATO
    }
    datos.update(
        identificacion_aliado_propuesto="900123456",
        digito_verificacion_aliado_propuesto="8",
        pais_aliado_propuesto_id=id_colombia,
        ciudad_aliado_propuesto="Cali",
        direccion_aliado_propuesto="Avenida 1 # 2-3",
        telefono_aliado_propuesto="6025550101",
        contacto_contraparte_telefono="3001234567",
        supervisor_usb_telefono="6025550202",
        supervisor_contraparte_telefono="3005550303",
        solicitante_correo=solicitante.correo,
        tipo_identificacion_aliado_propuesto="NIT",
        tipo_aliado_propuesto="EMPRESA", tipo_convenio_id=tipo.id,
        correo_aliado_propuesto="contacto@aliado.example",
        contacto_contraparte_correo="persona@aliado.example",
        supervisor_usb_correo="supervisor@usb.example",
        supervisor_contraparte_correo="supervisor@aliado.example",
    )
    creada = client.post("/api/solicitudes", json=datos)
    assert creada.status_code == 201, creada.text
    solicitud_id = creada.json()["id"]
    archivo = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "OTRO_DOCUMENTO_REPRESENTACION"},
        files={"archivo": ("soporte.pdf", BytesIO(b"%PDF-1.4 soporte"), "application/pdf")},
    )
    assert archivo.status_code == 201, archivo.text
    return solicitud_id


def test_radicacion_humana_con_efectos_automaticos_conserva_originador_en_api(
    client, db, solicitud_para_radicar, solicitante, crear_usuario, entrar_como,
) -> None:
    solicitud_id = solicitud_para_radicar
    radicada = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert radicada.status_code == 200, radicada.text
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI))
    respuesta = client.get(URL_AUDITORIA, params={
        "entidad": "solicitud", "registro_id": solicitud_id,
    })
    assert respuesta.status_code == 200
    filas = [f for f in respuesta.json()["items"] if f["evento"] == "SOLICITUD_RADICADA"]
    humanas = [f for f in filas if f["ejecucion"] == "HUMANA"]
    assert len(humanas) == 1
    assert humanas[0]["accion"] == "UPDATE"
    assert humanas[0]["campo"] is None
    efectos = {f["campo"]: f for f in filas if f["ejecucion"] == "AUTOMATICA"}
    assert set(efectos) == {"estado", "fecha_radicacion", "fecha_recibido_ori"}
    assert efectos["estado"]["valor_anterior"] == "BORRADOR"
    assert efectos["estado"]["valor_nuevo"] == "RADICADA"
    assert efectos["fecha_radicacion"]["valor_nuevo"] == efectos["fecha_recibido_ori"]["valor_nuevo"]
    for fila in filas:
        assert fila["usuario"]["id"] == solicitante.id
        assert fila["rol"] == "SOLICITANTE_INTERNO"
        assert fila["responsable"]["id"] == solicitante.id
        assert fila["contexto"] == "Radicó la solicitud"
        assert fila["fecha_hora"] == radicada.json()["fecha_radicacion"]
        # Una solicitud aún no tiene etapa ni versión formal de convenio.
        assert fila["etapa"] is None and fila["version"] is None


def test_ejecucion_automatica_con_originador_explicito(db, gestor, crear_aliado):
    aliado = crear_aliado()
    describir_accion_automatica(
        db, "Efecto programado por el Gestor", originador=gestor,
        evento="ALIADO_CONCILIADO",
    )
    aliado.activo = False
    db.commit()
    fila = _ultima_fila(db, "aliado", aliado.id)
    assert (fila.usuario_id, fila.rol, fila.ejecucion) == (
        gestor.id, gestor.rol.codigo, "AUTOMATICA",
    )


def test_solicitante_no_es_responsable_institucional_de_decision_ori(
    client, db, solicitud_para_radicar, gestor, solicitante, entrar_como,
):
    solicitud_id = solicitud_para_radicar
    entrar_como(solicitante)
    assert client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code == 200
    ServicioSolicitudes(db).aceptar(solicitud_id, gestor)
    fila = _ultima_fila(db, "solicitud", solicitud_id)
    assert fila.evento == "SOLICITUD_APROBADA"
    assert fila.usuario_id == gestor.id
    assert fila.responsable_id is None


def test_marcar_efectos_sin_cambios_no_genera_eventos(db, gestor, crear_aliado):
    aliado = crear_aliado()
    antes = db.scalar(select(func.count()).select_from(Auditoria))
    describir_accion(db, gestor, "Operación sin cambios", evento="SIN_CAMBIOS")
    describir_cambios_automaticos(db, aliado, "activo")
    aliado.activo = True
    db.commit()
    assert db.scalar(select(func.count()).select_from(Auditoria)) == antes


def test_efectos_automaticos_no_contaminan_otro_objeto_ni_otra_accion(
    db, gestor, crear_usuario, crear_aliado,
):
    primero, segundo = crear_aliado(), crear_aliado()
    otro = crear_usuario()
    with db.no_autoflush:
        describir_accion(db, gestor, "Primera operación", evento="PRIMER_EVENTO")
        describir_cambios_automaticos(db, primero, "activo")
        primero.activo = False
        # Sin flush entre contextos: la marca conserva su acción de origen.
        describir_accion(db, otro, "Segunda operación", evento="SEGUNDO_EVENTO")
        segundo.activo = False
        assert db.is_modified(primero) and db.is_modified(segundo)
    db.commit()
    fila_primera = _ultima_fila(db, "aliado", primero.id)
    fila_segunda = _ultima_fila(db, "aliado", segundo.id)
    assert (fila_primera.usuario_id, fila_primera.evento, fila_primera.ejecucion) == (
        gestor.id, "PRIMER_EVENTO", "AUTOMATICA",
    )
    assert (fila_segunda.usuario_id, fila_segunda.evento, fila_segunda.ejecucion) == (
        otro.id, "SEGUNDO_EVENTO", "HUMANA",
    )


def test_creador_sin_asignacion_no_se_inventa_como_responsable(db, gestor, crear_convenio):
    convenio = crear_convenio(gestor)
    ultimo = db.scalar(select(HistorialEtapa).where(
        HistorialEtapa.convenio_id == convenio.id,
    ).order_by(HistorialEtapa.id.desc()))
    ultimo.responsable_id = None
    db.commit()
    ServicioConvenios(db).actualizar(
        convenio.id, ConvenioElaboracionActualizar(objeto="Sin responsable asignado"), gestor,
    )
    fila = _ultima_fila(db, "convenio", convenio.id)
    assert fila.responsable_id is None
    assert convenio.creado_por_id == gestor.id


def test_responsable_de_etapa_asignado_puede_diferir_del_creador(
    db, gestor, crear_usuario, crear_convenio,
):
    convenio = crear_convenio(gestor)
    responsable = crear_usuario()
    ultimo = db.scalar(select(HistorialEtapa).where(
        HistorialEtapa.convenio_id == convenio.id,
    ).order_by(HistorialEtapa.id.desc()))
    ultimo.responsable_id = responsable.id
    db.commit()
    ServicioConvenios(db).actualizar(
        convenio.id, ConvenioElaboracionActualizar(objeto="Responsable verificable"), gestor,
    )
    assert _ultima_fila(db, "convenio", convenio.id).responsable_id == responsable.id
    assert convenio.creado_por_id == gestor.id


def test_no_se_recupera_un_responsable_de_una_etapa_anterior(db, gestor, convenio_listo):
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    # La nueva transición de Jurídica no tiene asignación, aunque Elaboración sí.
    assert contexto_auditoria(convenio_listo)["responsable_id"] is None


def test_contexto_no_hace_autoflush_antes_de_declarar_el_evento(db, gestor, crear_convenio):
    convenio = crear_convenio(gestor)
    db.expire(convenio, ["etapa_actual"])
    convenio.objeto = "Cambio todavía sin contexto"
    contexto = contexto_auditoria(convenio)
    assert db.is_modified(convenio)
    describir_accion(db, gestor, "Edición contextualizada", evento="CONVENIO_EDITADO", **contexto)
    db.commit()
    assert _ultima_fila(db, "convenio", convenio.id).evento == "CONVENIO_EDITADO"


def test_fallo_de_radicacion_despues_de_flush_no_deja_eventos_huerfanos(
    client, db, solicitud_para_radicar, monkeypatch,
):
    from sqlalchemy.exc import SQLAlchemyError

    from backend.services.notificaciones import ServicioNotificaciones

    solicitud_id = solicitud_para_radicar
    antes = set(db.scalars(select(Auditoria.id)).all())

    def fallar(*_args):
        db.flush()
        assert db.scalar(select(Auditoria.id).where(
            Auditoria.evento == "SOLICITUD_RADICADA",
            Auditoria.registro_id == solicitud_id,
        )) is not None
        raise SQLAlchemyError("Fallo tras registrar el evento y sus efectos")

    monkeypatch.setattr(ServicioNotificaciones, "resolver", fallar)
    with pytest.raises(SQLAlchemyError):
        client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert set(db.scalars(select(Auditoria.id)).all()) == antes
    solicitud = db.get(SolicitudConvenio, solicitud_id)
    assert solicitud.estado == "BORRADOR"
    assert solicitud.fecha_radicacion is None
    assert bitacora.CLAVE_CAMBIOS_AUTOMATICOS not in db.info


@pytest.mark.parametrize(("modelo", "campo", "secreto"), [
    (Usuario, "hash_contrasena", "hash-reservado"),
    (InvitacionRevisionContraparte, "token_hash", "token-reservado"),
    (FirmaConvenio, "firma_png", b"firma-reservada"),
    (BorradorConvenio, "contenido", {"text": "documento-reservado"}),
    (RevisionConvenio, "snapshot_datos", {"text": "snapshot-reservado"}),
])
def test_redaccion_se_conserva_con_ejecucion_automatica(modelo, campo, secreto):
    objeto = modelo(id=123)
    setattr(objeto, campo, secreto)
    actor = bitacora.Actor(7, "GESTOR_ORI")
    accion = bitacora.Accion(actor, "Efecto derivado", ejecucion="AUTOMATICA")
    (fila,) = bitacora._filas_de_modificacion(
        objeto, modelo.__tablename__, actor, accion.descripcion, None, accion,
    )
    assert fila["campo"] == campo
    assert fila["valor_anterior"] is None and fila["valor_nuevo"] is None
    assert fila["ejecucion"] == "AUTOMATICA" and fila["usuario_id"] == 7


def test_creacion_audita_la_version_inicial_real(client, db, gestor):
    creada = client.post("/api/convenios/manual", json={})
    assert creada.status_code == 201
    convenio_id = creada.json()["id"]
    fila = _ultima_fila(db, "convenio", convenio_id)
    assert fila.evento == "CONVENIO_CREADO_MANUAL"
    assert fila.etapa == "ELABORACION"
    assert fila.version == creada.json()["version_actual"] == 1


def test_revision_audita_la_version_generada_y_su_asignacion(
    db, gestor, revisor, convenio_listo,
):
    servicio = ServicioConvenios(db)
    servicio.finalizar_elaboracion(convenio_listo.id, gestor)
    revision = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio_listo.id,
    ))
    revision.responsable_id = revisor.id
    db.commit()
    numero = convenio_listo.version_actual
    version = servicio.guardar_contenido_revision(
        convenio_listo.id, revision.id,
        RevisionContenidoGuardar(expected_version=numero, contenido={
            "type": "doc", "content": [{"type": "paragraph", "content": [
                {"type": "text", "text": "Corrección jurídica"},
            ]}],
        }), revisor,
    )
    fila = _ultima_fila(db, "convenio", convenio_listo.id)
    assert fila.evento == "CONTENIDO_CORREGIDO_REVISION"
    assert fila.etapa == "REVISION_AVAL_JURIDICO"
    assert fila.version == version.numero == numero + 1
    assert fila.responsable_id == revisor.id
    assert fila.usuario_id == revisor.id


@pytest.mark.parametrize(("con_cambios", "evento", "numero"), [
    (True, "VERSION_GENERADA", 2), (False, "VERSION_REUTILIZADA", 1),
])
def test_eventos_ht13_se_persisten_sin_versionar_cada_guardado(
    client, db, gestor, convenio_listo, con_cambios, evento, numero,
):
    ruta = f"/api/convenios/{convenio_listo.id}/elaboracion"
    datos = client.get(ruta).json()
    if con_cambios:
        datos["contenido"] = {"type": "doc", "content": [{"type": "paragraph", "content": [
            {"type": "text", "text": "Avance persistido"},
        ]}]}
    guardado = client.patch(ruta, json={"contenido": datos["contenido"], "expected_revision": 0})
    assert guardado.status_code == 200
    assert guardado.json()["version_actual"] == 1
    if con_cambios:
        fila = db.scalar(select(Auditoria).where(
            Auditoria.entidad == "borrador_convenio", Auditoria.evento == "BORRADOR_GUARDADO",
        ).order_by(Auditoria.id.desc()))
        assert (fila.etapa, fila.version, fila.usuario_id) == ("ELABORACION", 1, gestor.id)
    antes = db.scalar(select(func.count()).select_from(Auditoria))
    repetido = client.patch(ruta, json={
        "contenido": datos["contenido"], "expected_revision": guardado.json()["revision_borrador"],
    })
    assert repetido.status_code == 200
    assert db.scalar(select(func.count()).select_from(Auditoria)) == antes
    final = client.post(f"{ruta}/finalizar", json={
        "expected_revision": guardado.json()["revision_borrador"],
    })
    assert final.status_code == 200
    revision = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio_listo.id,
    ))
    fila = _ultima_fila(db, "revision_convenio", revision.id)
    assert (fila.evento, fila.etapa, fila.version) == (evento, "ELABORACION", numero)


def test_not_null_legacy_es_incompatible_con_proceso_sin_originador(db):
    # Solo una tabla temporal: no se altera auditoria ni se ejecuta downgrade.
    db.execute(text("CREATE TEMP TABLE ht09_rollback_usuario (usuario_id INTEGER) ON COMMIT DROP"))
    db.execute(text("INSERT INTO ht09_rollback_usuario VALUES (NULL)"))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("ALTER TABLE ht09_rollback_usuario ALTER COLUMN usuario_id SET NOT NULL"))
    assert db.scalar(text("SELECT count(*) FROM ht09_rollback_usuario WHERE usuario_id IS NULL")) == 1


@pytest.mark.parametrize("hay_datos", [True, False])
def test_downgrade_verifica_integridad_antes_de_cualquier_ddl(monkeypatch, hay_datos):
    ruta = Path(__file__).parents[1] / "migrations/versions/9d53cf1dcef3_ht_09_ampliar_bitacora_de_auditoria.py"
    spec = spec_from_file_location("migracion_ht09", ruta)
    migracion = module_from_spec(spec)
    spec.loader.exec_module(migracion)
    operaciones = Mock()
    operaciones.get_bind.return_value.scalar.return_value = hay_datos
    monkeypatch.setattr(migracion, "op", operaciones)
    if hay_datos:
        with pytest.raises(RuntimeError, match="Downgrade HT-09 bloqueado"):
            migracion.downgrade()
        operaciones.drop_constraint.assert_not_called()
        operaciones.alter_column.assert_not_called()
        operaciones.drop_column.assert_not_called()
    else:
        migracion.downgrade()
        operaciones.alter_column.assert_called_once()
        assert operaciones.alter_column.call_args.args == ("auditoria", "usuario_id")
        assert operaciones.alter_column.call_args.kwargs["nullable"] is False
