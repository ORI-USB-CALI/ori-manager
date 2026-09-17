from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_readiness_check() -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "reachable",
    }
