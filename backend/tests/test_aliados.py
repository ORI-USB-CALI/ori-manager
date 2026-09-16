import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.db.session import get_db
from backend.main import app
from backend.models.aliado import Aliado, Convenio, EstadoAliado, EstadoConvenio

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer fake_token",
    "X-User-Permissions": "aliados:read, convenios:read",
}


def test_ca01_ca02_ca03_consultar_aliado_exito(setup_db):
    db = setup_db
    aliado = Aliado(
        id=uuid.uuid4(),
        nombre="Universidad de Pruebas",
        nit_o_identificacion="900123456-1",
        tipo_aliado="ACADEMICO",
        estado=EstadoAliado.ACTIVO,
        descripcion="Aliado académico principal",
    )
    db.add(aliado)
    db.commit()

    c1 = Convenio(
        id=uuid.uuid4(),
        aliado_id=aliado.id,
        codigo="CONV-2026-001",
        titulo="Convenio Marco de Cooperación",
        tipo_convenio="MARCO",
        estado=EstadoConvenio.VIGENTE,
    )
    c2 = Convenio(
        id=uuid.uuid4(),
        aliado_id=aliado.id,
        codigo="CONV-2024-088",
        titulo="Convenio de Intercambio Docente",
        tipo_convenio="ESPECIFICO",
        estado=EstadoConvenio.FINALIZADO,
    )
    db.add_all([c1, c2])
    db.commit()

    response = client.get(f"/api/v1/aliados/{aliado.id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()

    # CA-01
    assert data["id"] == str(aliado.id)
    assert data["nombre"] == "Universidad de Pruebas"
    assert data["estado"] == "ACTIVO"

    # CA-02 & CA-03
    assert len(data["convenios"]) == 2
    estados = {c["estado"] for c in data["convenios"]}
    assert "VIGENTE" in estados
    assert "FINALIZADO" in estados


def test_ca04_consultar_aliado_sin_convenios(setup_db):
    db = setup_db
    aliado = Aliado(
        id=uuid.uuid4(),
        nombre="Aliado Nuevo Sin Convenios",
        estado=EstadoAliado.ACTIVO,
    )
    db.add(aliado)
    db.commit()

    response = client.get(f"/api/v1/aliados/{aliado.id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(aliado.id)
    assert data["convenios"] == []


def test_ca05_consultar_aliado_inexistente(setup_db):
    random_id = uuid.uuid4()
    response = client.get(f"/api/v1/aliados/{random_id}", headers=AUTH_HEADERS)

    assert response.status_code == 404
    assert response.json()["detail"] == "Aliado no encontrado"


def test_ca06_consultar_aliado_sin_autenticacion_o_permisos(setup_db):
    db = setup_db
    aliado = Aliado(id=uuid.uuid4(), nombre="Aliado Test")
    db.add(aliado)
    db.commit()

    # Sin header de autenticación -> 401
    res_unauth = client.get(f"/api/v1/aliados/{aliado.id}")
    assert res_unauth.status_code == 401

    # Autenticado pero sin permiso 'aliados:read' -> 403
    no_perm_headers = {
        "Authorization": "Bearer fake_token",
        "X-User-Permissions": "otra_cosa:read",
    }
    res_forbidden = client.get(f"/api/v1/aliados/{aliado.id}", headers=no_perm_headers)
    assert res_forbidden.status_code == 403


def test_ca07_consistencia_convenios_otro_aliado(setup_db):
    db = setup_db
    aliado_a = Aliado(id=uuid.uuid4(), nombre="Aliado A")
    aliado_b = Aliado(id=uuid.uuid4(), nombre="Aliado B")
    db.add_all([aliado_a, aliado_b])
    db.commit()

    conv_a = Convenio(
        id=uuid.uuid4(),
        aliado_id=aliado_a.id,
        codigo="CONV-A",
        titulo="Convenio A",
        estado=EstadoConvenio.VIGENTE,
    )
    conv_b = Convenio(
        id=uuid.uuid4(),
        aliado_id=aliado_b.id,
        codigo="CONV-B",
        titulo="Convenio B",
        estado=EstadoConvenio.VIGENTE,
    )
    db.add_all([conv_a, conv_b])
    db.commit()

    res_a = client.get(f"/api/v1/aliados/{aliado_a.id}", headers=AUTH_HEADERS)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert len(data_a["convenios"]) == 1
    assert data_a["convenios"][0]["id"] == str(conv_a.id)


def test_ca08_consultar_aliado_inactivo(setup_db):
    db = setup_db
    aliado_inactivo = Aliado(
        id=uuid.uuid4(),
        nombre="Aliado Antiguo Inactivo",
        estado=EstadoAliado.INACTIVO,
    )
    db.add(aliado_inactivo)
    db.commit()

    conv_historico = Convenio(
        id=uuid.uuid4(),
        aliado_id=aliado_inactivo.id,
        codigo="CONV-HIST-01",
        titulo="Convenio Histórico Finalizado",
        estado=EstadoConvenio.FINALIZADO,
    )
    db.add(conv_historico)
    db.commit()

    response = client.get(f"/api/v1/aliados/{aliado_inactivo.id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(aliado_inactivo.id)
    assert data["estado"] == "INACTIVO"
    assert len(data["convenios"]) == 1
    assert data["convenios"][0]["codigo"] == "CONV-HIST-01"
