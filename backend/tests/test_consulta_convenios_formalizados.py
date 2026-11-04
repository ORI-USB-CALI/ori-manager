"""Consulta de formalizados sin restringir el tablero operativo ni otros clientes."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.models.etapa import Etapa
from backend.models.tipo_convenio import TipoConvenio
from backend.services.convenios import convenio_esta_formalizado

URL = "/api/convenios"


@pytest.fixture
def crear_por_origen(client, db, gestor, crear_convenio):
    def crear(origen, **datos):
        if origen == "SOLICITUD":
            return crear_convenio(gestor, **datos)
        respuesta = client.post(f"{URL}/manual", json=datos)
        assert respuesta.status_code == 201, respuesta.text
        convenio = db.get(Convenio, respuesta.json()["id"])
        assert convenio.solicitud_id is None
        assert convenio.solicitud is None
        return convenio

    return crear


@pytest.mark.parametrize("origen", ["MANUAL_ORI", "SOLICITUD"])
def test_filtro_opcional_excluye_proyecto_y_lo_incluye_al_formalizar(
    client, db, crear_por_origen, origen,
):
    convenio = crear_por_origen(origen, objeto=f"consulta-{uuid4().hex}")
    parametros = {"buscar": f"#{convenio.id}"}
    for filtro in ({}, {"solo_formalizados": False}):
        respuesta = client.get(URL, params={**parametros, **filtro})
        assert respuesta.status_code == 200
        assert [item["id"] for item in respuesta.json()["items"]] == [convenio.id]
    parametros["solo_formalizados"] = True
    assert client.get(URL, params=parametros).json() == {"items": [], "total": 0}

    convenio.estado = "VIGENTE"
    convenio.fecha_firma = date(2026, 6, 15)
    db.commit()
    respuesta = client.get(URL, params=parametros)
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1
    assert respuesta.json()["items"][0]["id"] == convenio.id
    assert respuesta.json()["items"][0]["fecha_formalizacion"] == "2026-06-15"


@pytest.mark.parametrize("origen", ["MANUAL_ORI", "SOLICITUD"])
@pytest.mark.parametrize("estado", list(EstadoConvenio))
@pytest.mark.parametrize("firma", [None, date(2026, 6, 15)])
def test_criterio_sql_coincide_con_formalizacion_para_todos_los_estados(
    client, db, crear_por_origen, origen, estado, firma,
):
    convenio = crear_por_origen(origen, objeto="Criterio de formalización")
    convenio.estado = estado.value
    convenio.fecha_firma = firma
    db.commit()
    respuesta = client.get(URL, params={
        "buscar": f"#{convenio.id}", "solo_formalizados": True,
    })
    assert respuesta.status_code == 200
    esperado = firma is not None and estado not in {EstadoConvenio.EN_TRAMITE, EstadoConvenio.CANCELADO}
    assert convenio_esta_formalizado(convenio) is esperado
    assert respuesta.json()["total"] == int(esperado)
    assert [item["id"] for item in respuesta.json()["items"]] == ([convenio.id] if esperado else [])


@pytest.mark.parametrize("tipo_fecha", ["FORMALIZACION", "VIGENCIA"])
def test_busqueda_filtros_conteo_y_paginacion_solo_incluyen_formalizados(
    client, db, crear_por_origen, tipo_fecha,
):
    termino = f"formalizados-{uuid4().hex}"
    tipo_id = db.scalar(select(TipoConvenio.id).where(TipoConvenio.codigo == "MARCO"))
    datos = {
        "objeto": termino, "tipo_convenio_id": tipo_id,
        "fecha_inicio": "2026-01-01", "fecha_vencimiento": "2026-12-31",
        "alcance": "INSTITUCIONAL",
    }
    esperados = []
    for origen, estado in (("MANUAL_ORI", "VIGENTE"), ("SOLICITUD", "POR_VENCER"), ("MANUAL_ORI", "VIGENTE")):
        convenio = crear_por_origen(origen, **datos)
        convenio.estado = estado
        convenio.fecha_firma = date(2026, 6, 15)
        db.commit()
        esperados.append(convenio.id)
    # Los excluidos se crean al final: deben desaparecer antes del LIMIT/OFFSET.
    for origen in ("MANUAL_ORI", "SOLICITUD"):
        crear_por_origen(origen, **datos)
        sin_firma = crear_por_origen(origen, **datos)
        sin_firma.estado = "VIGENTE"
        fuera_del_rango = crear_por_origen(origen, **datos)
        fuera_del_rango.estado = "VIGENTE"
        fuera_del_rango.fecha_firma = date(2025, 1, 1)
        fuera_del_rango.fecha_inicio = date(2025, 1, 1)
        fuera_del_rango.fecha_vencimiento = date(2025, 12, 31)
        otro_estado = crear_por_origen(origen, **datos)
        otro_estado.estado = "FINALIZADO"
        otro_estado.fecha_firma = date(2026, 6, 15)
        db.commit()
    parametros = {
        "solo_formalizados": True, "buscar": termino,
        "estado": ["VIGENTE", "POR_VENCER"], "alcance": "INSTITUCIONAL",
        "tipo_fecha": tipo_fecha, "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
        "limite": 1,
    }
    for desplazamiento, convenio_id in enumerate(reversed(esperados)):
        respuesta = client.get(URL, params={**parametros, "desplazamiento": desplazamiento})
        assert respuesta.status_code == 200
        assert respuesta.json()["total"] == 3
        assert [item["id"] for item in respuesta.json()["items"]] == [convenio_id]
    respuesta = client.get(URL, params={**parametros, "desplazamiento": 3})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"items": [], "total": 3}


@pytest.mark.parametrize("etapa", [
    "ELABORACION", "REVISION_AVAL_JURIDICO", "REVISION_CONTRAPARTE",
    "REVISION_FINAL", "APROBACION_FIRMAS",
])
@pytest.mark.parametrize("origen", ["MANUAL_ORI", "SOLICITUD"])
def test_proyectos_se_excluyen_de_consulta_y_conservan_tablero_y_detalle(
    client, db, crear_por_origen, origen, etapa,
):
    convenio = crear_por_origen(origen, objeto="Proyecto visible en el tablero")
    convenio.etapa_actual = db.scalar(select(Etapa).where(Etapa.codigo == etapa))
    db.commit()
    respuesta = client.get(URL, params={"buscar": f"#{convenio.id}", "solo_formalizados": True})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"items": [], "total": 0}
    tablero = client.get(f"{URL}/tablero")
    assert tablero.status_code == 200
    item = next(item for item in tablero.json()["convenios"] if item["id"] == convenio.id)
    assert item["etapa_actual"]["codigo"] == etapa
    assert item["puede_ver_detalle"] is True
    detalle = client.get(f"{URL}/{convenio.id}")
    assert detalle.status_code == 200
    assert detalle.json()["origen"] == origen
    if origen == "MANUAL_ORI":
        assert detalle.json()["solicitud_id"] is None
    if etapa == "ELABORACION":
        assert client.get(f"{URL}/{convenio.id}/elaboracion").status_code == 200


def test_catalogo_formalizados_excluye_estados_incompatibles(client, gestor):
    respuesta = client.get(f"{URL}/catalogos/consulta", params={"solo_formalizados": True})
    assert respuesta.status_code == 200
    assert set(respuesta.json()["estados"]) == {"VIGENTE", "POR_VENCER", "VENCIDO", "RENOVADO", "FINALIZADO"}
    respuesta = client.get(f"{URL}/catalogos/consulta")
    assert respuesta.status_code == 200
    assert set(respuesta.json()["estados"]) == {estado.value for estado in EstadoConvenio}
