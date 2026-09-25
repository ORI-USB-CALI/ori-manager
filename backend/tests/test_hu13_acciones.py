"""HU-13: aprobar, devolver y autorización."""
from sqlalchemy import select

from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.services.convenios import ServicioConvenios

# gestor, revisor y convenio_listo viven en conftest.py.


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


def test_pantalla_de_revision_tras_aprobar_no_revienta(
    client, db, gestor, revisor, convenio_listo, entrar_como
):
    """CA-01/CA-08: aprobar() no mueve la etapa (queda para otra HU), así que
    la pantalla de revisión puede volver a consultarse sobre un convenio ya
    resuelto — debe responder con un error manejado, no un 500."""
    revision = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    assert (
        client.post(
            f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/aprobar"
        ).status_code
        == 200
    )

    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revision")
    assert respuesta.status_code == 409


def test_historial_conserva_resultado_y_version_tras_aprobar_via_api(
    client, db, gestor, revisor, convenio_listo, entrar_como
):
    """CA-07: el resultado, el responsable y la versión revisada quedan
    trazables vía API (no solo en la sesión de base de datos)."""
    revision = _abrir(db, convenio_listo, gestor)
    snapshot_objeto = revision.snapshot_datos["objeto"]
    entrar_como(revisor)
    ruta = f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/aprobar"
    assert client.post(ruta).status_code == 200

    cuerpo = client.get(f"/api/convenios/{convenio_listo.id}/revisiones").json()
    revisada = next(r for r in cuerpo["revisiones"] if r["id"] == revision.id)
    assert revisada["resultado"] == "APROBADA"
    assert revisada["resuelta_por"]["id"] == revisor.id
    assert revisada["resuelta_en"] is not None
    assert revisada["snapshot_datos"]["objeto"] == snapshot_objeto


def test_historial_conserva_observaciones_y_devolucion_via_api(
    client, db, gestor, revisor, convenio_listo, entrar_como
):
    """CA-04/CA-07/CA-08: la devolución, sus observaciones y que el convenio
    no avanzó a contraparte quedan trazables vía API."""
    revision = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    ruta = f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/devolver"
    assert client.post(ruta, json={"observaciones": ["Corregir objeto"]}).status_code == 200

    cuerpo = client.get(f"/api/convenios/{convenio_listo.id}/revisiones").json()
    revisada = next(r for r in cuerpo["revisiones"] if r["id"] == revision.id)
    assert revisada["resultado"] == "DEVUELTA"
    assert revisada["resuelta_por"]["id"] == revisor.id
    assert [o["descripcion"] for o in revisada["observaciones"]] == ["Corregir objeto"]
    assert revisada["observaciones"][0]["estado"] == "PENDIENTE"
    assert cuerpo["cambios_etapa"][-1]["etapa_destino"]["codigo"] == "ELABORACION"


def test_atencion_exige_editor_respuesta_y_estado_pendiente(
    client, db, gestor, revisor, convenio_listo, entrar_como
):
    revision = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    devolucion = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/devolver",
        json={"observaciones": ["Corregir el objeto"]},
    )
    observacion_id = devolucion.json()["observaciones"][0]["id"]
    ruta = (
        f"/api/convenios/{convenio_listo.id}/observaciones/"
        f"{observacion_id}/atender"
    )

    assert client.patch(ruta, json={"respuesta": "Corregido"}).status_code == 403
    entrar_como(gestor)
    assert client.patch(ruta, json={"respuesta": "   "}).status_code == 422
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    ).status_code == 409

    respuesta = client.patch(
        ruta, json={"respuesta": "  Se corrigió el objeto solicitado.  "}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "ATENDIDA"
    assert cuerpo["respuesta"] == "Se corrigió el objeto solicitado."
    assert cuerpo["atendida_por"]["id"] == gestor.id
    assert cuerpo["fecha_atencion"] is not None
    assert client.patch(ruta, json={"respuesta": "Otra respuesta"}).status_code == 409


def test_ciclo_real_devolucion_correccion_atencion_reenvio_y_aprobacion(
    client, db, gestor, revisor, convenio_listo, entrar_como
):
    objeto_inicial = convenio_listo.objeto
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    ).status_code == 200
    primera = db.scalar(
        select(RevisionConvenio)
        .where(RevisionConvenio.convenio_id == convenio_listo.id)
        .order_by(RevisionConvenio.id)
    )
    snapshot_primera = dict(primera.snapshot_datos)

    entrar_como(revisor)
    devolucion = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{primera.id}/devolver",
        json={"observaciones": ["Ajustar el objeto del convenio"]},
    )
    assert devolucion.status_code == 200
    observacion_id = devolucion.json()["observaciones"][0]["id"]

    entrar_como(gestor)
    assert client.patch(
        f"/api/convenios/{convenio_listo.id}",
        json={"objeto": "Objeto corregido del convenio"},
    ).status_code == 200
    assert client.patch(
        f"/api/convenios/{convenio_listo.id}/observaciones/"
        f"{observacion_id}/atender",
        json={"respuesta": "Se ajustó el objeto conforme a la observación."},
    ).status_code == 200
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    ).status_code == 200

    revisiones = list(
        db.scalars(
            select(RevisionConvenio)
            .where(RevisionConvenio.convenio_id == convenio_listo.id)
            .order_by(RevisionConvenio.id)
        )
    )
    assert len(revisiones) == 2
    segunda = revisiones[1]
    assert snapshot_primera["objeto"] == objeto_inicial
    assert primera.snapshot_datos["objeto"] == objeto_inicial
    assert segunda.snapshot_datos["objeto"] == "Objeto corregido del convenio"
    assert primera.snapshot_datos != segunda.snapshot_datos

    entrar_como(revisor)
    aprobacion = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{segunda.id}/aprobar"
    )
    assert aprobacion.status_code == 200
    historial = client.get(
        f"/api/convenios/{convenio_listo.id}/revisiones"
    ).json()
    primera_api, segunda_api = historial["revisiones"]
    observacion = primera_api["observaciones"][0]
    assert primera_api["estado"] == "RESUELTA"
    assert primera_api["resultado"] == "DEVUELTA"
    assert observacion["estado"] == "ATENDIDA"
    assert observacion["respuesta"]
    assert observacion["atendida_por"]["id"] == gestor.id
    assert observacion["fecha_atencion"] is not None
    assert segunda_api["estado"] == "RESUELTA"
    assert segunda_api["resultado"] == "APROBADA"
    assert segunda_api["resuelta_por"]["id"] == revisor.id
    assert segunda_api["resuelta_en"] is not None
    db.refresh(convenio_listo)
    assert convenio_listo.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"
