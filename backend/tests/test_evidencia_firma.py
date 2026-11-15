"""Consulta aislada de evidencias; no requiere conexiones ni datos externos."""

from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.deps import get_current_user
from backend.api.routers.convenios import router
from backend.db.session import get_db
from backend.models.firma_convenio import FirmaConvenio
from backend.services.convenios import ConvenioNoEncontrado, ServicioConvenios


@pytest.fixture
def consulta(monkeypatch):
    firma = FirmaConvenio(
        id=17,
        proceso_firmas_id=5,
        modalidad="ELECTRONICA",
        estado="FIRMADA",
        firma_png=b"\x89PNG\r\n\x1a\noriginal",
        firma_sha256=sha256(b"\x89PNG\r\n\x1a\noriginal").hexdigest(),
    )
    db = Mock()
    # Ejecutar la selección real del proceso y la validación de la firma.
    db.scalar.side_effect = lambda query: (
        SimpleNamespace(id=11)
        if "FROM convenio" in str(query)
        else SimpleNamespace(id=5, firmas=[firma])
    )
    alcance = Mock()
    monkeypatch.setattr(ServicioConvenios, "verificar_alcance_operativo", alcance)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        rol=SimpleNamespace(codigo="GESTOR_ORI")
    )
    with TestClient(app) as client:
        yield client, app, firma, db, alcance


@pytest.mark.parametrize("disposicion", ["inline", "attachment"])
def test_png_original_sin_escrituras(consulta, disposicion):
    client, _, firma, db, alcance = consulta
    antes = deepcopy(
        {k: v for k, v in vars(firma).items() if k != "_sa_instance_state"}
    )
    respuesta = client.get(
        f"/api/convenios/11/firmas/17/evidencia?disposicion={disposicion}"
    )
    assert respuesta.status_code == 200
    assert respuesta.content == firma.firma_png
    assert respuesta.headers["content-type"] == "image/png"
    assert (
        respuesta.headers["content-disposition"]
        == f'{disposicion}; filename="convenio-11-firma-17.png"'
    )
    assert respuesta.headers["cache-control"] == "private, no-store"
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    alcance.assert_called_once()
    assert antes == {k: v for k, v in vars(firma).items() if k != "_sa_instance_state"}
    assert all(call[0] == "scalar" for call in db.mock_calls)


@pytest.mark.parametrize(
    "campo,valor,codigo",
    [
        ("modalidad", "FISICA", 404),
        ("estado", "PENDIENTE", 404),
        ("firma_png", None, 404),
        ("firma_sha256", None, 404),
        ("firma_sha256", "0" * 64, 409),
        ("firma_sha256", "\u00e9" * 64, 409),
        ("id", 18, 404),
    ],
)
def test_evidencia_no_consultable(consulta, campo, valor, codigo):
    client, _, firma, _, _ = consulta
    setattr(firma, campo, valor)
    respuesta = client.get("/api/convenios/11/firmas/17/evidencia")
    assert respuesta.status_code == codigo
    assert firma.firma_png not in respuesta.content if firma.firma_png else True


@pytest.mark.parametrize("codigo", [401, 403])
def test_autenticacion_y_permiso(consulta, codigo):
    client, app, _, db, alcance = consulta
    if codigo == 401:
        del app.dependency_overrides[get_current_user]
    else:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            rol=SimpleNamespace(codigo="REVISOR_ORI")
        )
    assert client.get("/api/convenios/11/firmas/17/evidencia").status_code == codigo
    alcance.assert_not_called()
    db.scalar.assert_not_called()


def test_fuera_de_alcance_no_lee_evidencia(consulta):
    client, _, _, db, alcance = consulta
    alcance.side_effect = ConvenioNoEncontrado("Convenio no encontrado")
    assert client.get("/api/convenios/12/firmas/17/evidencia").status_code == 404
    db.scalar.assert_not_called()


def test_sin_proceso_consultable_y_parametro_invalido(consulta):
    client, _, _, db, _ = consulta
    db.scalar.side_effect = [SimpleNamespace(id=11), None]
    assert client.get("/api/convenios/11/firmas/17/evidencia").status_code == 404
    assert (
        client.get(
            "/api/convenios/11/firmas/17/evidencia?disposicion=public"
        ).status_code
        == 422
    )
