from collections.abc import Callable
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.convenio import Convenio
from backend.models.enums import (
    AlcanceConvenio,
    EstadoConvenio,
    EstadoSolicitud,
    TipoSolicitante,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.usuario import Usuario
from backend.services.revision_contraparte import (
    ConvenioNoEncontrado,
    ConvenioNoEnRevisionContraparte,
    RevisionJuridicaNoAprobada,
    ServicioRevisionContraparte,
)


def _etapa(db: Session, codigo: str) -> Etapa:
    etapa = db.scalar(select(Etapa).where(Etapa.codigo == codigo))
    assert etapa is not None
    return etapa


@pytest.fixture
def crear_solicitud(db: Session, crear_usuario) -> Callable[..., SolicitudConvenio]:
    def _crear(solicitante: Usuario | None = None, **cambios) -> SolicitudConvenio:
        usuario = solicitante or crear_usuario()
        datos = {
            "consecutivo": f"SOL-{uuid4().hex}",
            "tipo_solicitante": TipoSolicitante.INTERNO.value,
            "solicitante_id": usuario.id,
            "objeto": "Solicitud de cooperación académica",
            "estado": EstadoSolicitud.APROBADA.value,
        }
        datos.update(cambios)
        solicitud = SolicitudConvenio(**datos)
        db.add(solicitud)
        db.commit()
        return solicitud

    return _crear


@pytest.fixture
def crear_convenio(db: Session, crear_solicitud, crear_usuario) -> Callable[..., Convenio]:
    def _crear(etapa_codigo: str = "REVISION_AVAL_JURIDICO", **cambios) -> Convenio:
        usuario = cambios.pop("creado_por", None) or crear_usuario()
        solicitud = cambios.pop("solicitud", None) or crear_solicitud()
        datos = {
            "solicitud_id": solicitud.id,
            "estado": EstadoConvenio.EN_TRAMITE.value,
            "objeto": "Cooperación internacional",
            "alcance": AlcanceConvenio.INSTITUCIONAL.value,
            "etapa_actual_id": _etapa(db, etapa_codigo).id,
            "creado_por_id": usuario.id,
        }
        datos.update(cambios)
        convenio = Convenio(**datos)
        db.add(convenio)
        db.commit()
        return convenio

    return _crear


def _autenticar(client, crear_usuario, entrar_como, rol: CodigoRol) -> Usuario:
    usuario = crear_usuario(rol, TipoUsuario.INTERNO)
    entrar_como(usuario)
    return usuario


# CA-01: registrar el envío a contraparte.
def test_ca01_registra_envio_a_contraparte(db, crear_convenio, crear_usuario) -> None:
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO")

    historial = ServicioRevisionContraparte(db).registrar_envio(convenio.id, gestor)

    db.refresh(convenio)
    etapa_contraparte = _etapa(db, "REVISION_CONTRAPARTE")
    assert convenio.etapa_actual_id == etapa_contraparte.id
    assert historial.convenio_id == convenio.id
    assert historial.etapa_destino_id == etapa_contraparte.id
    assert historial.etapa_origen_id == _etapa(db, "REVISION_AVAL_JURIDICO").id
    assert historial.usuario_id == gestor.id
    assert historial.numero_ciclo == 1
    assert historial.fecha_cambio is not None


# CA-02: impedir el envío sin aval jurídico.
def test_ca02_bloquea_envio_sin_aval_juridico(db, crear_convenio, crear_usuario) -> None:
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    convenio = crear_convenio(etapa_codigo="ELABORACION")

    with pytest.raises(RevisionJuridicaNoAprobada):
        ServicioRevisionContraparte(db).registrar_envio(convenio.id, gestor)

    db.refresh(convenio)
    assert convenio.etapa_actual_id == _etapa(db, "ELABORACION").id
    assert db.scalar(select(HistorialEtapa).where(HistorialEtapa.convenio_id == convenio.id)) is None


def test_ca02_bloquea_envio_convenio_ya_avanzado(db, crear_convenio, crear_usuario) -> None:
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    convenio = crear_convenio(etapa_codigo="REVISION_FINAL")

    with pytest.raises(RevisionJuridicaNoAprobada):
        ServicioRevisionContraparte(db).registrar_envio(convenio.id, gestor)


def test_registrar_envio_convenio_no_encontrado(db, crear_usuario) -> None:
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    with pytest.raises(ConvenioNoEncontrado):
        ServicioRevisionContraparte(db).registrar_envio(999999, gestor)


# CA-07: registrar un nuevo envío (reenvío) después de correcciones.
def test_ca07_reenvio_genera_nuevo_ciclo_sin_eliminar_historial(db, crear_convenio, crear_usuario) -> None:
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO")
    servicio = ServicioRevisionContraparte(db)

    primer_envio = servicio.registrar_envio(convenio.id, gestor)
    segundo_envio = servicio.registrar_envio(convenio.id, gestor)

    assert primer_envio.numero_ciclo == 1
    assert segundo_envio.numero_ciclo == 2
    assert segundo_envio.id != primer_envio.id

    historial = db.scalars(
        select(HistorialEtapa)
        .where(HistorialEtapa.convenio_id == convenio.id)
        .order_by(HistorialEtapa.numero_ciclo)
    ).all()
    assert [h.numero_ciclo for h in historial] == [1, 2]
    assert db.get(HistorialEtapa, primer_envio.id) is not None


# CA-03: registrar la aprobación de la contraparte.
def test_ca03_registra_aprobacion_contraparte(db, crear_convenio, crear_usuario) -> None:
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    convenio = crear_convenio(etapa_codigo="REVISION_CONTRAPARTE")

    historial = ServicioRevisionContraparte(db).registrar_aprobacion(convenio.id, gestor)

    db.refresh(convenio)
    etapa_final = _etapa(db, "REVISION_FINAL")
    assert convenio.etapa_actual_id == etapa_final.id
    assert historial.etapa_origen_id == _etapa(db, "REVISION_CONTRAPARTE").id
    assert historial.etapa_destino_id == etapa_final.id
    assert historial.usuario_id == gestor.id
    assert historial.fecha_cambio is not None


def test_ca03_bloquea_aprobacion_fuera_de_revision_contraparte(db, crear_convenio, crear_usuario) -> None:
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO")

    with pytest.raises(ConvenioNoEnRevisionContraparte):
        ServicioRevisionContraparte(db).registrar_aprobacion(convenio.id, gestor)


# CA-08: trazabilidad de envíos y aprobaciones.
def test_ca08_numero_ciclo_es_global_por_convenio(db, crear_convenio, crear_usuario) -> None:
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO")
    servicio = ServicioRevisionContraparte(db)

    envio = servicio.registrar_envio(convenio.id, gestor)
    assert envio.numero_ciclo == 1

    aprobacion = servicio.registrar_aprobacion(convenio.id, gestor)
    assert aprobacion.numero_ciclo == 2


# Endpoints HTTP.
def test_endpoint_envio_requiere_permiso(client, crear_convenio, crear_usuario, entrar_como) -> None:
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO")
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.SOLICITANTE_INTERNO)

    respuesta = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/envios")

    assert respuesta.status_code == 403


def test_endpoint_envio_gestor_ori_exitoso(client, crear_convenio, crear_usuario, entrar_como, db) -> None:
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO")
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)

    respuesta = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/envios")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["convenio_id"] == convenio.id
    assert cuerpo["numero_ciclo"] == 1


def test_endpoint_envio_bloqueado_devuelve_409(client, crear_convenio, crear_usuario, entrar_como) -> None:
    convenio = crear_convenio(etapa_codigo="ELABORACION")
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)

    respuesta = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/envios")

    assert respuesta.status_code == 409


def test_endpoint_aprobacion_gestor_ori_exitoso(client, crear_convenio, crear_usuario, entrar_como) -> None:
    convenio = crear_convenio(etapa_codigo="REVISION_CONTRAPARTE")
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)

    respuesta = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/aprobacion")

    assert respuesta.status_code == 201
    assert respuesta.json()["convenio_id"] == convenio.id


def test_endpoint_envio_convenio_inexistente_404(client, crear_usuario, entrar_como) -> None:
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)

    respuesta = client.post("/api/convenios/999999/revision-contraparte/envios")

    assert respuesta.status_code == 404
