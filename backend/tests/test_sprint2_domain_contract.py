from uuid import uuid4

from sqlalchemy import select

from backend.core.roles import CodigoRol
from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import (
    EstadoConvenio,
    EstadoObservacionRevision,
    EstadoRevisionConvenio,
    EstadoSolicitud,
    OrigenObservacionRevision,
    ResultadoRevisionConvenio,
    TipoAliado,
    TipoIdentificacion,
    TipoRevisionConvenio,
    TipoSolicitante,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio

CODIGOS_ETAPA_CANONICOS = {
    "SOLICITUD",
    "ELABORACION",
    "REVISION_AVAL_JURIDICO",
    "REVISION_CONTRAPARTE",
    "REVISION_FINAL",
    "APROBACION_FIRMAS",
    "FIRMA_ARCHIVO_SEGUIMIENTO",
}


def _crear_solicitud(
    db,
    usuario,
    *,
    estado: EstadoSolicitud = EstadoSolicitud.APROBADA,
    aliado_id: int | None = None,
) -> SolicitudConvenio:
    solicitud = SolicitudConvenio(
        consecutivo=f"SOL-{uuid4().hex}",
        tipo_solicitante=TipoSolicitante.INTERNO.value,
        solicitante_id=usuario.id,
        aliado_id=aliado_id,
        objeto="Solicitud para contrato de dominio",
        estado=estado.value,
    )
    db.add(solicitud)
    db.commit()
    return solicitud


def _crear_aliado(db) -> Aliado:
    aliado = Aliado(
        nombre="Aliado del contrato de dominio",
        tipo=TipoAliado.UNIVERSIDAD.value,
        tipo_identificacion=TipoIdentificacion.NIT.value,
        identificacion=str(900000000 + uuid4().int % 99999999),
        activo=True,
    )
    db.add(aliado)
    db.commit()
    return aliado


def _payload_convenio(solicitud_id: int) -> dict[str, object]:
    return {
        "solicitud_id": solicitud_id,
        "objeto": "Convenio del contrato de dominio",
        "alcance": "INSTITUCIONAL",
    }


def _autenticar_gestor(client, crear_usuario, entrar_como):
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    entrar_como(gestor)
    return gestor


def test_etapas_canonicas_y_elaboracion_resoluble_por_codigo(db):
    codigos = set(db.scalars(select(Etapa.codigo)))

    assert codigos == CODIGOS_ETAPA_CANONICOS
    elaboracion = db.scalar(select(Etapa).where(Etapa.codigo == "ELABORACION"))
    assert elaboracion is not None
    assert elaboracion.codigo == "ELABORACION"


def test_solicitud_aprobada_origina_convenio_e_historial_inicial(
    db, client, crear_usuario, entrar_como
):
    gestor = _autenticar_gestor(client, crear_usuario, entrar_como)
    solicitud = _crear_solicitud(db, gestor)

    respuesta = client.post("/api/convenios", json=_payload_convenio(solicitud.id))

    assert respuesta.status_code == 201
    convenio = db.get(Convenio, respuesta.json()["id"])
    assert convenio is not None
    assert convenio.estado == EstadoConvenio.EN_TRAMITE
    assert convenio.etapa_actual is not None
    assert convenio.etapa_actual.codigo == "ELABORACION"
    assert convenio.aliado_id is None
    db.refresh(solicitud)
    assert solicitud.estado == EstadoSolicitud.APROBADA

    historiales = list(
        db.scalars(
            select(HistorialEtapa).where(HistorialEtapa.convenio_id == convenio.id)
        )
    )
    assert len(historiales) == 1
    historial = historiales[0]
    assert historial.etapa_origen_id is None
    assert historial.etapa_destino.codigo == "ELABORACION"
    assert historial.usuario_id == gestor.id
    assert historial.responsable_id == gestor.id
    assert historial.observacion is None

    duplicada = client.post(
        "/api/convenios", json=_payload_convenio(solicitud.id)
    )
    assert duplicada.status_code == 409


def test_solicitud_no_aprobada_no_origina_convenio(
    db, client, crear_usuario, entrar_como
):
    gestor = _autenticar_gestor(client, crear_usuario, entrar_como)
    solicitud = _crear_solicitud(db, gestor, estado=EstadoSolicitud.RADICADA)

    respuesta = client.post("/api/convenios", json=_payload_convenio(solicitud.id))

    assert respuesta.status_code == 409
    assert (
        db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud.id))
        is None
    )


def test_convenio_deriva_aliado_de_solicitud(
    db, client, crear_usuario, entrar_como
):
    gestor = _autenticar_gestor(client, crear_usuario, entrar_como)
    aliado = _crear_aliado(db)
    solicitud = _crear_solicitud(db, gestor, aliado_id=aliado.id)

    respuesta = client.post("/api/convenios", json=_payload_convenio(solicitud.id))

    assert respuesta.status_code == 201
    assert respuesta.json()["aliado_id"] == aliado.id
    convenio = db.get(Convenio, respuesta.json()["id"])
    assert convenio is not None
    assert convenio.aliado_id == solicitud.aliado_id == aliado.id


def test_cliente_no_controla_estado_etapa_solicitud_ni_aliado(
    db, client, crear_usuario, entrar_como
):
    gestor = _autenticar_gestor(client, crear_usuario, entrar_como)
    solicitud = _crear_solicitud(db, gestor)
    for campo, valor in (
        ("aliado_id", 1),
        ("etapa_actual_id", 1),
        ("estado", EstadoConvenio.VIGENTE.value),
    ):
        respuesta = client.post(
            "/api/convenios",
            json={**_payload_convenio(solicitud.id), campo: valor},
        )
        assert respuesta.status_code == 422

    creada = client.post(
        "/api/convenios", json=_payload_convenio(solicitud.id)
    )
    assert creada.status_code == 201
    convenio_id = creada.json()["id"]
    for campo, valor in (
        ("solicitud_id", solicitud.id + 1),
        ("aliado_id", 1),
        ("etapa_actual_id", 1),
        ("estado", EstadoConvenio.VIGENTE.value),
    ):
        respuesta = client.patch(f"/api/convenios/{convenio_id}", json={campo: valor})
        assert respuesta.status_code == 422


def test_documento_soporta_solicitud_convenio_y_campos_estructurales(
    db, client, crear_usuario, entrar_como
):
    gestor = _autenticar_gestor(client, crear_usuario, entrar_como)
    solicitud = _crear_solicitud(db, gestor)
    creada = client.post(
        "/api/convenios", json=_payload_convenio(solicitud.id)
    )
    assert creada.status_code == 201
    convenio_id = creada.json()["id"]

    documento_solicitud = Documento(
        solicitud_id=solicitud.id,
        tipo="OTRO_SOPORTE",
        nombre_archivo="solicitud.pdf",
        ruta_almacenamiento=f"contrato/{uuid4().hex}.pdf",
        tipo_mime="application/pdf",
        tamano_bytes=10,
    )
    documento_convenio = Documento(
        convenio_id=convenio_id,
        tipo="BORRADOR",
        nombre_archivo="convenio.pdf",
        ruta_almacenamiento=f"contrato/{uuid4().hex}.pdf",
        tipo_mime="application/pdf",
        tamano_bytes=20,
    )
    db.add_all([documento_solicitud, documento_convenio])
    db.flush()

    assert documento_solicitud.solicitud_id == solicitud.id
    assert documento_solicitud.convenio_id is None
    assert documento_convenio.solicitud_id is None
    assert documento_convenio.convenio_id == convenio_id
    assert {"version", "es_vigente"} <= set(Documento.__table__.columns.keys())
    assert documento_solicitud.version is None
    assert documento_solicitud.es_vigente is True


def test_catalogos_canonicos_de_observacion_revision():
    assert {valor.value for valor in OrigenObservacionRevision} == {
        "REVISOR_ORI",
        "CONTRAPARTE",
        "REVISION_FINAL_ORI",
    }
    assert {valor.value for valor in EstadoObservacionRevision} == {
        "PENDIENTE",
        "ATENDIDA",
    }


def test_contrato_estructural_compartido_de_revision_convenio():
    assert {valor.value for valor in TipoRevisionConvenio} == {
        "JURIDICA",
        "CONTRAPARTE",
        "FINAL",
    }
    assert {valor.value for valor in EstadoRevisionConvenio} == {
        "PENDIENTE",
        "RESUELTA",
    }
    assert {valor.value for valor in ResultadoRevisionConvenio} == {
        "APROBADA",
        "DEVUELTA",
    }

    fk_documento = next(
        iter(RevisionConvenio.__table__.c.documento_id.foreign_keys)
    )
    fk_revision = next(
        iter(ObservacionRevision.__table__.c.revision_convenio_id.foreign_keys)
    )
    assert fk_documento.target_fullname == "documento.id"
    assert fk_revision.target_fullname == "revision_convenio.id"
