from fastapi.testclient import TestClient

HEADERS_GESTOR = {"X-Rol-Usuario": "gestor_ori"}
HEADERS_REVISOR = {"X-Rol-Usuario": "revisor_ori"}
HEADERS_SOLICITANTE = {"X-Rol-Usuario": "solicitante_interno"}

CONTACTO_BASE = {
    "nombre": "Laura Restrepo",
    "cargo": "Coordinadora de alianzas",
    "correo": "lrestrepo@entidad.org",
    "telefono": "+57 602 5542100",
    "extension": "145",
}


def _crear_aliado(client: TestClient, identificacion: str) -> dict:
    response = client.post(
        "/aliados",
        json={"identificacion": identificacion, "nombre": "Aliado con contactos", "tipo": "colegio"},
        headers=HEADERS_GESTOR,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _crear_contacto(client: TestClient, aliado_id: int, **extra: object) -> dict:
    response = client.post(
        f"/aliados/{aliado_id}/contactos",
        json={**CONTACTO_BASE, **extra},
        headers=HEADERS_GESTOR,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_crear_contacto_devuelve_201_con_valores_por_defecto(client: TestClient) -> None:
    aliado = _crear_aliado(client, "CTO-TEST-1")

    contacto = _crear_contacto(client, aliado["id"])

    assert contacto["aliado_id"] == aliado["id"]
    assert contacto["nombre"] == "Laura Restrepo"
    assert contacto["es_principal"] is False
    assert contacto["activo"] is True


def test_crear_contacto_con_rol_de_consulta_devuelve_403(client: TestClient) -> None:
    aliado = _crear_aliado(client, "CTO-TEST-2")

    response = client.post(
        f"/aliados/{aliado['id']}/contactos", json=CONTACTO_BASE, headers=HEADERS_REVISOR
    )

    assert response.status_code == 403


def test_crear_contacto_en_aliado_inexistente_devuelve_404(client: TestClient) -> None:
    response = client.post(
        "/aliados/999999/contactos", json=CONTACTO_BASE, headers=HEADERS_GESTOR
    )

    assert response.status_code == 404


def test_listar_contactos_pone_primero_al_principal(client: TestClient) -> None:
    aliado = _crear_aliado(client, "CTO-TEST-3")
    _crear_contacto(client, aliado["id"], nombre="Andrés Mejía")
    _crear_contacto(client, aliado["id"], nombre="Zulma Ortiz", es_principal=True)

    response = client.get(f"/aliados/{aliado['id']}/contactos", headers=HEADERS_REVISOR)

    assert response.status_code == 200
    assert [c["nombre"] for c in response.json()] == ["Zulma Ortiz", "Andrés Mejía"]


def test_listar_contactos_con_rol_sin_permiso_devuelve_403(client: TestClient) -> None:
    aliado = _crear_aliado(client, "CTO-TEST-4")

    response = client.get(f"/aliados/{aliado['id']}/contactos", headers=HEADERS_SOLICITANTE)

    assert response.status_code == 403


def test_editar_contacto_actualiza_cargo(client: TestClient) -> None:
    aliado = _crear_aliado(client, "CTO-TEST-5")
    contacto = _crear_contacto(client, aliado["id"])

    response = client.patch(
        f"/aliados/{aliado['id']}/contactos/{contacto['id']}",
        json={"cargo": "Directora de relaciones internacionales"},
        headers=HEADERS_GESTOR,
    )

    assert response.status_code == 200
    assert response.json()["cargo"] == "Directora de relaciones internacionales"
    assert response.json()["correo"] == CONTACTO_BASE["correo"]


def test_desactivar_contacto_conserva_el_registro(client: TestClient) -> None:
    aliado = _crear_aliado(client, "CTO-TEST-6")
    contacto = _crear_contacto(client, aliado["id"])

    response = client.patch(
        f"/aliados/{aliado['id']}/contactos/{contacto['id']}",
        json={"activo": False},
        headers=HEADERS_GESTOR,
    )
    listado = client.get(f"/aliados/{aliado['id']}/contactos", headers=HEADERS_GESTOR).json()

    assert response.status_code == 200
    assert response.json()["activo"] is False
    assert [c["id"] for c in listado] == [contacto["id"]]


def test_consultar_contacto_de_otro_aliado_devuelve_404(client: TestClient) -> None:
    aliado_a = _crear_aliado(client, "CTO-TEST-7A")
    aliado_b = _crear_aliado(client, "CTO-TEST-7B")
    contacto = _crear_contacto(client, aliado_a["id"])

    response = client.get(
        f"/aliados/{aliado_b['id']}/contactos/{contacto['id']}", headers=HEADERS_GESTOR
    )

    assert response.status_code == 404


def test_editar_contacto_inexistente_devuelve_404(client: TestClient) -> None:
    aliado = _crear_aliado(client, "CTO-TEST-8")

    response = client.patch(
        f"/aliados/{aliado['id']}/contactos/999999",
        json={"cargo": "Nada"},
        headers=HEADERS_GESTOR,
    )

    assert response.status_code == 404
