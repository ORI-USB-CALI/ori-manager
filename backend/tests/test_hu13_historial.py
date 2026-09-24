"""HU-13 — Realizar revisión y aval jurídico del convenio.

Parte cubierta aquí: historial y trazabilidad (CA-06, CA-07), expuestos en
GET /convenios/{id}/revisiones. No cubre aprobar()/devolver() (Persona 2) ni
la pantalla principal de revisión (Persona 3): ese endpoint no existe todavía
en este archivo, así que el "ciclo anterior" de las pruebas de CA-06 se arma
a mano (ver `_simular_devolucion`), sin depender de código que aún no existe.
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
    que test_hu12_elaboracion.py)."""

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
    HU-12)."""
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    return crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Sin costo para la Universidad",
        duracion_meses=24,
        fecha_inicio=date(2026, 1, 1),
        fecha_vencimiento=date(2028, 1, 1),
    )


def _simular_devolucion(db: Session, convenio: Convenio, revisor: Usuario, gestor: Usuario) -> None:
    """Deja el mismo estado que dejaría ServicioConvenios.devolver() de HU-13
    (Persona 2), sin depender de esa implementación: resuelve la ronda de
    revisión pendiente como DEVUELTA con una observación atendida, y regresa
    el convenio a Elaboración. Solo para preparar el escenario de un
    segundo ciclo en las pruebas de CA-06.
    """
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


# ---- CA-06/CA-07: historial y trazabilidad ------------------------------


def test_convenio_en_elaboracion_no_tiene_revisiones_pero_si_ingreso_a_etapa(
    client, convenio_listo
) -> None:
    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revisiones")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["revisiones"] == []
    assert len(cuerpo["cambios_etapa"]) == 1
    assert cuerpo["cambios_etapa"][0]["etapa_destino"]["codigo"] == "ELABORACION"
    assert cuerpo["cambios_etapa"][0]["etapa_origen"] is None


def test_finalizar_elaboracion_deja_una_revision_juridica_pendiente(
    client, convenio_listo
) -> None:
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")

    cuerpo = client.get(f"/api/convenios/{convenio_listo.id}/revisiones").json()

    assert len(cuerpo["revisiones"]) == 1
    revision = cuerpo["revisiones"][0]
    assert revision["tipo"] == "JURIDICA"
    assert revision["estado"] == "PENDIENTE"
    assert revision["resultado"] is None
    assert revision["resuelta_en"] is None
    assert revision["observaciones"] == []
    assert revision["snapshot_datos"]["objeto"] == convenio_listo.objeto

    assert len(cuerpo["cambios_etapa"]) == 2
    assert cuerpo["cambios_etapa"][0]["etapa_destino"]["codigo"] == "ELABORACION"
    assert (
        cuerpo["cambios_etapa"][1]["etapa_destino"]["codigo"]
        == "REVISION_AVAL_JURIDICO"
    )
    assert cuerpo["cambios_etapa"][1]["etapa_origen"]["codigo"] == "ELABORACION"


def test_trazabilidad_registra_usuario_y_fecha_del_cambio_de_etapa(
    client, gestor, convenio_listo
) -> None:
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")

    cuerpo = client.get(f"/api/convenios/{convenio_listo.id}/revisiones").json()

    cambio = cuerpo["cambios_etapa"][1]
    assert cambio["usuario"]["id"] == gestor.id
    assert cambio["fecha_cambio"] is not None


def test_ca06_historial_conserva_ciclos_de_revision_anteriores(
    client, db, gestor, revisor, convenio_listo
) -> None:
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")
    db.refresh(convenio_listo)

    _simular_devolucion(db, convenio_listo, revisor, gestor)

    # Corregido y reenviado: reutiliza el mismo endpoint real de HU-12.
    segunda = client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    )
    assert segunda.status_code == 200

    cuerpo = client.get(f"/api/convenios/{convenio_listo.id}/revisiones").json()

    assert len(cuerpo["revisiones"]) == 2

    primera, segunda_revision = cuerpo["revisiones"]
    assert primera["estado"] == "RESUELTA"
    assert primera["resultado"] == "DEVUELTA"
    assert len(primera["observaciones"]) == 1
    assert primera["observaciones"][0]["estado"] == "ATENDIDA"
    assert primera["observaciones"][0]["respuesta"] == "Se anexó el certificado solicitado"

    assert segunda_revision["estado"] == "PENDIENTE"
    assert segunda_revision["resultado"] is None
    assert segunda_revision["observaciones"] == []

    # Elaboración -> Jurídica -> Elaboración -> Jurídica otra vez.
    assert len(cuerpo["cambios_etapa"]) == 4


def test_convenio_inexistente_devuelve_404(client) -> None:
    respuesta = client.get("/api/convenios/999999999/revisiones")

    assert respuesta.status_code == 404


def test_usuario_sin_permiso_no_puede_consultar_el_historial(
    client, solicitante, entrar_como, convenio_listo
) -> None:
    entrar_como(solicitante)

    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revisiones")

    assert respuesta.status_code == 403
