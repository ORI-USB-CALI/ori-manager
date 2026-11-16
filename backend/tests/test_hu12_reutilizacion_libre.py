"""CA-02: el documento generado por frontend usa los contratos vigentes de guardado."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.contenido_convenio import validar_contenido
from backend.services.integridad_exportacion import precarga_hu12_reconocible

EJEMPLO = json.loads(
    (Path(__file__).resolve().parents[2] / "frontend/src/pages/fixtures/hu12_base_solicitud.json")
    .read_text(encoding="utf-8")
)
NARRATIVAS = ("objeto", "justificacion", "actividades_por_parte", "metas_esperadas")


def _solicitud(db, solicitud_id):
    return db.execute(
        select(SolicitudConvenio.__table__).where(SolicitudConvenio.id == solicitud_id)
    ).one()


@pytest.mark.parametrize("edicion", ["base", "sin_titulos", "sustituida"])
def test_base_se_guarda_y_edita_sin_versionar_ni_alterar_solicitud(
    client, db, gestor, convenio_listo, edicion
):
    convenio = convenio_listo
    solicitud = convenio.solicitud
    for campo in NARRATIVAS:
        setattr(solicitud, campo, EJEMPLO["solicitud"][campo])
    solicitud.vigencia_estimada = EJEMPLO["solicitud"]["vigencia_estimada"]
    solicitud.tipo_convenio_id = None
    db.commit()
    original = deepcopy(_solicitud(db, solicitud.id))
    url = f"/api/convenios/{convenio.id}/elaboracion"
    lectura = client.get(url).json()
    assert all(lectura["solicitud"][c] == EJEMPLO["solicitud"][c] for c in NARRATIVAS)
    assert lectura["contenido"] != EJEMPLO["documento"]
    assert lectura["duracion_meses"] != EJEMPLO["solicitud"]["duracion_meses"]
    assert lectura["tipo_convenio_id"] is not None

    base = EJEMPLO["documento"]
    assert validar_contenido(base) == base
    assert not precarga_hu12_reconocible(base)
    assert "{{" not in json.dumps(base)
    guardado = client.patch(url, json={
        "contenido": base, "expected_revision": lectura["revision_borrador"],
    })
    assert guardado.status_code == 200
    datos = guardado.json()
    assert datos["contenido"] == base
    assert datos["version_actual"] == 0
    assert datos["contiene_antecedentes_iniciales"] is False
    assert datos["tipo_convenio_id"] == lectura["tipo_convenio_id"]
    assert datos["duracion_meses"] == lectura["duracion_meses"]
    assert datos["fecha_inicio"] == lectura["fecha_inicio"]
    assert datos["fecha_vencimiento"] == lectura["fecha_vencimiento"]
    assert list(db.scalars(select(VersionConvenio).where(
        VersionConvenio.convenio_id == convenio.id,
    ))) == []
    assert _solicitud(db, solicitud.id) == original

    # La acción no elude la revisión optimista del guardado existente.
    assert client.patch(url, json={
        "contenido": base, "expected_revision": lectura["revision_borrador"],
    }).status_code == 409
    assert client.get(url).json()["contenido"] == base

    contenido = deepcopy(base)
    if edicion == "sin_titulos":
        contenido["content"] = [b for b in contenido["content"] if b["type"] != "heading"]
    elif edicion == "sustituida":
        contenido = {"type": "doc", "content": [{
            "type": "paragraph", "content": [{"type": "text", "text": "Acuerdo redactado libremente por ORI"}],
        }]}
    enviada = client.post(url + "/finalizar", json={
        "contenido": contenido, "expected_revision": datos["revision_borrador"],
    })
    assert enviada.status_code == 200
    assert enviada.json()["version_actual"] == 1
    db.expire_all()
    version = db.scalar(select(VersionConvenio).where(
        VersionConvenio.convenio_id == convenio.id,
    ))
    assert version.contenido == contenido
    assert version.snapshot_metadata["duracion_meses"] == lectura["duracion_meses"]
    revision = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id,
        RevisionConvenio.estado == "PENDIENTE",
    ))
    assert revision.version_convenio_id == version.id
    assert _solicitud(db, solicitud.id) == original


@pytest.mark.parametrize("formato", ["pdf", "excel"])
def test_base_libre_aprobada_es_exportable_sin_proteccion_de_precarga(
    client, db, convenio_exportable, formato
):
    # Preparar la fuente aprobada del fixture local, como en las regresiones OBS-S3-003.
    version = db.scalar(select(VersionConvenio).where(
        VersionConvenio.convenio_id == convenio_exportable.id,
        VersionConvenio.numero == convenio_exportable.version_actual,
    ))
    version.contenido = deepcopy(EJEMPLO["documento"])
    db.commit()
    antes = deepcopy((version.contenido, version.snapshot_metadata))
    respuesta = client.get(
        f"/api/convenios/{convenio_exportable.id}/exportar?formato={formato}"
    )
    assert respuesta.status_code == 200
    assert respuesta.content.startswith(b"%PDF" if formato == "pdf" else b"PK")
    db.refresh(version)
    assert (version.contenido, version.snapshot_metadata) == antes
