"""HU-13 — Realizar revisión y aval jurídico del convenio.

Parte cubierta aquí: la pantalla principal de revisión, GET
/convenios/{id}/revision (CA-01, CA-02). No cubre aprobar()/devolver()
(Persona 2) ni el historial/trazabilidad completos (CA-06/CA-07, ver
test_hu13_historial.py).
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.convenio import Convenio
from backend.models.enums import (
    AlcanceConvenio,
    EstadoObservacionRevision,
    EstadoRevisionConvenio,
    EstadoSolicitud,
    OrigenObservacionRevision,
    ResultadoRevisionConvenio,
    TipoSolicitante,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.schemas.convenio import ConvenioCrear
from backend.services.convenios import ServicioConvenios


@pytest.fixture
def gestor(client, crear_usuario, entrar_como) -> Usuario:
    usuario = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    entrar_como(usuario)
    return usuario


@pytest.fixture
def revisor(crear_usuario) -> Usuario:
    return crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)


@pytest.fixture
def solicitante(crear_usuario) -> Usuario:
    return crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)


@pytest.fixture
def crear_convenio(db: Session) -> Callable[..., Convenio]:
    """Crea el convenio mediante el contrato canónico de HU-06 (mismo patrón
    que test_hu13_historial.py)."""

    def _crear(autor: Usuario, **cambios) -> Convenio:
        solicitud = SolicitudConvenio(
            consecutivo=f"SOL-{uuid4().hex}",
            tipo_solicitante=TipoSolicitante.INTERNO.value,
            solicitante_id=autor.id,
            objeto="Objeto solicitado originalmente",
            justificacion="Fortalecer la movilidad académica",
            vigencia_estimada="24 meses",
            estado=EstadoSolicitud.APROBADA.value,
            nombre_aliado_propuesto="Universidad Contraparte",
            correo_aliado_propuesto="convenios@contraparte.example",
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


@pytest.fixture
def convenio_listo(db: Session, gestor, crear_convenio) -> Convenio:
    """Convenio con todo lo requerido para entregarlo a Jurídica (igual que
    HU-12/HU-13 historial)."""
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    return crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Sin costo para la Universidad",
        duracion_meses=24,
        fecha_inicio=date(2026, 1, 1),
        fecha_vencimiento=date(2028, 1, 1),
    )


def _simular_devolucion(
    db: Session, convenio: Convenio, revisor: Usuario, gestor: Usuario
) -> None:
    """Mismo helper que test_hu13_historial.py: deja el estado que dejaría
    devolver() de HU-13 (Persona 2), sin depender de esa implementación."""
    revision_pendiente = db.scalar(
        select(RevisionConvenio)
        .where(RevisionConvenio.convenio_id == convenio.id)
        .order_by(RevisionConvenio.id.desc())
    )
    observacion = ObservacionRevision(
        convenio_id=convenio.id,
        historial_etapa_id=revision_pendiente.historial_etapa_id,
        revision_convenio_id=revision_pendiente.id,
        origen=OrigenObservacionRevision.REVISOR_ORI.value,
        registrada_por_id=revisor.id,
        responsable_id=gestor.id,
        descripcion="Falta anexar el certificado de representación legal",
        respuesta="Se anexó el certificado solicitado",
        atendida_por_id=gestor.id,
        fecha_atencion=datetime.now(UTC),
        estado=EstadoObservacionRevision.ATENDIDA.value,
    )
    db.add(observacion)
    revision_pendiente.estado = EstadoRevisionConvenio.RESUELTA.value
    revision_pendiente.resultado = ResultadoRevisionConvenio.DEVUELTA.value
    revision_pendiente.resuelta_por_id = revisor.id
    revision_pendiente.resuelta_en = datetime.now(UTC)

    elaboracion = db.scalar(select(Etapa).where(Etapa.codigo == "ELABORACION"))
    db.add(
        HistorialEtapa(
            convenio_id=convenio.id,
            etapa_origen_id=convenio.etapa_actual_id,
            etapa_destino_id=elaboracion.id,
            usuario_id=revisor.id,
            responsable_id=gestor.id,
            observacion="Devuelto con observaciones",
        )
    )
    convenio.etapa_actual_id = elaboracion.id
    db.commit()


# ---- CA-01/CA-02: pantalla principal de revisión -------------------------


def test_usuario_sin_permiso_no_puede_acceder_a_la_revision(
    client, solicitante, entrar_como, convenio_listo
) -> None:
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")
    entrar_como(solicitante)

    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revision")

    assert respuesta.status_code == 403


def test_convenio_inexistente_devuelve_404(client, revisor, entrar_como) -> None:
    entrar_como(revisor)

    respuesta = client.get("/api/convenios/999999999/revision")

    assert respuesta.status_code == 404


def test_convenio_que_no_esta_en_revision_juridica_devuelve_409(
    client, revisor, entrar_como, convenio_listo
) -> None:
    """El convenio sigue en Elaboración: nunca se finalizó."""
    entrar_como(revisor)

    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revision")

    assert respuesta.status_code == 409


def test_revisor_accede_al_convenio_preparado_con_documentos_y_version(
    client, revisor, entrar_como, convenio_listo
) -> None:
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")
    entrar_como(revisor)

    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revision")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()

    # CA-01: información del proyecto de convenio.
    assert cuerpo["convenio"]["id"] == convenio_listo.id
    assert cuerpo["convenio"]["objeto"] == convenio_listo.objeto
    assert cuerpo["convenio"]["etapa_actual"]["codigo"] == "REVISION_AVAL_JURIDICO"

    # CA-01: documentos asociados consultables (lista presente, aunque vacía
    # en este escenario porque HU-13 no depende de HU-09/carga documental).
    assert cuerpo["documentos"] == []

    # CA-01: identificar la versión objeto de revisión.
    assert cuerpo["revision_pendiente"]["tipo"] == "JURIDICA"
    assert cuerpo["revision_pendiente"]["estado"] == "PENDIENTE"
    assert cuerpo["revision_pendiente"]["resultado"] is None
    assert (
        cuerpo["revision_pendiente"]["snapshot_datos"]["objeto"]
        == convenio_listo.objeto
    )
    assert cuerpo["revision_pendiente"]["id"] is not None


def test_segunda_ronda_muestra_solo_la_revision_pendiente_vigente(
    client, db, gestor, revisor, entrar_como, convenio_listo
) -> None:
    """CA-06: tras devolución y corrección, la pantalla de revisión debe
    mostrar la nueva ronda pendiente, no la ya resuelta."""
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")
    db.refresh(convenio_listo)
    primera_revision_id = db.scalar(
        select(RevisionConvenio.id)
        .where(RevisionConvenio.convenio_id == convenio_listo.id)
        .order_by(RevisionConvenio.id.desc())
    )

    _simular_devolucion(db, convenio_listo, revisor, gestor)

    segunda = client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")
    assert segunda.status_code == 200

    entrar_como(revisor)
    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revision")

    assert respuesta.status_code == 200
    revision_pendiente = respuesta.json()["revision_pendiente"]
    assert revision_pendiente["id"] != primera_revision_id
    assert revision_pendiente["estado"] == "PENDIENTE"
    assert revision_pendiente["resultado"] is None
