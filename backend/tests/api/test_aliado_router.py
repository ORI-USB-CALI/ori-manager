from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio, RolUsuario, TipoAliado
from backend.services import aliado as aliado_service

HEADERS_GESTOR = {"X-Rol-Usuario": "gestor_ori"}
HEADERS_ADMIN = {"X-Rol-Usuario": "administrador_ori"}
HEADERS_REVISOR = {"X-Rol-Usuario": "revisor_ori"}
HEADERS_SOLICITANTE = {"X-Rol-Usuario": "solicitante_interno"}

PAYLOAD_BASE = {
    "identificacion": "900123456-1",
    "nombre": "Aliado de Prueba",
    "tipo": "empresa",
    "sector_economico": "Tecnología",
}


def test_crear_aliado_devuelve_201(client: TestClient) -> None:
    response = client.post("/aliados", json=PAYLOAD_BASE, headers=HEADERS_GESTOR)

    assert response.status_code == 201
    cuerpo = response.json()
    assert cuerpo["identificacion"] == "900123456-1"
    assert cuerpo["estado"] == "activo"


def test_crear_aliado_sin_header_de_rol_devuelve_401(client: TestClient) -> None:
    response = client.post("/aliados", json=PAYLOAD_BASE)

    assert response.status_code == 401


def test_crear_aliado_con_rol_invalido_devuelve_400(client: TestClient) -> None:
    response = client.post(
        "/aliados", json=PAYLOAD_BASE, headers={"X-Rol-Usuario": "rol_inexistente"}
    )

    assert response.status_code == 400


def test_crear_aliado_con_rol_sin_permiso_devuelve_403(client: TestClient) -> None:
    response = client.post("/aliados", json=PAYLOAD_BASE, headers=HEADERS_SOLICITANTE)

    assert response.status_code == 403


def test_crear_aliado_duplicado_devuelve_409(client: TestClient) -> None:
    client.post("/aliados", json=PAYLOAD_BASE, headers=HEADERS_ADMIN)

    response = client.post("/aliados", json=PAYLOAD_BASE, headers=HEADERS_ADMIN)

    assert response.status_code == 409


def test_crear_aliado_empresa_sin_sector_devuelve_422(client: TestClient) -> None:
    payload = {**PAYLOAD_BASE, "identificacion": "900654321-1", "sector_economico": None}

    response = client.post("/aliados", json=payload, headers=HEADERS_ADMIN)

    assert response.status_code == 422


def test_consultar_aliado_devuelve_200(client: TestClient, db_session: Session) -> None:
    creado = aliado_service.crear_aliado(
        db_session,
        aliado_service.DatosAliado(
            identificacion="900111222-3",
            nombre="Aliado de Prueba",
            tipo=TipoAliado.EMPRESA,
            sector_economico="Tecnología",
        ),
        rol=RolUsuario.ADMINISTRADOR_ORI,
    )
    db_session.commit()

    response = client.get(f"/aliados/{creado.id}", headers=HEADERS_REVISOR)

    assert response.status_code == 200
    assert response.json()["id"] == creado.id


def test_consultar_aliado_inexistente_devuelve_404(client: TestClient) -> None:
    response = client.get("/aliados/999999", headers=HEADERS_ADMIN)

    assert response.status_code == 404


def test_editar_aliado_actualiza_ciudad(client: TestClient) -> None:
    creado = client.post(
        "/aliados",
        json={**PAYLOAD_BASE, "identificacion": "900222333-4"},
        headers=HEADERS_GESTOR,
    ).json()

    response = client.patch(
        f"/aliados/{creado['id']}", json={"ciudad": "Cali"}, headers=HEADERS_GESTOR
    )

    assert response.status_code == 200
    assert response.json()["ciudad"] == "Cali"


def test_inactivar_aliado_ok(client: TestClient) -> None:
    creado = client.post(
        "/aliados",
        json={**PAYLOAD_BASE, "identificacion": "900333444-5"},
        headers=HEADERS_ADMIN,
    ).json()

    response = client.post(f"/aliados/{creado['id']}/inactivar", headers=HEADERS_ADMIN)

    assert response.status_code == 200
    assert response.json()["estado"] == "inactivo"


def test_inactivar_aliado_con_convenios_vigentes_devuelve_409(
    client: TestClient, db_session: Session
) -> None:
    creado = client.post(
        "/aliados",
        json={**PAYLOAD_BASE, "identificacion": "900444555-6"},
        headers=HEADERS_ADMIN,
    ).json()
    db_session.add(Convenio(aliado_id=creado["id"], estado=EstadoConvenio.VIGENTE))
    db_session.commit()

    response = client.post(f"/aliados/{creado['id']}/inactivar", headers=HEADERS_ADMIN)

    assert response.status_code == 409


def test_reactivar_aliado_ok(client: TestClient) -> None:
    creado = client.post(
        "/aliados",
        json={**PAYLOAD_BASE, "identificacion": "900555666-7"},
        headers=HEADERS_ADMIN,
    ).json()
    client.post(f"/aliados/{creado['id']}/inactivar", headers=HEADERS_ADMIN)

    response = client.post(f"/aliados/{creado['id']}/reactivar", headers=HEADERS_ADMIN)

    assert response.status_code == 200
    assert response.json()["estado"] == "activo"
