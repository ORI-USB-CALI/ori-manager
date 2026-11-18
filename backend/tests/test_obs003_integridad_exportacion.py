"""Regresiones de fuentes oficiales; escenarios locales sin datos de staging."""

import ast
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.models.auditoria import Auditoria
from backend.models.version_convenio import VersionConvenio
from backend.services.contenido_convenio import expandir_plantilla
from backend.services.integridad_exportacion import precarga_hu12_reconocible
from backend.services.pdf_convenio import ServicioPdfConvenio


@pytest.fixture
def precarga(convenio_exportable):
    arbol = ast.parse(
        (
            Path(__file__).parents[1]
            / "migrations/versions/7f2a4c9d1e30_hu12_editor_versiones.py"
        ).read_text()
    )
    base = next(
        ast.literal_eval(n.value)
        for n in arbol.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "PLANTILLA_BASE" for t in n.targets)
    )
    solicitud = convenio_exportable.solicitud
    solicitud.vigencia_estimada = "24 meses"
    return expandir_plantilla(base, solicitud, "Especifico")


def version(db, convenio):
    return db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio.id,
            VersionConvenio.numero == convenio.version_actual,
        )
    )


@pytest.mark.parametrize("formato", ["pdf", "excel"])
@pytest.mark.parametrize("agregar_clausula", [False, True])
def test_precarga_historica_se_rechaza_sin_reescribir(
    db, client, convenio_exportable, precarga, formato, agregar_clausula
):
    v = version(db, convenio_exportable)
    if agregar_clausula:
        precarga["content"].append(
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Clausula libre aprobada"}],
            }
        )
    v.contenido = precarga
    v.snapshot_metadata = {**v.snapshot_metadata, "duracion_meses": 1}
    db.commit()
    antes = deepcopy((v.contenido, v.snapshot_metadata, convenio_exportable.estado))
    auditoria = list(db.execute(select(Auditoria.__table__)).all())
    r = client.get(
        f"/api/convenios/{convenio_exportable.id}/exportar?formato={formato}"
    )
    assert r.status_code == 422
    assert r.json()["error"] == "CONVENIO_INCOMPLETO"
    assert "contenido_contractual_ambiguo" in str(r.json()["campos_faltantes"])
    db.expire_all()
    assert antes == (v.contenido, v.snapshot_metadata, convenio_exportable.estado)
    assert auditoria == list(db.execute(select(Auditoria.__table__)).all())


def test_snapshot_prevalece_y_codigo_posterior_es_legitimo(db, convenio_exportable):
    v = version(db, convenio_exportable)
    v.snapshot_metadata = {
        **v.snapshot_metadata,
        "objeto": "Objeto aprobado",
        "duracion_meses": 1,
        "fecha_inicio": "2026-01-01",
        "fecha_vencimiento": "2026-02-01",
        "codigo": None,
        "aliado_id": None,
    }
    convenio_exportable.objeto = "Objeto actual diferente"
    convenio_exportable.duracion_meses = 24
    db.commit()
    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio_exportable.id, db)
    assert dto.objeto == "Objeto aprobado"
    assert dto.duracion_meses == 1
    assert dto.fecha_inicio == date(2026, 1, 1)
    assert dto.codigo == convenio_exportable.codigo
    assert dto.aliado_nombre == convenio_exportable.aliado.nombre


@pytest.mark.parametrize(
    "snapshot", [{}, {"codigo": None, "aliado_id": None}, {"objeto": None}]
)
def test_snapshot_historico_incompleto_no_se_completa(
    db, convenio_exportable, snapshot
):
    v = version(db, convenio_exportable)
    v.snapshot_metadata = snapshot
    db.commit()
    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio_exportable.id, db)
    assert dto.codigo == convenio_exportable.codigo
    assert v.snapshot_metadata == snapshot
    if "objeto" in snapshot:
        assert dto.objeto != convenio_exportable.objeto


def test_palabras_y_titulos_no_son_prueba_de_precarga(precarga):
    assert precarga_hu12_reconocible(precarga)
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
                        "text": "Tipo de convenio: investigacion. Duracion: un mes. Renovacion acordada.",
                    }
                ],
            },
        ],
    }
    assert not precarga_hu12_reconocible(libre)
    precarga["content"][0]["content"][0]["text"] = "Titulo juridico manual diferente"
    assert not precarga_hu12_reconocible(precarga)


@pytest.mark.parametrize("formato", ["pdf", "excel"])
def test_documento_libre_exporta_sin_escrituras(
    db, client, convenio_exportable, formato
):
    from sqlalchemy import event

    sentencias = []

    def observar(conn, cursor, statement, parameters, context, executemany):
        sentencias.append(statement.lstrip().split()[0].upper())

    conexion = db.connection()
    event.listen(conexion, "before_cursor_execute", observar)
    try:
        r = client.get(
            f"/api/convenios/{convenio_exportable.id}/exportar?formato={formato}"
        )
        assert r.status_code == 200
        assert sentencias and set(sentencias) <= {"SELECT"}
    finally:
        event.remove(conexion, "before_cursor_execute", observar)


def test_tipo_congelado_y_no_tipo_de_solicitud(db, convenio_exportable):
    from backend.models.tipo_convenio import TipoConvenio

    aprobado = TipoConvenio(codigo="PRUEBA_OBS003", nombre="Investigacion")
    db.add(aprobado)
    db.flush()
    v = version(db, convenio_exportable)
    v.snapshot_metadata = {
        **v.snapshot_metadata,
        "tipo_convenio_id": aprobado.id,
        "duracion_meses": 1,
    }
    convenio_exportable.solicitud.vigencia_estimada = "24 meses"
    db.commit()
    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio_exportable.id, db)
    assert dto.tipo_convenio == "Investigacion"
    assert dto.duracion_meses == 1
    assert dto.tipo_convenio != convenio_exportable.tipo_convenio.nombre


@pytest.mark.parametrize("formato", ["pdf", "excel"])
def test_manual_sin_solicitud_conserva_exportacion(db, client, convenio_exportable, formato):
    convenio_exportable.origen = "MANUAL_ORI"
    convenio_exportable.solicitud = None
    db.commit()
    assert client.get(f"/api/convenios/{convenio_exportable.id}/exportar?formato={formato}").status_code == 200


def test_identidad_congelada_prevalece_sobre_catalogo(db, convenio_exportable):
    v = version(db, convenio_exportable)
    identidad = {"nombre": "Aliado aprobado", "tipo": "UNIVERSIDAD", "tipo_identificacion": "NIT",
                 "identificacion": "900123456", "digito_verificacion": None}
    v.snapshot_metadata = {**v.snapshot_metadata, "aliado_identidad": identidad}
    db.commit()
    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio_exportable.id, db)
    assert dto.aliado_nombre == "Aliado aprobado"
    assert dto.aliado_nombre != convenio_exportable.aliado.nombre
