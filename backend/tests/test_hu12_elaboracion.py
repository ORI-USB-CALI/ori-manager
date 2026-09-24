"""HU-12 — Elaborar el proyecto de convenio.

BE-2: la edición solo ocurre en etapa de Elaboración, cada cambio queda auditado,
la solicitud original no se altera y los guardados parciales no mueven la etapa.
BE-3: la vista de elaboración expone el convenio con su antecedente heredado.
BE-4: la validación indica qué falta para poder entregar el proyecto a Jurídica.
"""

from collections.abc import Callable
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import (
    AccionAuditoria,
    AlcanceConvenio,
    EstadoConvenio,
    EstadoRevisionConvenio,
    EstadoSolicitud,
    TipoAliado,
    TipoIdentificacion,
    TipoRevisionConvenio,
    TipoSolicitante,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario
from backend.schemas.convenio import ConvenioCrear
from backend.services.convenios import ServicioConvenios


@pytest.fixture
def gestor(client, crear_usuario, entrar_como) -> Usuario:
    usuario = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    entrar_como(usuario)
    return usuario


@pytest.fixture
def crear_convenio(db: Session) -> Callable[..., Convenio]:
    """Crea el convenio mediante el contrato canónico de HU-06."""

    def _crear(autor: Usuario, **cambios) -> Convenio:
        aliado_id = cambios.pop("aliado_id", None)
        solicitud = SolicitudConvenio(
            consecutivo=f"SOL-{uuid4().hex}",
            tipo_solicitante=TipoSolicitante.INTERNO.value,
            solicitante_id=autor.id,
            objeto="Objeto solicitado originalmente",
            justificacion="Fortalecer la movilidad académica",
            vigencia_estimada="24 meses",
            estado=EstadoSolicitud.APROBADA.value,
            aliado_id=aliado_id,
            nombre_aliado_propuesto="Universidad Contraparte",
            correo_aliado_propuesto="convenios@contraparte.example",
            contacto_contraparte_nombre="Ana Gómez",
            contacto_contraparte_correo="ana.gomez@contraparte.example",
            supervisor_usb_nombre="Carlos Ruiz",
            supervisor_usb_cargo="Coordinador de Internacionalización",
            supervisor_contraparte_nombre="María Salas",
            supervisor_contraparte_cargo="Directora de Relaciones",
        )
        db.add(solicitud)
        db.commit()

        datos = {
            "solicitud_id": solicitud.id,
            "objeto": "Objeto inicial del convenio",
            "alcance": AlcanceConvenio.INSTITUCIONAL,
            **cambios,
        }
        return ServicioConvenios(db).crear(
            ConvenioCrear.model_validate(datos),
            autor,
        )

    return _crear


def _auditoria_de(db: Session, convenio_id: int) -> list[Auditoria]:
    return list(
        db.scalars(
            select(Auditoria)
            .where(
                Auditoria.entidad == "convenio",
                Auditoria.registro_id == convenio_id,
            )
            .order_by(Auditoria.campo)
        )
    )


def _historiales_de(db: Session, convenio_id: int) -> list[HistorialEtapa]:
    return list(
        db.scalars(
            select(HistorialEtapa)
            .where(HistorialEtapa.convenio_id == convenio_id)
            .order_by(HistorialEtapa.id)
        )
    )


def test_convenio_creado_canonicamente_registra_ingreso_a_elaboracion(
    db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    elaboracion = db.scalar(select(Etapa).where(Etapa.codigo == "ELABORACION"))

    assert convenio.estado == EstadoConvenio.EN_TRAMITE
    assert convenio.etapa_actual_id == elaboracion.id
    historiales = _historiales_de(db, convenio.id)
    assert len(historiales) == 1
    assert historiales[0].etapa_origen_id is None
    assert historiales[0].etapa_destino_id == elaboracion.id


def test_ca05_guardado_parcial_conserva_etapa_elaboracion(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    etapa_antes = convenio.etapa_actual_id

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"objeto": "Objeto ajustado durante la elaboración"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["objeto"] == "Objeto ajustado durante la elaboración"
    db.refresh(convenio)
    assert convenio.etapa_actual_id == etapa_antes
    assert len(_historiales_de(db, convenio.id)) == 1


def test_ca03_edicion_bloqueada_fuera_de_elaboracion(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    juridica = db.scalar(select(Etapa).where(Etapa.codigo == "REVISION_AVAL_JURIDICO"))
    convenio.etapa_actual = juridica
    db.commit()

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}", json={"objeto": "Cambio tardío"}
    )

    assert respuesta.status_code == 409
    db.refresh(convenio)
    assert convenio.objeto == "Objeto inicial del convenio"
    assert _auditoria_de(db, convenio.id) == []


def test_ca07_cada_campo_modificado_genera_una_fila_de_auditoria(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}",
        json={
            "objeto": "Objeto revisado",
            "implicacion_financiera": "Sin costo para la Universidad",
        },
    )
    assert respuesta.status_code == 200

    registros = _auditoria_de(db, convenio.id)
    assert len(registros) == 2

    por_campo = {r.campo: r for r in registros}
    assert set(por_campo) == {"implicacion_financiera", "objeto"}

    objeto = por_campo["objeto"]
    assert objeto.valor_anterior == "Objeto inicial del convenio"
    assert objeto.valor_nuevo == "Objeto revisado"

    financiera = por_campo["implicacion_financiera"]
    assert financiera.valor_anterior is None
    assert financiera.valor_nuevo == "Sin costo para la Universidad"

    for registro in registros:
        assert registro.usuario_id == gestor.id
        assert registro.accion == AccionAuditoria.UPDATE.value
        assert registro.fecha_hora is not None


def test_ca07_reenviar_el_mismo_valor_no_genera_auditoria(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}", json={"objeto": "Objeto inicial del convenio"}
    )

    assert respuesta.status_code == 200
    assert _auditoria_de(db, convenio.id) == []


def test_ca04_editar_el_convenio_no_altera_la_solicitud_original(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    solicitud = db.get(SolicitudConvenio, convenio.solicitud_id)
    objeto_solicitado = solicitud.objeto
    actualizado_en = solicitud.actualizado_en

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"objeto": "La ORI redacta un objeto distinto al solicitado"},
    )
    assert respuesta.status_code == 200

    db.refresh(solicitud)
    db.refresh(convenio)
    assert solicitud.objeto == objeto_solicitado
    assert solicitud.actualizado_en == actualizado_en
    assert convenio.objeto != solicitud.objeto
    # La relación entre ambos registros se conserva.
    assert convenio.solicitud_id == solicitud.id


def test_ca05_guardados_sucesivos_no_generan_historial_de_etapa(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    historial_antes = db.scalar(
        select(func.count())
        .select_from(HistorialEtapa)
        .where(HistorialEtapa.convenio_id == convenio.id)
    )

    for numero in range(3):
        respuesta = client.patch(
            f"/api/convenios/{convenio.id}", json={"objeto": f"Versión {numero}"}
        )
        assert respuesta.status_code == 200

    historial_despues = db.scalar(
        select(func.count())
        .select_from(HistorialEtapa)
        .where(HistorialEtapa.convenio_id == convenio.id)
    )
    assert historial_despues == historial_antes
    assert historial_despues == 1
    assert len(_auditoria_de(db, convenio.id)) == 3


def test_ca05_programa_sin_unidad_se_puede_guardar_como_avance(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"alcance": "PROGRAMA", "unidad_organizacional_id": None},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["alcance"] == "PROGRAMA"
    assert respuesta.json()["unidad_organizacional_id"] is None
    db.refresh(convenio)
    assert convenio.alcance == AlcanceConvenio.PROGRAMA
    assert convenio.unidad_organizacional_id is None
    assert len(_historiales_de(db, convenio.id)) == 1


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("codigo", "NO-PERMITIDO"),
        ("fecha_firma", "2026-01-01"),
        ("porcentaje_avance", 10),
        ("convenio_origen_id", 1),
        ("numero_renovacion", 1),
        ("aliado_id", 1),
        ("solicitud_id", 1),
        ("estado", "VIGENTE"),
        ("etapa_actual_id", 1),
        ("creado_por_id", 1),
        ("id", 1),
        ("creado_en", "2026-01-01T00:00:00Z"),
        ("actualizado_en", "2026-01-01T00:00:00Z"),
    ],
)
def test_patch_rechaza_campos_fuera_del_alcance_hu12(
    client, gestor, crear_convenio, campo, valor
) -> None:
    convenio = crear_convenio(gestor)

    respuesta = client.patch(f"/api/convenios/{convenio.id}", json={campo: valor})

    assert respuesta.status_code == 422


def test_tipo_convenio_valido_se_puede_guardar(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}", json={"tipo_convenio_id": tipo.id}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["tipo_convenio_id"] == tipo.id


def test_tipo_convenio_inexistente_se_rechaza(
    client, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}", json={"tipo_convenio_id": 999999999}
    )

    assert respuesta.status_code == 422


def test_catalogo_elaboracion_solo_expone_referencias_activas(
    client, db, gestor
) -> None:
    sufijo = uuid4().hex[:24]
    tipo_inactivo = TipoConvenio(
        codigo=f"INACTIVO-{sufijo}",
        nombre="Tipo inactivo",
        duracion_meses_defecto=18,
        activo=False,
    )
    unidad_inactiva = UnidadOrganizacional(
        codigo=f"INACTIVA-{sufijo}",
        nombre="Unidad inactiva",
        tipo="FACULTAD",
        activa=False,
    )
    db.add_all([tipo_inactivo, unidad_inactiva])
    db.commit()

    respuesta = client.get("/api/convenios/catalogos/elaboracion")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["tipos_convenio"]
    assert cuerpo["unidades_organizacionales"]
    assert tipo_inactivo.id not in {item["id"] for item in cuerpo["tipos_convenio"]}
    assert unidad_inactiva.id not in {
        item["id"] for item in cuerpo["unidades_organizacionales"]
    }
    assert {
        "id",
        "codigo",
        "nombre",
        "naturaleza",
        "duracion_meses_defecto",
    } == set(cuerpo["tipos_convenio"][0])


# --- BE-3: vista de elaboración (CA-01, CA-02) ---


def test_ca01_ca02_vista_expone_antecedente_y_conserva_aliado(
    client, db, gestor, crear_convenio
) -> None:
    aliado = Aliado(
        nombre="Universidad Contraparte",
        tipo=TipoAliado.UNIVERSIDAD.value,
        tipo_identificacion=TipoIdentificacion.NIT.value,
        identificacion=str(900000000 + (uuid4().int % 99999999)),
    )
    db.add(aliado)
    db.commit()
    convenio = crear_convenio(gestor, aliado_id=aliado.id)

    respuesta = client.get(f"/api/convenios/{convenio.id}/elaboracion")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()

    # CA-01: identifica la solicitud que le dio origen.
    assert cuerpo["solicitud"]["id"] == convenio.solicitud_id
    assert cuerpo["solicitud"]["consecutivo"].startswith("SOL-")
    assert cuerpo["solicitud"]["objeto"] == "Objeto solicitado originalmente"
    assert cuerpo["etapa_actual"]["codigo"] == "ELABORACION"

    # CA-02: conserva la contraparte y la relación con el aliado.
    assert cuerpo["aliado"]["id"] == aliado.id
    assert cuerpo["solicitud"]["nombre_aliado_propuesto"] == "Universidad Contraparte"
    assert cuerpo["solicitud"]["contacto_contraparte_nombre"] == "Ana Gómez"

    # Supervisores como contexto (su gestión formal es HU-19).
    assert cuerpo["solicitud"]["supervisor_usb_nombre"] == "Carlos Ruiz"
    assert cuerpo["solicitud"]["supervisor_contraparte_nombre"] == "María Salas"


def test_ca02_la_vista_de_elaboracion_es_de_solo_lectura(
    client, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    ruta = f"/api/convenios/{convenio.id}/elaboracion"

    assert client.post(ruta, json={"objeto": "X"}).status_code == 405
    assert client.patch(ruta, json={"objeto": "X"}).status_code == 405


def test_vista_de_elaboracion_inexistente_responde_404(client, gestor) -> None:
    assert client.get("/api/convenios/999999/elaboracion").status_code == 404


# --- BE-4: validación de completitud (CA-06) ---


def test_ca06_reporta_los_campos_requeridos_que_faltan(
    client, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)

    cuerpo = client.get(
        f"/api/convenios/{convenio.id}/elaboracion/validacion"
    ).json()

    assert cuerpo["completo"] is False
    faltantes = {f["campo"] for f in cuerpo["faltantes"]}
    assert faltantes == {
        "tipo_convenio_id",
        "implicacion_financiera",
        "duracion_meses",
    }


def test_ca06_convenio_completo_no_reporta_faltantes(
    client, db, gestor, crear_convenio
) -> None:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    convenio = crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Sin costo para la Universidad",
        duracion_meses=24,
    )

    cuerpo = client.get(
        f"/api/convenios/{convenio.id}/elaboracion/validacion"
    ).json()

    assert cuerpo["completo"] is True
    assert cuerpo["faltantes"] == []


def test_ca06_codigo_y_fechas_no_son_obligatorios(
    client, db, gestor, crear_convenio
) -> None:
    """codigo puede entrar en NULL a Jurídica y las fechas son opcionales en esta etapa."""
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    convenio = crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Aporte en especie",
        duracion_meses=12,
    )
    assert convenio.codigo is None
    assert convenio.fecha_inicio is None

    cuerpo = client.get(
        f"/api/convenios/{convenio.id}/elaboracion/validacion"
    ).json()

    assert cuerpo["completo"] is True


def test_ca06_alcance_programa_exige_unidad_organizacional(
    client, db, gestor, crear_convenio
) -> None:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    convenio = crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Sin costo",
        duracion_meses=12,
    )
    convenio.alcance = AlcanceConvenio.PROGRAMA.value
    db.commit()

    cuerpo = client.get(
        f"/api/convenios/{convenio.id}/elaboracion/validacion"
    ).json()

    assert cuerpo["completo"] is False
    assert [f["campo"] for f in cuerpo["faltantes"]] == ["unidad_organizacional_id"]


def test_ca06_finalizar_programa_sin_unidad_es_rechazado(
    client, db, gestor, crear_convenio
) -> None:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    convenio = crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Sin costo",
        duracion_meses=12,
    )
    guardado = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"alcance": "PROGRAMA", "unidad_organizacional_id": None},
    )
    assert guardado.status_code == 200

    respuesta = client.post(f"/api/convenios/{convenio.id}/elaboracion/finalizar")

    assert respuesta.status_code == 422
    assert [
        item["campo"] for item in respuesta.json()["detail"]["faltantes"]
    ] == ["unidad_organizacional_id"]
    db.refresh(convenio)
    assert convenio.etapa_actual.codigo == "ELABORACION"
    assert len(_historiales_de(db, convenio.id)) == 1
    assert _revisiones_de(db, convenio.id) == []


def test_ca06_vencimiento_anterior_al_inicio_se_reporta(
    client, db, gestor, crear_convenio
) -> None:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    convenio = crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Sin costo",
        duracion_meses=12,
        fecha_inicio=date(2026, 6, 1),
        fecha_vencimiento=date(2026, 1, 1),
    )

    cuerpo = client.get(
        f"/api/convenios/{convenio.id}/elaboracion/validacion"
    ).json()

    assert cuerpo["completo"] is False
    assert [f["campo"] for f in cuerpo["faltantes"]] == ["fecha_vencimiento"]


# --- BE-5: snapshot inmutable y finalización (CA-06, CA-08) ---


@pytest.fixture
def convenio_listo(db: Session, gestor, crear_convenio) -> Convenio:
    """Convenio con todo lo requerido para entregarlo a Jurídica."""
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    return crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Sin costo para la Universidad",
        duracion_meses=24,
        fecha_inicio=date(2026, 1, 1),
        fecha_vencimiento=date(2028, 1, 1),
    )


def _revisiones_de(db: Session, convenio_id: int) -> list[RevisionConvenio]:
    return list(
        db.scalars(
            select(RevisionConvenio)
            .where(RevisionConvenio.convenio_id == convenio_id)
            .order_by(RevisionConvenio.id)
        )
    )


def test_ca06_finalizar_incompleto_no_cambia_nada(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)  # sin tipo, implicación ni duración
    etapa_antes = convenio.etapa_actual_id

    respuesta = client.post(f"/api/convenios/{convenio.id}/elaboracion/finalizar")

    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    assert {f["campo"] for f in detalle["faltantes"]} == {
        "tipo_convenio_id",
        "implicacion_financiera",
        "duracion_meses",
    }

    db.refresh(convenio)
    assert convenio.etapa_actual_id == etapa_antes
    assert _revisiones_de(db, convenio.id) == []
    assert (
        db.scalar(
            select(func.count())
            .select_from(HistorialEtapa)
            .where(HistorialEtapa.convenio_id == convenio.id)
        )
        == 1
    )


def test_ca08_finalizar_mueve_etapa_y_abre_revision_juridica(
    client, db, gestor, convenio_listo
) -> None:
    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    )
    assert respuesta.status_code == 200

    juridica = db.scalar(select(Etapa).where(Etapa.codigo == "REVISION_AVAL_JURIDICO"))
    db.refresh(convenio_listo)
    assert convenio_listo.etapa_actual_id == juridica.id
    assert convenio_listo.estado == EstadoConvenio.EN_TRAMITE

    revisiones = _revisiones_de(db, convenio_listo.id)
    assert len(revisiones) == 1
    revision = revisiones[0]
    assert revision.tipo == TipoRevisionConvenio.JURIDICA.value
    assert revision.estado == EstadoRevisionConvenio.PENDIENTE.value
    assert revision.resultado is None
    assert revision.documento_id is None
    # HU-13 decidirá quién toma la revisión: aquí no se asigna revisor.
    assert revision.responsable_id is None

    elaboracion = db.scalar(select(Etapa).where(Etapa.codigo == "ELABORACION"))
    historiales = _historiales_de(db, convenio_listo.id)
    assert len(historiales) == 2
    inicial = next(item for item in historiales if item.etapa_origen_id is None)
    transicion = next(
        item
        for item in historiales
        if item.etapa_origen_id == elaboracion.id
        and item.etapa_destino_id == juridica.id
    )
    assert inicial.etapa_destino_id == elaboracion.id
    assert transicion.usuario_id == gestor.id
    assert transicion.responsable_id is None
    # La revisión queda enlazada a la transición real que la originó.
    assert revision.historial_etapa_id == transicion.id


def test_ca08_snapshot_congela_los_trece_campos(client, db, convenio_listo) -> None:
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")

    snapshot = _revisiones_de(db, convenio_listo.id)[0].snapshot_datos

    assert set(snapshot) == {
        "codigo",
        "solicitud_id",
        "aliado_id",
        "tipo_convenio_id",
        "objeto",
        "alcance",
        "unidad_organizacional_id",
        "implicacion_financiera",
        "fecha_inicio",
        "fecha_vencimiento",
        "duracion_meses",
        "convenio_origen_id",
        "numero_renovacion",
    }
    assert snapshot["objeto"] == convenio_listo.objeto
    assert snapshot["duracion_meses"] == 24
    assert snapshot["fecha_inicio"] == "2026-01-01"
    # Los nulos se conservan como nulos, no se omiten ni se rellenan.
    assert snapshot["codigo"] is None
    assert snapshot["aliado_id"] is None
    # Nada de etapas posteriores ni objetos ORM.
    assert "fecha_firma" not in snapshot
    assert "porcentaje_avance" not in snapshot


def test_ca08_el_snapshot_no_cambia_si_el_convenio_cambia_despues(
    client, db, convenio_listo
) -> None:
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")
    snapshot_original = dict(_revisiones_de(db, convenio_listo.id)[0].snapshot_datos)

    # Se fuerza un cambio posterior en el convenio, saltando el guard de etapa.
    db.refresh(convenio_listo)
    convenio_listo.objeto = "Objeto modificado después de entregar a Jurídica"
    db.commit()

    assert _revisiones_de(db, convenio_listo.id)[0].snapshot_datos == snapshot_original


def test_ca08_no_se_puede_finalizar_dos_veces(client, db, convenio_listo) -> None:
    assert (
        client.post(
            f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
        ).status_code
        == 200
    )

    segunda = client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    )

    assert segunda.status_code == 409
    assert len(_revisiones_de(db, convenio_listo.id)) == 1
    assert len(_historiales_de(db, convenio_listo.id)) == 2


def test_revisor_puede_consultar_pero_no_editar_ni_finalizar(
    client,
    gestor,
    crear_convenio,
    crear_usuario,
    entrar_como,
) -> None:
    convenio = crear_convenio(gestor)
    revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(revisor)

    assert client.get(f"/api/convenios/{convenio.id}/elaboracion").status_code == 200
    assert (
        client.get("/api/convenios/catalogos/elaboracion").status_code == 200
    )
    assert (
        client.patch(
            f"/api/convenios/{convenio.id}", json={"objeto": "Cambio no permitido"}
        ).status_code
        == 403
    )
    assert (
        client.post(f"/api/convenios/{convenio.id}/elaboracion/finalizar").status_code
        == 403
    )


def test_usuario_sin_permisos_no_puede_consultar_editar_ni_finalizar(
    client,
    gestor,
    crear_convenio,
    crear_usuario,
    entrar_como,
) -> None:
    convenio = crear_convenio(gestor)
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)
    entrar_como(solicitante)

    assert client.get(f"/api/convenios/{convenio.id}/elaboracion").status_code == 403
    assert (
        client.patch(f"/api/convenios/{convenio.id}", json={"objeto": "X"}).status_code
        == 403
    )
    assert (
        client.post(f"/api/convenios/{convenio.id}/elaboracion/finalizar").status_code
        == 403
    )
