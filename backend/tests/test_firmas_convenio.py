from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol
from backend.models.convenio import Convenio
from backend.models.enums import (
    AlcanceConvenio,
    EstadoConvenio,
    EstadoFirma,
    EstadoSolicitud,
    ModalidadFirma,
    ParteFirmante,
    RolFirmante,
    TipoSolicitante,
)
from backend.models.firma_convenio import FirmaConvenio
from backend.models.solicitud_convenio import SolicitudConvenio


def _crear_convenio_aux(db: Session, usuario) -> Convenio:
    solicitud = SolicitudConvenio(
        consecutivo=f"SOL-{uuid4().hex[:8]}",
        tipo_solicitante=TipoSolicitante.INTERNO.value,
        solicitante_id=usuario.id,
        objeto="Solicitud de cooperación",
        estado=EstadoSolicitud.APROBADA.value,
    )
    db.add(solicitud)
    db.commit()

    convenio = Convenio(
        solicitud_id=solicitud.id,
        estado=EstadoConvenio.EN_TRAMITE.value,
        objeto="Cooperación institucional",
        alcance=AlcanceConvenio.INSTITUCIONAL.value,
        creado_por_id=usuario.id,
    )
    db.add(convenio)
    db.commit()
    return convenio


def test_crear_firma_convenio_exito(db: Session, crear_usuario):
    usuario = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    convenio = _crear_convenio_aux(db, usuario)

    firma = FirmaConvenio(
        convenio_id=convenio.id,
        orden=1,
        rol_firmante=RolFirmante.ADMINISTRADOR_ORI.value,
        parte=ParteFirmante.USB.value,
        nombre_firmante="Administrador ORI Test",
        cargo_firmante="Jefe ORI",
        modalidad=ModalidadFirma.ELECTRONICA.value,
        estado=EstadoFirma.PENDIENTE.value,
    )
    db.add(firma)
    db.commit()

    assert firma.id is not None
    assert firma.convenio_id == convenio.id
    assert firma.orden == 1
    assert firma.rol_firmante == "ADMINISTRADOR_ORI"
    assert firma.estado == "PENDIENTE"


def test_endpoint_consultar_revision_final(client, entrar_como, crear_usuario, db: Session):
    usuario_ori = crear_usuario(CodigoRol.GESTOR_ORI)
    entrar_como(usuario_ori)

    convenio = _crear_convenio_aux(db, usuario_ori)

    firmas = [
        FirmaConvenio(
            convenio_id=convenio.id,
            orden=1,
            rol_firmante=RolFirmante.ADMINISTRADOR_ORI.value,
            parte=ParteFirmante.USB.value,
            estado=EstadoFirma.PENDIENTE.value,
        ),
        FirmaConvenio(
            convenio_id=convenio.id,
            orden=7,
            rol_firmante=RolFirmante.PARTE_SOLICITANTE.value,
            parte=ParteFirmante.SOLICITANTE.value,
            estado=EstadoFirma.PENDIENTE.value,
        ),
    ]
    db.add_all(firmas)
    db.commit()

    response = client.get(f"/api/convenios/{convenio.id}/revision-final")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == convenio.id
    assert data["revision_final_aprobada"] is True
    assert data["proceso_firmas_abierto"] is False
    assert len(data["firmas"]) == 2
    assert data["firmas"][0]["rol_firmante"] == "ADMINISTRADOR_ORI"
