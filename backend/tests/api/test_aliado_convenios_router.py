from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio

HEADERS_GESTOR = {"X-Rol-Usuario": "gestor_ori"}
HEADERS_REVISOR = {"X-Rol-Usuario": "revisor_ori"}
HEADERS_SOLICITANTE = {"X-Rol-Usuario": "solicitante_interno"}


def _crear_aliado(client: TestClient, identificacion: str) -> dict:
    response = client.post(
        "/aliados",
        json={"identificacion": identificacion, "nombre": "Aliado con convenios", "tipo": "colegio"},
        headers=HEADERS_GESTOR,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_listar_convenios_devuelve_todos_los_estados(
    client: TestClient, db_session: Session
) -> None:
    aliado = _crear_aliado(client, "CNV-TEST-1")
    db_session.add_all(
        [
            Convenio(aliado_id=aliado["id"], estado=EstadoConvenio.VIGENTE),
            Convenio(aliado_id=aliado["id"], estado=EstadoConvenio.VENCIDO),
        ]
    )
    db_session.commit()

    response = client.get(f"/aliados/{aliado['id']}/convenios", headers=HEADERS_REVISOR)

    assert response.status_code == 200
    convenios = response.json()
    assert [c["estado"] for c in convenios] == ["vigente", "vencido"]
    assert all(c["aliado_id"] == aliado["id"] for c in convenios)


def test_listar_convenios_de_aliado_sin_convenios_devuelve_lista_vacia(
    client: TestClient,
) -> None:
    aliado = _crear_aliado(client, "CNV-TEST-2")

    response = client.get(f"/aliados/{aliado['id']}/convenios", headers=HEADERS_GESTOR)

    assert response.status_code == 200
    assert response.json() == []


def test_listar_convenios_de_aliado_inexistente_devuelve_404(client: TestClient) -> None:
    response = client.get("/aliados/999999/convenios", headers=HEADERS_GESTOR)

    assert response.status_code == 404


def test_listar_convenios_con_rol_sin_permiso_devuelve_403(client: TestClient) -> None:
    aliado = _crear_aliado(client, "CNV-TEST-3")

    response = client.get(f"/aliados/{aliado['id']}/convenios", headers=HEADERS_SOLICITANTE)

    assert response.status_code == 403
