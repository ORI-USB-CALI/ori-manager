import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.db.session import get_db
from backend.main import app
from backend.models.aliado import Aliado, Convenio, EstadoConvenio

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.pop(get_db, None)


client = TestClient(app)

GESTION_HEADERS = {
    "Authorization": "Bearer fake_token",
    "X-User-Permissions": "aliados:read, convenios:read, convenios:gestionar",
}


def test_crear_convenio_exito_nace_en_tramite(setup_db):
    db = setup_db
    aliado = Aliado(id=uuid.uuid4(), nombre="Aliado Nuevo")
    db.add(aliado)
    db.commit()

    payload = {
        "aliado_id": str(aliado.id),
        "codigo": "CONV-NUEVO-001",
        "titulo": "Convenio recién creado",
        "tipo_convenio": "MARCO",
    }
    response = client.post("/api/v1/convenios", json=payload, headers=GESTION_HEADERS)

    assert response.status_code == 201
    data = response.json()
    # Un convenio nunca nace VIGENTE, sin importar lo que envíe el cliente.
    assert data["estado"] == "EN_TRAMITE"
    assert data["codigo"] == "CONV-NUEVO-001"


def test_crear_convenio_ignora_estado_enviado_por_el_cliente(setup_db):
    db = setup_db
    aliado = Aliado(id=uuid.uuid4(), nombre="Aliado Nuevo")
    db.add(aliado)
    db.commit()

    payload = {
        "aliado_id": str(aliado.id),
        "codigo": "CONV-NUEVO-002",
        "titulo": "Convenio que intenta nacer vigente",
        "estado": "VIGENTE",
    }
    response = client.post("/api/v1/convenios", json=payload, headers=GESTION_HEADERS)

    assert response.status_code == 201
    assert response.json()["estado"] == "EN_TRAMITE"


def test_crear_convenio_sin_permiso_gestionar(setup_db):
    db = setup_db
    aliado = Aliado(id=uuid.uuid4(), nombre="Aliado Nuevo")
    db.add(aliado)
    db.commit()

    headers_sin_gestion = {
        "Authorization": "Bearer fake_token",
        "X-User-Permissions": "aliados:read, convenios:read",
    }
    payload = {
        "aliado_id": str(aliado.id),
        "codigo": "CONV-SIN-PERMISO",
        "titulo": "No debería crearse",
    }
    response = client.post("/api/v1/convenios", json=payload, headers=headers_sin_gestion)

    assert response.status_code == 403


def test_crear_convenio_aliado_inexistente(setup_db):
    payload = {
        "aliado_id": str(uuid.uuid4()),
        "codigo": "CONV-HUERFANO",
        "titulo": "Convenio sin aliado",
    }
    response = client.post("/api/v1/convenios", json=payload, headers=GESTION_HEADERS)

    assert response.status_code == 404


def test_crear_convenio_codigo_duplicado(setup_db):
    db = setup_db
    aliado_a = Aliado(id=uuid.uuid4(), nombre="Aliado A")
    aliado_b = Aliado(id=uuid.uuid4(), nombre="Aliado B")
    db.add_all([aliado_a, aliado_b])
    db.commit()
    db.add(
        Convenio(
            id=uuid.uuid4(),
            aliado_id=aliado_a.id,
            codigo="CONV-REPETIDO",
            titulo="Convenio original",
            estado=EstadoConvenio.EN_TRAMITE,
        )
    )
    db.commit()

    payload = {
        "aliado_id": str(aliado_b.id),
        "codigo": "CONV-REPETIDO",
        "titulo": "Convenio con código repetido",
    }
    response = client.post("/api/v1/convenios", json=payload, headers=GESTION_HEADERS)

    assert response.status_code == 409


def test_crear_convenio_fecha_inicio_posterior_a_fecha_fin(setup_db):
    db = setup_db
    aliado = Aliado(id=uuid.uuid4(), nombre="Aliado Fechas")
    db.add(aliado)
    db.commit()

    payload = {
        "aliado_id": str(aliado.id),
        "codigo": "CONV-FECHAS-INVALIDAS",
        "titulo": "Convenio con fechas invertidas",
        "fecha_inicio": "2027-01-01T00:00:00Z",
        "fecha_fin": "2026-01-01T00:00:00Z",
    }
    response = client.post("/api/v1/convenios", json=payload, headers=GESTION_HEADERS)

    assert response.status_code == 422


def test_cambiar_estado_convenio_exito(setup_db):
    db = setup_db
    aliado = Aliado(id=uuid.uuid4(), nombre="Aliado")
    db.add(aliado)
    db.commit()
    convenio = Convenio(
        id=uuid.uuid4(),
        aliado_id=aliado.id,
        codigo="CONV-TRANSICION-001",
        titulo="Convenio en trámite",
        estado=EstadoConvenio.EN_TRAMITE,
    )
    db.add(convenio)
    db.commit()

    response = client.patch(
        f"/api/v1/convenios/{convenio.id}/estado",
        json={"estado": "VIGENTE"},
        headers=GESTION_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["estado"] == "VIGENTE"


def test_cambiar_estado_convenio_finalizado_no_transiciona(setup_db):
    db = setup_db
    aliado = Aliado(id=uuid.uuid4(), nombre="Aliado")
    db.add(aliado)
    db.commit()
    convenio = Convenio(
        id=uuid.uuid4(),
        aliado_id=aliado.id,
        codigo="CONV-FINALIZADO-001",
        titulo="Convenio ya finalizado",
        estado=EstadoConvenio.FINALIZADO,
    )
    db.add(convenio)
    db.commit()

    response = client.patch(
        f"/api/v1/convenios/{convenio.id}/estado",
        json={"estado": "VIGENTE"},
        headers=GESTION_HEADERS,
    )

    assert response.status_code == 409


def test_cambiar_estado_convenio_cancelado_no_transiciona(setup_db):
    db = setup_db
    aliado = Aliado(id=uuid.uuid4(), nombre="Aliado")
    db.add(aliado)
    db.commit()
    convenio = Convenio(
        id=uuid.uuid4(),
        aliado_id=aliado.id,
        codigo="CONV-CANCELADO-001",
        titulo="Convenio ya cancelado",
        estado=EstadoConvenio.CANCELADO,
    )
    db.add(convenio)
    db.commit()

    response = client.patch(
        f"/api/v1/convenios/{convenio.id}/estado",
        json={"estado": "FINALIZADO"},
        headers=GESTION_HEADERS,
    )

    assert response.status_code == 409


def test_cambiar_estado_convenio_sin_permiso_gestionar(setup_db):
    db = setup_db
    aliado = Aliado(id=uuid.uuid4(), nombre="Aliado")
    db.add(aliado)
    db.commit()
    convenio = Convenio(
        id=uuid.uuid4(),
        aliado_id=aliado.id,
        codigo="CONV-SIN-PERMISO-002",
        titulo="Convenio",
        estado=EstadoConvenio.EN_TRAMITE,
    )
    db.add(convenio)
    db.commit()

    headers_sin_gestion = {
        "Authorization": "Bearer fake_token",
        "X-User-Permissions": "aliados:read, convenios:read",
    }
    response = client.patch(
        f"/api/v1/convenios/{convenio.id}/estado",
        json={"estado": "VIGENTE"},
        headers=headers_sin_gestion,
    )

    assert response.status_code == 403


def test_cambiar_estado_convenio_inexistente(setup_db):
    response = client.patch(
        f"/api/v1/convenios/{uuid.uuid4()}/estado",
        json={"estado": "VIGENTE"},
        headers=GESTION_HEADERS,
    )

    assert response.status_code == 404
