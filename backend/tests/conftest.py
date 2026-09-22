from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings
from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import generar_token_sesion, hash_contrasena
from backend.db.session import get_db
from backend.main import app
from backend.models.rol import Rol
from backend.models.usuario import Usuario
from backend.services.auth import DURACION_SESION
from backend.services.documentos import AlmacenDocumentosLocal, get_almacen_documentos
from backend.services.sesiones import (
    RepositorioSesionesMemoria,
    get_repositorio_sesiones,
)

engine = create_engine(settings.database_url, pool_pre_ping=True)


@pytest.fixture(scope="session")
def db_engine():
    yield engine


@pytest.fixture
def db(db_engine) -> Iterator[Session]:
    connection = db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def sesiones() -> RepositorioSesionesMemoria:
    return RepositorioSesionesMemoria()


@pytest.fixture
def client(
    db: Session, sesiones: RepositorioSesionesMemoria, tmp_path
) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db

    def override_sesiones() -> RepositorioSesionesMemoria:
        return sesiones

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_repositorio_sesiones] = override_sesiones
    app.dependency_overrides[get_almacen_documentos] = lambda: AlmacenDocumentosLocal(
        tmp_path / "documentos"
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def crear_usuario(db: Session) -> Callable[..., Usuario]:
    def _crear(
        codigo_rol: CodigoRol = CodigoRol.GESTOR_ORI,
        tipo_usuario: TipoUsuario = TipoUsuario.INTERNO,
        activo: bool = True,
        correo: str | None = None,
        contrasena: str = "ClaveSegura123",
    ) -> Usuario:
        rol = db.scalar(select(Rol).where(Rol.codigo == codigo_rol.value))
        assert rol is not None
        usuario = Usuario(
            correo=correo or f"usuario-{uuid4().hex}@example.com",
            hash_contrasena=hash_contrasena(contrasena),
            nombre_completo="Usuario de prueba",
            rol=rol,
            tipo_usuario=tipo_usuario.value,
            activo=activo,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario

    return _crear


@pytest.fixture
def entrar_como(
    client: TestClient,
    sesiones: RepositorioSesionesMemoria,
) -> Callable[[Usuario], str]:
    def _entrar(usuario: Usuario) -> str:
        token = generar_token_sesion()
        sesiones.crear(
            usuario.id,
            token,
            datetime.now(UTC) + DURACION_SESION,
        )
        client.cookies.set("session_id", token)
        return token

    return _entrar
