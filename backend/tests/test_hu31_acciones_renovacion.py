from copy import deepcopy
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.decision_no_renovacion import DecisionNoRenovacion
from backend.models.documento import Documento
from backend.models.enums import (
    AccionAuditoria,
    ContextoVersionConvenio,
    EstadoConvenio,
    EstadoSeguimientoRenovacion,
    EstadoSolicitud,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services import renovaciones
from backend.services.convenios import ServicioConvenios
from backend.services.renovaciones import ServicioRenovaciones

FECHA_REFERENCIA = date(2026, 10, 7)
DOCUMENTO_VIGENTE = {
    "type": "doc",
    "content": [
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Cláusula diligenciada del convenio vigente"}
            ],
        }
    ],
}


@pytest.fixture(autouse=True)
def fecha_dominio_fija(monkeypatch):
    monkeypatch.setattr(renovaciones, "fecha_actual_dominio", lambda: FECHA_REFERENCIA)


@pytest.fixture
def origen(db, crear_usuario, crear_convenio, solicitante):
    autor = crear_usuario(CodigoRol.GESTOR_ORI)
    convenio = crear_convenio(
        autor,
        codigo=f"ORIGEN-{autor.id}",
        fecha_inicio=date(2025, 1, 1),
        fecha_vencimiento=FECHA_REFERENCIA + timedelta(days=30),
        implicacion_financiera="Recursos propios",
        duracion_meses=24,
    )
    convenio.solicitud.solicitante_id = solicitante.id
    convenio.solicitud.contacto_contraparte_nombre = "Contacto vigente"
    convenio.solicitud.observaciones = "Observación histórica que no debe copiarse"
    convenio.solicitud.observaciones_devolucion = "Devolución histórica"
    convenio.fecha_firma = date(2025, 1, 1)
    convenio.porcentaje_avance = 100
    ServicioConvenios(db)._crear_version(
        convenio,
        deepcopy(DOCUMENTO_VIGENTE),
        autor,
        ContextoVersionConvenio.FINALIZACION,
    )
    convenio.estado = EstadoConvenio.VIGENTE.value
    convenio.etapa_actual = db.scalar(
        select(Etapa).where(Etapa.codigo == "FIRMA_ARCHIVO_SEGUIMIENTO")
    )
    db.commit()
    return convenio


def url(convenio_id, accion="renovaciones"):
    return f"/api/convenios/{convenio_id}/{accion}"


def snapshot(convenio):
    return {
        col.name: deepcopy(getattr(convenio, col.name))
        for col in Convenio.__table__.columns
    }


def conteos(db):
    return {
        modelo.__tablename__: db.scalar(select(func.count()).select_from(modelo))
        for modelo in (
            SolicitudConvenio,
            Convenio,
            VersionConvenio,
            HistorialEtapa,
            DecisionNoRenovacion,
            Auditoria,
        )
    }


@pytest.mark.parametrize("accion", ["renovaciones", "no-renovar"])
@pytest.mark.parametrize("rol", [CodigoRol.GESTOR_ORI, CodigoRol.ADMINISTRADOR_ORI])
def test_roles_autorizados_pueden_ejecutar_acciones(
    client, crear_usuario, entrar_como, origen, rol, accion
):
    entrar_como(crear_usuario(rol))

    assert client.post(url(origen.id, accion)).status_code == 201


@pytest.mark.parametrize("rol", list(CodigoRol))
def test_permisos_renovacion_tardia(db, client, crear_usuario, entrar_como, origen, rol):
    origen.estado = EstadoConvenio.FINALIZADO.value
    db.commit()
    tipo = TipoUsuario.EXTERNO if rol == CodigoRol.SOLICITANTE_EXTERNO else TipoUsuario.INTERNO
    entrar_como(crear_usuario(rol, tipo))
    esperado = 201 if rol in {CodigoRol.GESTOR_ORI, CodigoRol.ADMINISTRADOR_ORI} else 403
    assert client.post(url(origen.id)).status_code == esperado


@pytest.mark.parametrize("accion", ["renovaciones", "no-renovar"])
@pytest.mark.parametrize(
    ("rol", "tipo"),
    [
        (CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_roles_sin_permiso_no_pueden_ejecutar_acciones(
    db, client, crear_usuario, entrar_como, origen, rol, tipo, accion
):
    entrar_como(crear_usuario(rol, tipo))
    antes = conteos(db)

    assert client.post(url(origen.id, accion)).status_code == 403
    assert conteos(db) == antes


@pytest.mark.parametrize("accion", ["renovaciones", "no-renovar"])
def test_no_autenticado_no_puede_ejecutar_acciones(client, origen, accion):
    assert client.post(url(origen.id, accion)).status_code == 401


@pytest.mark.parametrize("accion", ["renovaciones", "no-renovar"])
def test_convenio_inexistente_responde_404(client, gestor, accion):
    assert client.post(url(2_000_000_000, accion)).status_code == 404


@pytest.mark.parametrize(
    "estado",
    [EstadoConvenio.VIGENTE, EstadoConvenio.POR_VENCER, EstadoConvenio.VENCIDO, EstadoConvenio.FINALIZADO],
)
def test_estados_permitidos_inician_renovacion(db, client, gestor, origen, estado):
    origen.estado = estado.value
    if estado in {EstadoConvenio.VENCIDO, EstadoConvenio.FINALIZADO}:
        origen.fecha_vencimiento = FECHA_REFERENCIA - timedelta(days=10)
    db.commit()

    assert client.post(url(origen.id)).status_code == 201


@pytest.mark.parametrize(
    "estado",
    [
        EstadoConvenio.RENOVADO,
        EstadoConvenio.CANCELADO,
        EstadoConvenio.EN_TRAMITE,
    ],
)
def test_estados_no_permitidos_rechazan_renovacion(db, client, gestor, origen, estado):
    origen.estado = estado.value
    db.commit()
    antes = conteos(db)

    assert client.post(url(origen.id)).status_code == 409
    assert conteos(db) == antes


@pytest.mark.parametrize("estado", [EstadoConvenio.VIGENTE, EstadoConvenio.FINALIZADO])
def test_crea_solicitud_elaboracion_version_e_historial_propios(
    db, client, gestor, origen, monkeypatch, estado
):
    origen.estado = estado.value
    db.commit()
    antes = snapshot(origen)
    solicitud_original = origen.solicitud
    solicitante_id = solicitud_original.solicitante_id
    version_original = ServicioConvenios(db)._version_actual(origen)

    def plantilla_prohibida(*args):
        raise AssertionError("La renovación no debe reconstruirse desde una plantilla")

    monkeypatch.setattr(
        ServicioConvenios, "_plantilla_base_activa", plantilla_prohibida
    )
    respuesta = client.post(url(origen.id))

    assert respuesta.status_code == 201
    datos = respuesta.json()
    hijo = db.get(Convenio, datos["convenio_renovacion_id"])
    assert datos == {
        "convenio_origen_id": origen.id,
        "convenio_renovacion_id": hijo.id,
        "codigo": None,
        "numero_renovacion": 1,
        "estado": "EN_TRAMITE",
        "etapa": "ELABORACION",
    }
    assert hijo.id != origen.id
    assert hijo.solicitud_id != solicitud_original.id
    assert hijo.solicitud.solicitante_id == solicitante_id
    assert hijo.solicitud.estado == EstadoSolicitud.APROBADA.value
    assert hijo.solicitud.consecutivo == f"SOL-{hijo.solicitud_id:08d}"
    assert hijo.solicitud.fecha_radicacion is None
    assert hijo.solicitud.contacto_contraparte_nombre == "Contacto vigente"
    assert hijo.solicitud.observaciones is None
    assert hijo.solicitud.observaciones_devolucion is None
    assert hijo.objeto == origen.objeto
    assert hijo.alcance == origen.alcance
    assert hijo.implicacion_financiera == origen.implicacion_financiera
    assert hijo.fecha_inicio is None
    assert hijo.fecha_vencimiento is None
    assert hijo.fecha_firma is None
    assert hijo.porcentaje_avance is None
    version = ServicioConvenios(db)._version_actual(hijo)
    assert version.id != version_original.id
    assert version.convenio_id == hijo.id
    assert version.numero == hijo.version_actual == 1
    assert version.contenido == DOCUMENTO_VIGENTE
    assert version.contenido is not version_original.contenido
    assert version.snapshot_metadata["convenio_origen_id"] == origen.id
    assert version.autor_id == gestor.id
    assert version.etapa.codigo == "ELABORACION"
    assert version.contexto == ContextoVersionConvenio.INICIALIZACION.value
    assert len(hijo.versiones) == 1
    assert len(hijo.historial_etapas) == 1
    assert hijo.historial_etapas[0].etapa_origen_id is None
    assert hijo.historial_etapas[0].etapa_destino.codigo == "ELABORACION"
    for modelo in (
        RevisionConvenio,
        ObservacionRevision,
        ProcesoFirmasConvenio,
        Documento,
    ):
        assert (
            db.scalar(
                select(func.count())
                .select_from(modelo)
                .where(modelo.convenio_id == hijo.id)
            )
            == 0
        )
    db.refresh(origen)
    assert snapshot(origen) == antes


def test_no_renovar_registra_decision_y_auditoria_sin_cambiar_padre(
    db, client, gestor, origen
):
    antes = snapshot(origen)
    cantidades = conteos(db)

    respuesta = client.post(url(origen.id, "no-renovar"))

    assert respuesta.status_code == 201
    datos = respuesta.json()
    decision = db.scalar(
        select(DecisionNoRenovacion).where(
            DecisionNoRenovacion.convenio_id == origen.id
        )
    )
    assert datos["convenio_id"] == origen.id
    assert datos["fecha_vencimiento_origen"] == origen.fecha_vencimiento.isoformat()
    assert datos["decidida_por_id"] == gestor.id
    assert datos["decidida_en"]
    assert datos["estado_seguimiento"] == "NO_SE_RENOVARA"
    assert decision.decidida_en.tzinfo is not None
    auditoria = db.scalar(
        select(Auditoria).where(
            Auditoria.entidad == "decision_no_renovacion",
            Auditoria.registro_id == decision.id,
        )
    )
    assert auditoria.usuario_id == gestor.id
    assert auditoria.accion == AccionAuditoria.INSERT.value
    assert auditoria.campo is None
    db.refresh(origen)
    assert snapshot(origen) == antes
    despues = conteos(db)
    assert despues["decision_no_renovacion"] == cantidades["decision_no_renovacion"] + 1
    assert despues["auditoria"] == cantidades["auditoria"] + 1
    for tabla in (
        "solicitud_convenio",
        "convenio",
        "version_convenio",
        "historial_etapa",
    ):
        assert despues[tabla] == cantidades[tabla]
    assert origen.id not in {
        item["convenio_id"]
        for item in client.get(
            "/api/convenios/renovaciones", params={"estado": "PENDIENTE_DE_DECISION"}
        ).json()
    }


@pytest.mark.parametrize("finalizado", [False, True])
def test_no_renovar_no_bloquea_iniciar_y_conserva_decision(db, client, gestor, origen, finalizado):
    assert client.post(url(origen.id, "no-renovar")).status_code == 201
    decision = db.scalar(
        select(DecisionNoRenovacion).where(
            DecisionNoRenovacion.convenio_id == origen.id
        )
    )
    historica = (
        decision.id,
        decision.fecha_vencimiento_origen,
        decision.decidida_por_id,
        decision.decidida_en,
    )

    if finalizado:
        origen.estado = EstadoConvenio.FINALIZADO.value
        db.commit()
    assert client.post(url(origen.id)).status_code == 201

    db.refresh(decision)
    assert (
        decision.id,
        decision.fecha_vencimiento_origen,
        decision.decidida_por_id,
        decision.decidida_en,
    ) == historica
    assert (
        renovaciones.calcular_estado_seguimiento(db, origen)
        == EstadoSeguimientoRenovacion.RENOVACION_INICIADA
    )


def test_hijo_activo_bloquea_ambas_acciones(db, client, gestor, origen):
    assert client.post(url(origen.id)).status_code == 201
    antes = conteos(db)

    assert client.post(url(origen.id)).status_code == 409
    assert client.post(url(origen.id, "no-renovar")).status_code == 409
    assert conteos(db) == antes


def test_intento_cancelado_no_consume_numero(db, client, gestor, origen):
    origen.numero_renovacion = 2
    db.commit()
    primero = client.post(url(origen.id)).json()
    hijo = db.get(Convenio, primero["convenio_renovacion_id"])
    hijo.estado = EstadoConvenio.CANCELADO.value
    db.commit()
    antes = snapshot(origen)

    respuesta = client.post(url(origen.id))

    assert respuesta.status_code == 201
    assert primero["numero_renovacion"] == respuesta.json()["numero_renovacion"] == 3
    assert (
        primero["convenio_renovacion_id"] != respuesta.json()["convenio_renovacion_id"]
    )
    assert respuesta.json()["convenio_origen_id"] == origen.id
    db.refresh(origen)
    assert snapshot(origen) == antes


def test_duplicado_no_renovar_responde_409(db, client, gestor, origen):
    assert client.post(url(origen.id, "no-renovar")).status_code == 201
    antes = conteos(db)

    assert client.post(url(origen.id, "no-renovar")).status_code == 409
    assert conteos(db) == antes


@pytest.mark.parametrize(
    ("dias", "estado"),
    [
        (121, EstadoConvenio.VIGENTE),
        (-1, EstadoConvenio.VIGENTE),
        (-1, EstadoConvenio.VENCIDO),
        (30, EstadoConvenio.EN_TRAMITE),
        (None, EstadoConvenio.VIGENTE),
    ],
)
def test_no_renovar_exige_pendiente_real(db, client, gestor, origen, dias, estado):
    origen.fecha_vencimiento = (
        FECHA_REFERENCIA + timedelta(days=dias) if dias is not None else None
    )
    origen.estado = estado.value
    db.commit()
    antes = conteos(db)

    assert client.post(url(origen.id, "no-renovar")).status_code == 409
    assert conteos(db) == antes


def test_error_intermedio_revierte_solicitud_convenio_version_e_historial(
    db, gestor, origen, monkeypatch
):
    antes = conteos(db)
    padre = snapshot(origen)
    crear_version = ServicioConvenios._crear_version

    def crear_y_fallar(*args, **kwargs):
        crear_version(*args, **kwargs)
        raise RuntimeError("Fallo después de crear la versión")

    monkeypatch.setattr(ServicioConvenios, "_crear_version", crear_y_fallar)
    with pytest.raises(RuntimeError, match="Fallo después"):
        ServicioRenovaciones(db).iniciar_renovacion(origen.id, gestor)

    assert conteos(db) == antes
    db.refresh(origen)
    assert snapshot(origen) == padre


def test_error_al_auditar_revierte_decision(db, gestor, origen, monkeypatch):
    antes = conteos(db)

    def commit_fallido():
        raise SQLAlchemyError("Fallo al persistir auditoría")

    monkeypatch.setattr(db, "commit", commit_fallido)
    with pytest.raises(SQLAlchemyError):
        ServicioRenovaciones(db).registrar_no_renovacion(origen.id, gestor)

    assert conteos(db) == antes


@pytest.mark.parametrize("estado", [EstadoConvenio.VIGENTE, EstadoConvenio.FINALIZADO])
def test_version_vigente_ausente_rechaza_sin_dejar_parciales(
    db, client, gestor, origen, estado
):
    origen.estado = estado.value
    origen.version_actual = 999
    db.commit()
    antes = conteos(db)

    assert client.post(url(origen.id)).status_code == 409
    assert conteos(db) == antes


def test_finalizado_sin_fecha_rechaza_renovacion(db, client, gestor, origen):
    origen.estado = EstadoConvenio.FINALIZADO.value
    origen.fecha_vencimiento = None
    db.commit()
    antes = conteos(db)
    assert client.post(url(origen.id)).status_code == 409
    assert conteos(db) == antes
