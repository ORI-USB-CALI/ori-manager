"""HU-13: aprobar, devolver y autorización."""
from sqlalchemy import select
from backend.models.revision_convenio import RevisionConvenio
from backend.models.observacion_revision import ObservacionRevision
from backend.models.historial_etapa import HistorialEtapa
from backend.services.convenios import ServicioConvenios
from test_hu13_historial import convenio_listo, crear_convenio, gestor, revisor  # noqa: F401


def _abrir(db, convenio, gestor):
    ServicioConvenios(db).finalizar_elaboracion(convenio.id, gestor)
    return db.scalar(select(RevisionConvenio).where(RevisionConvenio.convenio_id == convenio.id))


def test_aprobar_no_mueve_etapa_y_no_admite_repeticion(client, db, gestor, revisor, convenio_listo, entrar_como):
    revision = _abrir(db, convenio_listo, gestor)
    etapa = convenio_listo.etapa_actual_id
    entrar_como(revisor)
    ruta = f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/aprobar"
    respuesta = client.post(ruta)
    assert respuesta.status_code == 200
    db.refresh(revision)
    db.refresh(convenio_listo)
    assert revision.resultado == "APROBADA" and revision.estado == "RESUELTA"
    assert revision.resuelta_por_id == revisor.id and revision.resuelta_en is not None
    assert convenio_listo.etapa_actual_id == etapa
    assert client.post(ruta).status_code == 409
    db.refresh(revision)
    assert revision.resultado == "APROBADA"


def test_devolver_exige_observaciones_y_registra_retorno(client, db, gestor, revisor, convenio_listo, entrar_como):
    revision = _abrir(db, convenio_listo, gestor)
    juridica = convenio_listo.etapa_actual_id
    entrar_como(revisor)
    ruta = f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/devolver"
    assert client.post(ruta, json={"observaciones": []}).status_code == 422
    assert client.post(ruta, json={"observaciones": ["   "]}).status_code == 422
    assert client.post(ruta, json={"observaciones": ["Corregir objeto", "Revisar plazo"]}).status_code == 200
    db.refresh(convenio_listo)
    db.refresh(revision)
    assert convenio_listo.etapa_actual.codigo == "ELABORACION"
    assert revision.resultado == "DEVUELTA" and revision.estado == "RESUELTA"
    assert revision.resuelta_por_id == revisor.id
    observaciones = list(db.scalars(select(ObservacionRevision).where(ObservacionRevision.revision_convenio_id == revision.id)))
    assert [o.descripcion for o in observaciones] == ["Corregir objeto", "Revisar plazo"]
    historial = db.get(HistorialEtapa, observaciones[0].historial_etapa_id)
    assert all(o.historial_etapa_id == historial.id for o in observaciones)
    assert historial.etapa_origen_id == juridica
    assert historial.etapa_destino_id == convenio_listo.etapa_actual_id
    assert client.post(ruta, json={"observaciones": ["Otra"]}).status_code == 409


def test_revisor_no_edita_y_gestor_no_aprueba(client, db, gestor, revisor, convenio_listo, entrar_como):
    revision = _abrir(db, convenio_listo, gestor)
    ruta = f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/aprobar"
    assert client.post(ruta).status_code == 403
    entrar_como(revisor)
    assert client.patch(f"/api/convenios/{convenio_listo.id}", json={"objeto": "X"}).status_code == 403
    assert client.post(ruta).status_code == 200
