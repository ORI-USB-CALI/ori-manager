from uuid import uuid4

import pytest
from sqlalchemy import func, select

from backend.models.convenio import Convenio
from backend.models.enums import EstadoSolicitud, TipoSolicitante
from backend.models.historial_etapa import HistorialEtapa
from backend.models.solicitud_convenio import SolicitudConvenio


@pytest.fixture
def solicitud_radicada(db, solicitante) -> SolicitudConvenio:
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
    return solicitud


def _iniciar_elaboracion(client, solicitud_id: int):
    return client.post(f"/api/solicitudes/recibidas/{solicitud_id}/iniciar-elaboracion")


def _convenio_de(db, solicitud_id: int) -> Convenio:
    convenio = db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud_id))
    assert convenio is not None
    db.refresh(convenio)
    return convenio


def _ingreso_a_elaboracion(db, convenio_id: int) -> HistorialEtapa:
    return db.scalar(
        select(HistorialEtapa).where(
            HistorialEtapa.convenio_id == convenio_id,
            HistorialEtapa.etapa_origen_id.is_(None),
        )
    )


def test_iniciar_elaboracion_registra_la_fecha_del_hito(
    db, client, gestor, solicitud_radicada
) -> None:
    client.post(f"/api/solicitudes/recibidas/{solicitud_radicada.id}/aceptar")

    respuesta = _iniciar_elaboracion(client, solicitud_radicada.id)

    assert respuesta.status_code == 200
    convenio = _convenio_de(db, solicitud_radicada.id)
    assert convenio.elaboracion_iniciada_en is not None
    assert (
        convenio.elaboracion_iniciada_en
        == _ingreso_a_elaboracion(db, convenio.id).fecha_cambio
    )
    assert convenio.activado_en is None


def test_repetir_iniciar_elaboracion_conserva_la_fecha_original(
    db, client, gestor, solicitud_radicada
) -> None:
    client.post(f"/api/solicitudes/recibidas/{solicitud_radicada.id}/aceptar")
    _iniciar_elaboracion(client, solicitud_radicada.id)
    original = _convenio_de(db, solicitud_radicada.id).elaboracion_iniciada_en

    _iniciar_elaboracion(client, solicitud_radicada.id)

    assert _convenio_de(db, solicitud_radicada.id).elaboracion_iniciada_en == original
    assert db.scalar(
        select(func.count())
        .select_from(Convenio)
        .where(Convenio.solicitud_id == solicitud_radicada.id)
    ) == 1


def test_crear_convenio_directo_tambien_registra_el_hito(
    db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    db.refresh(convenio)

    assert convenio.elaboracion_iniciada_en is not None
    assert (
        convenio.elaboracion_iniciada_en
        == _ingreso_a_elaboracion(db, convenio.id).fecha_cambio
    )
    assert convenio.activado_en is None


@pytest.mark.parametrize("campo", ["elaboracion_iniciada_en", "activado_en"])
def test_el_cliente_no_puede_fijar_los_hitos(
    db, client, gestor, solicitud_radicada, campo
) -> None:
    solicitud_radicada.estado = EstadoSolicitud.APROBADA.value
    db.commit()

    respuesta = client.post(
        "/api/convenios",
        json={
            "solicitud_id": solicitud_radicada.id,
            "objeto": "Convenio con hito enviado por el cliente",
            "alcance": "INSTITUCIONAL",
            campo: "2020-01-01T00:00:00Z",
        },
    )

    assert respuesta.status_code == 422
    assert db.scalar(
        select(Convenio.id).where(Convenio.solicitud_id == solicitud_radicada.id)
    ) is None
