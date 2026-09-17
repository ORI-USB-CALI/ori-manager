from fastapi.testclient import TestClient

HEADERS_GESTOR = {"X-Rol-Usuario": "gestor_ori"}
HEADERS_REVISOR = {"X-Rol-Usuario": "revisor_ori"}
HEADERS_SOLICITANTE = {"X-Rol-Usuario": "solicitante_interno"}

# Prefijo poco probable en datos reales, para que los filtros de los tests
# no dependan de lo que haya en la base local.
PREFIJO = "LST-TEST"


def _crear(client: TestClient, sufijo: str, **extra: object) -> dict:
    payload = {
        "identificacion": f"{PREFIJO}-{sufijo}",
        "nombre": f"{PREFIJO} Entidad {sufijo}",
        "tipo": "universidad",
        **extra,
    }
    response = client.post("/aliados", json=payload, headers=HEADERS_GESTOR)
    assert response.status_code == 201, response.text
    return response.json()


def test_listar_sin_header_de_rol_devuelve_401(client: TestClient) -> None:
    response = client.get("/aliados")

    assert response.status_code == 401


def test_listar_con_rol_sin_permiso_devuelve_403(client: TestClient) -> None:
    response = client.get("/aliados", headers=HEADERS_SOLICITANTE)

    assert response.status_code == 403


def test_listar_devuelve_items_y_total(client: TestClient) -> None:
    _crear(client, "A1")
    _crear(client, "A2")

    response = client.get("/aliados", params={"buscar": PREFIJO}, headers=HEADERS_REVISOR)

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total"] == 2
    assert {item["identificacion"] for item in cuerpo["items"]} == {
        f"{PREFIJO}-A1",
        f"{PREFIJO}-A2",
    }


def test_buscar_por_identificacion_exacta(client: TestClient) -> None:
    _crear(client, "B1")
    _crear(client, "B2")

    response = client.get(
        "/aliados", params={"buscar": f"{PREFIJO}-B2"}, headers=HEADERS_GESTOR
    )

    cuerpo = response.json()
    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["identificacion"] == f"{PREFIJO}-B2"


def test_buscar_por_nombre_ignora_mayusculas(client: TestClient) -> None:
    _crear(client, "C1")

    response = client.get(
        "/aliados", params={"buscar": f"{PREFIJO.lower()} entidad c1"}, headers=HEADERS_GESTOR
    )

    assert response.json()["total"] == 1


def test_filtrar_por_tipo_y_estado(client: TestClient) -> None:
    _crear(client, "D1")
    empresa = _crear(client, "D2", tipo="empresa", sector_economico="Tecnología")
    inactiva = _crear(client, "D3", tipo="empresa", sector_economico="Salud")
    client.post(f"/aliados/{inactiva['id']}/inactivar", headers=HEADERS_GESTOR)

    solo_empresas = client.get(
        "/aliados", params={"buscar": PREFIJO, "tipo": "empresa"}, headers=HEADERS_GESTOR
    ).json()
    empresas_activas = client.get(
        "/aliados",
        params={"buscar": PREFIJO, "tipo": "empresa", "estado": "activo"},
        headers=HEADERS_GESTOR,
    ).json()

    assert solo_empresas["total"] == 2
    assert empresas_activas["total"] == 1
    assert empresas_activas["items"][0]["id"] == empresa["id"]


def test_paginacion_respeta_limite_y_desplazamiento(client: TestClient) -> None:
    for sufijo in ("E1", "E2", "E3"):
        _crear(client, sufijo)

    primera = client.get(
        "/aliados", params={"buscar": PREFIJO, "limite": 2}, headers=HEADERS_GESTOR
    ).json()
    segunda = client.get(
        "/aliados",
        params={"buscar": PREFIJO, "limite": 2, "desplazamiento": 2},
        headers=HEADERS_GESTOR,
    ).json()

    assert primera["total"] == 3
    assert len(primera["items"]) == 2
    assert len(segunda["items"]) == 1
    nombres = [item["nombre"] for item in primera["items"] + segunda["items"]]
    assert nombres == sorted(nombres)


def test_limite_fuera_de_rango_devuelve_422(client: TestClient) -> None:
    demasiado = client.get("/aliados", params={"limite": 101}, headers=HEADERS_GESTOR)
    cero = client.get("/aliados", params={"limite": 0}, headers=HEADERS_GESTOR)

    assert demasiado.status_code == 422
    assert cero.status_code == 422
