from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
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


def test_ca01_gestor_consulta_detalle_de_solicitud_pendiente(
    client, gestor, crear_solicitud
):
    solicitud = crear_solicitud()
    respuesta = client.get(f"/api/solicitudes/recibidas/{solicitud.id}")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "RADICADA"
    assert cuerpo["solicitante_id"] == solicitud.solicitante_id
    assert cuerpo["nombre_aliado_propuesto"] == "Universidad Contraparte"
    assert "documentos" in cuerpo


def test_ca02_aceptar_registra_responsable_fecha_y_auditoria(
    client, db, gestor, crear_solicitud
):
    solicitud = crear_solicitud()
    respuesta = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "APROBADA"
    assert cuerpo["decidida_por_id"] == gestor.id
    assert cuerpo["decidida_por_nombre"] == gestor.nombre_completo
    assert cuerpo["fecha_decision"] is not None
    auditoria = db.scalar(
        select(Auditoria).where(
            Auditoria.entidad == "solicitud",
            Auditoria.registro_id == solicitud.id,
            Auditoria.campo == "estado",
        )
    )
    assert (auditoria.valor_anterior, auditoria.valor_nuevo, auditoria.usuario_id) == (
        "RADICADA",
        "APROBADA",
        gestor.id,
    )


def test_ca03_aceptar_no_crea_convenio(client, db, gestor, crear_solicitud):
    solicitud = crear_solicitud()
    client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert (
        db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud.id))
        is None
    )
    detalle = client.get(f"/api/solicitudes/recibidas/{solicitud.id}").json()
    assert detalle["convenio_id"] is None


def test_ca04_rechazar_conserva_motivo_y_sigue_consultable(
    client, gestor, crear_solicitud
):
    solicitud = crear_solicitud(EstadoSolicitud.EN_ESTUDIO)
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/rechazar",
        json={"motivo": "  La contraparte no cumple requisitos  "},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "RECHAZADA"
    assert respuesta.json()["motivo_rechazo"] == "La contraparte no cumple requisitos"
    bandeja = client.get("/api/solicitudes/recibidas").json()["items"]
    assert solicitud.id in {item["id"] for item in bandeja}


@pytest.mark.parametrize("motivo", ["", "   "])
def test_rechazo_sin_motivo_es_422(client, gestor, crear_solicitud, motivo):
    solicitud = crear_solicitud()
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/rechazar", json={"motivo": motivo}
    )
    assert respuesta.status_code == 422


@pytest.mark.parametrize(
    "estado",
    [EstadoSolicitud.APROBADA, EstadoSolicitud.RECHAZADA, EstadoSolicitud.DEVUELTA],
)
@pytest.mark.parametrize("accion", ["aceptar", "rechazar"])
def test_no_se_decide_fuera_de_revision(
    client, gestor, crear_solicitud, estado, accion
):
    solicitud = crear_solicitud(estado)
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/{accion}", json={"motivo": "x"}
    )
    assert respuesta.status_code == 409


def test_segunda_decision_no_pisa_la_primera(client, gestor, crear_solicitud):
    solicitud = crear_solicitud()
    aceptada = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert aceptada.status_code == 200
    segunda = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/rechazar", json={"motivo": "tarde"}
    )
    assert segunda.status_code == 409


def test_borrador_no_es_visible_para_decidir(client, gestor, crear_solicitud):
    solicitud = crear_solicitud(EstadoSolicitud.BORRADOR)
    respuesta = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert respuesta.status_code == 404


@pytest.mark.parametrize(
    "rol,tipo",
    [
        (CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_solo_gestion_ori_puede_decidir(
    client, crear_usuario, entrar_como, crear_solicitud, rol, tipo
):
    solicitud = crear_solicitud()
    entrar_como(crear_usuario(rol, tipo))
    aceptar = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    rechazar = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/rechazar", json={"motivo": "x"}
    )
    assert (aceptar.status_code, rechazar.status_code) == (403, 403)


def test_administrador_tambien_puede_aceptar(
    client, crear_usuario, entrar_como, crear_solicitud
):
    solicitud = crear_solicitud()
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO))
    respuesta = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert respuesta.status_code == 200
