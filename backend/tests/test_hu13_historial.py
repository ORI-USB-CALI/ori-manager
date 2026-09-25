"""HU-13: historial y trazabilidad de rondas reales de revisión."""

from sqlalchemy import select

from backend.models.revision_convenio import RevisionConvenio

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
    client, db, gestor, revisor, entrar_como, convenio_listo
) -> None:
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")
    primera = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id
        )
    )
    entrar_como(revisor)
    devolucion = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{primera.id}/devolver",
        json={"observaciones": ["Falta anexar el certificado"]},
    )
    observacion_id = devolucion.json()["observaciones"][0]["id"]
    entrar_como(gestor)
    assert client.patch(
        f"/api/convenios/{convenio_listo.id}/observaciones/"
        f"{observacion_id}/atender",
        json={"respuesta": "Se anexó el certificado solicitado"},
    ).status_code == 200
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
    assert (
        primera["observaciones"][0]["respuesta"]
        == "Se anexó el certificado solicitado"
    )

    assert segunda_revision["estado"] == "PENDIENTE"
    assert segunda_revision["resultado"] is None
    assert segunda_revision["observaciones"] == []

    # Elaboración -> Jurídica -> Elaboración -> Jurídica otra vez.
    assert len(cuerpo["cambios_etapa"]) == 4


def test_convenio_inexistente_devuelve_404(client, gestor) -> None:
    respuesta = client.get("/api/convenios/999999999/revisiones")

    assert respuesta.status_code == 404


def test_usuario_sin_permiso_no_puede_consultar_el_historial(
    client, solicitante, entrar_como, convenio_listo
) -> None:
    entrar_como(solicitante)

    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revisiones")

    assert respuesta.status_code == 403
