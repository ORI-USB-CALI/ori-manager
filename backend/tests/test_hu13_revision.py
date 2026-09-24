"""HU-13 — Realizar revisión y aval jurídico del convenio.

Parte cubierta aquí: la pantalla principal de revisión, GET
/convenios/{id}/revision (CA-01, CA-02). No cubre aprobar()/devolver()
(Persona 2) ni el historial/trazabilidad completos (CA-06/CA-07, ver
test_hu13_historial.py).
"""

from sqlalchemy import select
from test_hu13_historial import _simular_devolucion

from backend.models.revision_convenio import RevisionConvenio

# gestor, revisor, solicitante, crear_convenio y convenio_listo viven en
# conftest.py (compartidas con test_hu13_historial.py y test_hu13_acciones.py).

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
