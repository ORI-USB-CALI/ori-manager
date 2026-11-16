from copy import deepcopy

import pytest
from helpers_contenido import documento_contractual
from sqlalchemy import select

from backend.models.auditoria import Auditoria
from backend.models.borrador_convenio import BorradorConvenio
from backend.models.convenio import Convenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.plantilla_convenio import PlantillaConvenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.contenido_convenio import expandir_plantilla
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


def test_recuperar_borrador_antiguo_sin_alterar_solicitud(client, db, convenio_listo):
    convenio = convenio_listo
    plantilla = db.scalar(select(PlantillaConvenio).where(PlantillaConvenio.codigo == "BASE_HU12"))
    anterior = expandir_plantilla(plantilla.contenido_base, convenio.solicitud, None)
    anterior["content"].extend(documento_contractual("Trabajo adicional del Gestor")["content"])
    convenio.borrador.contenido = anterior
    db.commit()
    antes = _snapshot(db)
    url = f"/api/convenios/{convenio.id}/elaboracion"
    lectura = client.get(url).json()
    assert lectura["contenido"] == anterior
    assert lectura["contiene_antecedentes_iniciales"] is True
    assert _snapshot(db) == antes
    revision = lectura["revision_borrador"]
    vacio = {"type": "doc", "content": [{"type": "paragraph"}]}
    guardado = client.patch(url, json={"contenido": vacio, "expected_revision": revision})
    assert guardado.status_code == 200
    assert guardado.json()["contiene_antecedentes_iniciales"] is False
    despues = _snapshot(db)
    assert client.patch(url, json={"contenido": anterior, "expected_revision": revision}).status_code == 409
    assert _snapshot(db) == despues
    revision = guardado.json()["revision_borrador"]
    assert client.post(url + "/finalizar", json={"expected_revision": revision}).status_code == 422
    assert _snapshot(db) == despues
    contrato = documento_contractual()
    assert client.patch(url, json={"contenido": contrato, "expected_revision": revision}).status_code == 200
    assert client.post(url + "/finalizar", json={"expected_revision": revision + 1}).status_code == 200
    db.expire_all()
    assert _snapshot(db)[SolicitudConvenio.__tablename__] == antes[SolicitudConvenio.__tablename__]
    assert db.scalar(select(VersionConvenio).where(VersionConvenio.convenio_id == convenio.id)).contenido == contrato


def test_reutiliza_plantilla_neutra_sin_expandir_solicitud(db, gestor, crear_convenio):
    plantilla = db.scalar(select(PlantillaConvenio).where(PlantillaConvenio.codigo == "BASE_HU12"))
    plantilla.contenido_base = documento_contractual("Texto de plantilla configurada por ORI")
    db.commit()
    convenio = crear_convenio(gestor)
    assert convenio.borrador.contenido == plantilla.contenido_base
    assert convenio.plantilla_origen_id == plantilla.id


@pytest.mark.parametrize("activa,contenido", [
    (False, documento_contractual()),
    (True, {"type": "doc", "content": [{"type": "unsupported"}]}),
    (True, documento_contractual("{{ solicitud.objeto }}")),
])
def test_sin_plantilla_apropiada_inicia_vacio(db, gestor, crear_convenio, activa, contenido):
    plantilla = db.scalar(select(PlantillaConvenio).where(PlantillaConvenio.codigo == "BASE_HU12"))
    plantilla.activa = activa
    plantilla.contenido_base = contenido
    db.commit()
    convenio = crear_convenio(gestor)
    assert convenio.borrador.contenido == {"type": "doc", "content": [{"type": "paragraph"}]}
    assert convenio.plantilla_origen_id is None


@pytest.mark.parametrize("fuente", ["borrador", "formulario", "historica"])
@pytest.mark.parametrize("agregado", [False, True])
def test_estructura_antigua_no_bloquea_revision_juridica(
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
    precarga = expandir_plantilla(
        db.scalar(select(PlantillaConvenio).where(PlantillaConvenio.codigo == "BASE_HU12")).contenido_base,
        bruto.solicitud, None,
    )
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
    historicas = deepcopy(list(db.execute(select(VersionConvenio.__table__)).all()))
    lectura = client.get(f"/api/convenios/{convenio.id}/elaboracion")
    if fuente != "formulario":
        assert lectura.json()["contenido"] == precarga
        assert lectura.json()["contiene_antecedentes_iniciales"] is True
    respuesta = client.post(
        f"/api/convenios/{convenio.id}/elaboracion/finalizar", json=cuerpo
    )
    assert respuesta.status_code == 200, respuesta.text
    db.expire_all()
    for anterior in historicas:
        assert db.execute(select(VersionConvenio.__table__).where(
            VersionConvenio.id == anterior.id
        )).one() == anterior
    assert convenio.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"


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
