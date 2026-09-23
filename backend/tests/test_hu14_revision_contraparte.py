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
    EstadoObservacion,
    EstadoRevisionPendiente,
    EstadoSolicitud,
    ResultadoRevisionPendiente,
    TipoSolicitante,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_pendiente import RevisionPendiente
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.usuario import Usuario
from backend.services.revision_contraparte import (
    ConvenioNoEncontrado,
    ObservacionesRequeridas,
    RevisionJuridicaNoAprobada,
    RevisionPendienteNoEncontrada,
    ServicioRevisionContraparte,
    UsuarioNoAutorizado,
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

    revision = db.scalar(
        select(RevisionPendiente).where(RevisionPendiente.historial_etapa_id == historial.id)
    )
    assert revision is not None
    assert revision.convenio_id == convenio.id
    assert revision.responsable_id == convenio.solicitud.solicitante_id
    assert revision.estado == EstadoRevisionPendiente.PENDIENTE.value
    assert revision.resultado is None
    assert revision.resuelta_en is None


# CA-02: impedir el envío sin aval jurídico.
def test_ca02_bloquea_envio_sin_aval_juridico(db, crear_convenio, crear_usuario) -> None:
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    convenio = crear_convenio(etapa_codigo="ELABORACION")

    with pytest.raises(RevisionJuridicaNoAprobada):
        ServicioRevisionContraparte(db).registrar_envio(convenio.id, gestor)

    db.refresh(convenio)
    assert convenio.etapa_actual_id == _etapa(db, "ELABORACION").id
    assert db.scalar(select(HistorialEtapa).where(HistorialEtapa.convenio_id == convenio.id)) is None
    assert db.scalar(select(RevisionPendiente).where(RevisionPendiente.convenio_id == convenio.id)) is None


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

    revisiones = db.scalars(
        select(RevisionPendiente)
        .where(RevisionPendiente.convenio_id == convenio.id)
        .order_by(RevisionPendiente.id)
    ).all()
    assert len(revisiones) == 2
    assert revisiones[0].historial_etapa_id == primer_envio.id
    assert revisiones[1].historial_etapa_id == segundo_envio.id


# CA-04: el Solicitante aprueba el convenio dentro de la plataforma.
def test_ca04_solicitante_aprueba_convenio(db, crear_convenio, crear_solicitud, crear_usuario) -> None:
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(solicitante)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO", solicitud=solicitud)
    envio = ServicioRevisionContraparte(db).registrar_envio(convenio.id, gestor)

    revision = ServicioRevisionContraparte(db).aprobar(convenio.id, solicitante)

    db.refresh(convenio)
    etapa_final = _etapa(db, "REVISION_FINAL")
    assert convenio.etapa_actual_id == etapa_final.id
    assert revision.historial_etapa_id == envio.id
    assert revision.estado == EstadoRevisionPendiente.RESUELTA.value
    assert revision.resultado == ResultadoRevisionPendiente.APROBADA.value
    assert revision.resuelta_en is not None

    nuevo_historial = db.scalar(
        select(HistorialEtapa)
        .where(HistorialEtapa.convenio_id == convenio.id)
        .order_by(HistorialEtapa.numero_ciclo.desc())
    )
    assert nuevo_historial.etapa_destino_id == etapa_final.id
    assert nuevo_historial.usuario_id == solicitante.id


def test_aprobar_rechaza_usuario_que_no_es_el_solicitante(
    db, crear_convenio, crear_solicitud, crear_usuario
) -> None:
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    otro_solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(solicitante)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO", solicitud=solicitud)
    ServicioRevisionContraparte(db).registrar_envio(convenio.id, gestor)

    with pytest.raises(UsuarioNoAutorizado):
        ServicioRevisionContraparte(db).aprobar(convenio.id, otro_solicitante)


def test_aprobar_sin_revision_pendiente(db, crear_convenio, crear_solicitud, crear_usuario) -> None:
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    solicitud = crear_solicitud(solicitante)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO", solicitud=solicitud)

    with pytest.raises(RevisionPendienteNoEncontrada):
        ServicioRevisionContraparte(db).aprobar(convenio.id, solicitante)


# CA-05: el Solicitante devuelve el convenio con observaciones.
def test_ca05_solicitante_devuelve_con_observaciones(
    db, crear_convenio, crear_solicitud, crear_usuario
) -> None:
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(solicitante)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO", solicitud=solicitud)
    envio = ServicioRevisionContraparte(db).registrar_envio(convenio.id, gestor)

    revision = ServicioRevisionContraparte(db).devolver_con_observaciones(
        convenio.id, ["Falta anexar el anexo financiero"], solicitante
    )

    db.refresh(convenio)
    assert convenio.etapa_actual_id == _etapa(db, "REVISION_CONTRAPARTE").id
    assert revision.estado == EstadoRevisionPendiente.RESUELTA.value
    assert revision.resultado == ResultadoRevisionPendiente.DEVUELTA.value

    observacion = db.scalar(
        select(ObservacionRevision).where(ObservacionRevision.historial_etapa_id == envio.id)
    )
    assert observacion is not None
    assert observacion.descripcion == "Falta anexar el anexo financiero"
    assert observacion.registrada_por_id == solicitante.id
    assert observacion.estado == EstadoObservacion.PENDIENTE.value


# CA-06: exigir al menos una observación al devolver.
def test_ca06_exige_observaciones_al_devolver(db, crear_convenio, crear_solicitud, crear_usuario) -> None:
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(solicitante)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO", solicitud=solicitud)
    ServicioRevisionContraparte(db).registrar_envio(convenio.id, gestor)

    with pytest.raises(ObservacionesRequeridas):
        ServicioRevisionContraparte(db).devolver_con_observaciones(convenio.id, [], solicitante)

    with pytest.raises(ObservacionesRequeridas):
        ServicioRevisionContraparte(db).devolver_con_observaciones(convenio.id, ["   "], solicitante)


# CA-09: trazabilidad — el ciclo es global y el ejecutor de cada acción queda registrado.
def test_ca09_numero_ciclo_es_global_por_convenio(db, crear_convenio, crear_solicitud, crear_usuario) -> None:
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(solicitante)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO", solicitud=solicitud)
    servicio = ServicioRevisionContraparte(db)

    envio = servicio.registrar_envio(convenio.id, gestor)
    assert envio.numero_ciclo == 1

    servicio.aprobar(convenio.id, solicitante)
    ultimo_historial = db.scalar(
        select(HistorialEtapa)
        .where(HistorialEtapa.convenio_id == convenio.id)
        .order_by(HistorialEtapa.numero_ciclo.desc())
    )
    assert ultimo_historial.numero_ciclo == 2


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


def test_endpoint_aprobacion_solicitante_exitoso(
    client, crear_convenio, crear_solicitud, crear_usuario, entrar_como
) -> None:
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(solicitante)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO", solicitud=solicitud)

    entrar_como(gestor)
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/envios").status_code == 201

    entrar_como(solicitante)
    respuesta = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/aprobacion")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["convenio_id"] == convenio.id
    assert cuerpo["resultado"] == "APROBADA"


def test_endpoint_aprobacion_gestor_ori_no_autorizado(
    client, crear_convenio, crear_solicitud, crear_usuario, entrar_como
) -> None:
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(solicitante)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO", solicitud=solicitud)

    entrar_como(gestor)
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/envios").status_code == 201

    respuesta = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/aprobacion")

    assert respuesta.status_code == 403


def test_endpoint_devolucion_solicitante_exitoso(
    client, crear_convenio, crear_solicitud, crear_usuario, entrar_como
) -> None:
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(solicitante)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO", solicitud=solicitud)

    entrar_como(gestor)
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/envios").status_code == 201

    entrar_como(solicitante)
    respuesta = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/devolucion",
        json={"observaciones": ["Corregir la cláusula tercera"]},
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["resultado"] == "DEVUELTA"


def test_endpoint_devolucion_sin_observaciones_422(
    client, crear_convenio, crear_solicitud, crear_usuario, entrar_como
) -> None:
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(solicitante)
    convenio = crear_convenio(etapa_codigo="REVISION_AVAL_JURIDICO", solicitud=solicitud)

    entrar_como(gestor)
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/envios").status_code == 201

    entrar_como(solicitante)
    respuesta = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/devolucion",
        json={"observaciones": []},
    )

    assert respuesta.status_code == 422


def test_endpoint_envio_convenio_inexistente_404(client, crear_usuario, entrar_como) -> None:
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)

    respuesta = client.post("/api/convenios/999999/revision-contraparte/envios")

    assert respuesta.status_code == 404
