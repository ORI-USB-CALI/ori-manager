from uuid import uuid4

import pytest

from backend.models.enums import EstadoSolicitud, TipoSolicitante
from backend.models.solicitud_convenio import SolicitudConvenio


@pytest.fixture
def crear_solicitud(db, solicitante):
    def _crear(estado: EstadoSolicitud = EstadoSolicitud.RADICADA) -> SolicitudConvenio:
        solicitud = SolicitudConvenio(
            consecutivo=f"SOL-{uuid4().hex[:12]}",
            tipo_solicitante=TipoSolicitante.INTERNO.value,
            solicitante_id=solicitante.id,
            objeto="Cooperación académica",
            nombre_aliado_propuesto="Universidad Contraparte",
            estado=estado.value,
        )
        db.add(solicitud)
        db.commit()
        return solicitud

    return _crear


def test_solicitud_sin_decision_tiene_campos_nulos(crear_solicitud):
    solicitud = crear_solicitud(EstadoSolicitud.APROBADA)
    assert solicitud.decidida_por_id is None
    assert solicitud.fecha_decision is None
