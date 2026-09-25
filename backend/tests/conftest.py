from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
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
from backend.models.convenio import Convenio
from backend.models.enums import AlcanceConvenio, EstadoSolicitud, TipoSolicitante
from backend.models.rol import Rol
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.schemas.convenio import ConvenioCrear
from backend.services.auth import DURACION_SESION
from backend.services.convenios import ServicioConvenios
from backend.services.correo import CorreoLocal, get_enviador_correo
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
def correo_local() -> CorreoLocal:
    return CorreoLocal()


@pytest.fixture
def client(
    db: Session,
    sesiones: RepositorioSesionesMemoria,
    correo_local: CorreoLocal,
    tmp_path,
) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db

    def override_sesiones() -> RepositorioSesionesMemoria:
        return sesiones

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_repositorio_sesiones] = override_sesiones
    app.dependency_overrides[get_enviador_correo] = lambda: correo_local
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
        contrasena: str = "ClaveSegura123!",
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
            correo_verificado_en=datetime.now(UTC),
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


# ---- Fixtures compartidas de HU-13 (convenios) ----------------------------
# Usadas por test_hu13_historial.py, test_hu13_revision.py y
# test_hu13_acciones.py. Centralizadas aquí (en vez de duplicarlas o
# importarlas entre archivos de test) para que pytest las inyecte por nombre
# sin que ruff las marque como redefiniciones (F811).


@pytest.fixture
def gestor(client, crear_usuario, entrar_como) -> Usuario:
    usuario = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    entrar_como(usuario)
    return usuario


@pytest.fixture
def revisor(crear_usuario) -> Usuario:
    return crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)


@pytest.fixture
def solicitante(crear_usuario) -> Usuario:
    return crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)


@pytest.fixture
def crear_convenio(db: Session) -> Callable[..., Convenio]:
    """Crea el convenio mediante el contrato canónico de HU-06."""

    def _crear(autor: Usuario, **cambios) -> Convenio:
        solicitud = SolicitudConvenio(
            consecutivo=f"SOL-{uuid4().hex}",
            tipo_solicitante=TipoSolicitante.INTERNO.value,
            solicitante_id=autor.id,
            objeto="Objeto solicitado originalmente",
            justificacion="Fortalecer la movilidad académica",
            vigencia_estimada="24 meses",
            estado=EstadoSolicitud.APROBADA.value,
            nombre_aliado_propuesto="Universidad Contraparte",
            correo_aliado_propuesto="convenios@contraparte.example",
        )
        db.add(solicitud)
        db.commit()

        datos = {
            "solicitud_id": solicitud.id,
            "objeto": "Objeto inicial del convenio",
            "alcance": AlcanceConvenio.INSTITUCIONAL,
            **cambios,
        }
        return ServicioConvenios(db).crear(
            ConvenioCrear.model_validate(datos),
            autor,
        )

    return _crear


@pytest.fixture
def convenio_listo(db: Session, gestor, crear_convenio) -> Convenio:
    """Convenio con todo lo requerido para entregarlo a Jurídica."""
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    return crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Sin costo para la Universidad",
        duracion_meses=24,
        fecha_inicio=date(2026, 1, 1),
        fecha_vencimiento=date(2028, 1, 1),
    )
