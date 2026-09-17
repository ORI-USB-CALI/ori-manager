from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models.pais import Pais

HEADERS_SOLICITANTE = {"X-Rol-Usuario": "solicitante_interno"}


def test_listar_paises_sin_header_de_rol_devuelve_401(client: TestClient) -> None:
    response = client.get("/paises")

    assert response.status_code == 401


def test_listar_paises_devuelve_catalogo_ordenado_por_nombre(
    client: TestClient, db_session: Session
) -> None:
    db_session.add_all(
        [
            Pais(codigo_iso="ZZ", nombre="Zz País de prueba"),
            Pais(codigo_iso="ZY", nombre="Zy País de prueba"),
        ]
    )
    db_session.commit()

    response = client.get("/paises", headers=HEADERS_SOLICITANTE)

    assert response.status_code == 200
    nombres = [p["nombre"] for p in response.json()]
    assert nombres == sorted(nombres)
    assert {"id", "codigo_iso", "nombre"} <= set(response.json()[0])
    de_prueba = [p for p in response.json() if p["codigo_iso"] in {"ZZ", "ZY"}]
    assert [p["nombre"] for p in de_prueba] == ["Zy País de prueba", "Zz País de prueba"]
