from copy import deepcopy

import pytest
from sqlalchemy import select

from backend.models.auditoria import Auditoria
from backend.models.borrador_convenio import BorradorConvenio
from backend.models.convenio import Convenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.convenios import ServicioConvenios


def _snapshot(db):
    return {
        m.__tablename__: deepcopy(
            list(
                db.execute(select(m.__table__).order_by(*m.__table__.primary_key)).all()
            )
        )
        for m in (
            Convenio,
            BorradorConvenio,
            VersionConvenio,
            RevisionConvenio,
            HistorialEtapa,
            Auditoria,
            SolicitudConvenio,
        )
    }


@pytest.mark.parametrize("fuente", ["borrador", "formulario", "historica"])
@pytest.mark.parametrize("agregado", [False, True])
def test_rechaza_precarga_antes_de_versionar_sin_efectos(
    client,
    db,
    gestor,
    crear_convenio,
    convenio_listo,
    formalizar_version,
    fuente,
    agregado,
):
    # Recuperar la precarga real, sin usar el contenido ya elaborado de convenio_listo.
    bruto = crear_convenio(gestor)
    precarga = deepcopy(bruto.borrador.contenido)
    if agregado:
        precarga["content"].append(
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "Clausula adicional sin sustituir antecedentes",
                    }
                ],
            }
        )
    convenio = convenio_listo
    if fuente != "formulario":
        convenio.borrador.contenido = precarga
    db.commit()
    cuerpo = {"objeto": "Cambio simultaneo que debe revertirse"}
    if fuente == "formulario":
        cuerpo["contenido"] = precarga
    if fuente == "historica":
        formalizar_version(convenio, gestor)
    cuerpo["expected_revision"] = (
        convenio.borrador.revision if fuente != "historica" else 0
    )
    antes = _snapshot(db)
    respuesta = client.post(
        f"/api/convenios/{convenio.id}/elaboracion/finalizar", json=cuerpo
    )
    assert respuesta.status_code == 422
    faltantes = respuesta.json()["detail"]["faltantes"]
    assert [f["campo"] for f in faltantes] == ["contenido"]
    assert "Debe elaborar el texto contractual definitivo" in faltantes[0]["motivo"]
    assert "HU-12" in faltantes[0]["motivo"]
    db.expire_all()
    assert _snapshot(db) == antes


@pytest.mark.parametrize("en_formulario", [False, True])
def test_validacion_previa_y_contenido_libre_con_titulos_similares(
    client, db, gestor, crear_convenio, convenio_listo, en_formulario
):
    bruto = crear_convenio(gestor)
    servicio = ServicioConvenios(db)
    assert any(f.campo == "contenido" for f in servicio.validar_elaboracion(bruto.id))
    libre = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Vigencia y renovacion"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "Las partes acuerdan el tipo de convenio y la duracion contractual.",
                    }
                ],
            },
        ],
    }
    convenio_listo.borrador.contenido = (
        bruto.borrador.contenido if en_formulario else libre
    )
    db.commit()
    assert bool(servicio.validar_elaboracion(convenio_listo.id)) is en_formulario
    cuerpo = {"expected_revision": convenio_listo.borrador.revision}
    if en_formulario:
        cuerpo["contenido"] = libre
    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar", json=cuerpo
    )
    assert respuesta.status_code == 200, respuesta.text
    nueva = db.scalar(
        select(VersionConvenio).where(VersionConvenio.convenio_id == convenio_listo.id)
    )
    assert nueva.contenido == libre
