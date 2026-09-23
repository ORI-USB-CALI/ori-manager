from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    String,
    inspect,
)

from backend.core.roles import TipoUsuario
from backend.db.base import Base
from backend.models import Rol, UnidadOrganizacional, Usuario
from backend.models import usuario as modulo_usuario

CAMPOS_USUARIO = {
    "id",
    "correo",
    "hash_contrasena",
    "nombre_completo",
    "documento_identidad",
    "telefono",
    "cargo",
    "rol_id",
    "tipo_usuario",
    "unidad_organizacional_id",
    "entidad_externa",
    "activo",
    "ultimo_acceso",
    "correo_verificado_en",
    "creado_en",
    "actualizado_en",
}


def test_usuario_usa_tabla_base_y_campos_oficiales() -> None:
    assert Usuario.__tablename__ == "usuario"
    assert issubclass(Usuario, Base)
    assert Base.metadata.tables["usuario"] is Usuario.__table__
    assert set(Usuario.__table__.columns.keys()) == CAMPOS_USUARIO


def test_id_es_primary_key_entera_autoincremental() -> None:
    columna = Usuario.__table__.c.id

    assert columna.primary_key
    assert isinstance(columna.type, Integer)
    assert columna.autoincrement in (True, "auto")


def test_campos_obligatorios_tienen_longitudes_correctas() -> None:
    esperados = {
        "correo": 160,
        "hash_contrasena": 255,
        "nombre_completo": 160,
    }

    for nombre, longitud in esperados.items():
        columna = Usuario.__table__.c[nombre]
        assert isinstance(columna.type, String)
        assert columna.type.length == longitud
        assert not columna.nullable

    assert Usuario.__table__.c.correo.unique


def test_campos_opcionales_tienen_longitudes_correctas() -> None:
    esperados = {
        "documento_identidad": 40,
        "telefono": 40,
        "cargo": 120,
        "entidad_externa": 160,
    }

    for nombre, longitud in esperados.items():
        columna = Usuario.__table__.c[nombre]
        assert isinstance(columna.type, String)
        assert columna.type.length == longitud
        assert columna.nullable


def test_rol_id_es_fk_obligatoria_con_restrict() -> None:
    columna = Usuario.__table__.c.rol_id
    foreign_keys = list(columna.foreign_keys)

    assert isinstance(columna.type, Integer)
    assert not columna.nullable
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "rol.id"
    assert foreign_keys[0].column is Rol.__table__.c.id
    assert foreign_keys[0].ondelete == "RESTRICT"


def test_tipo_usuario_es_varchar_obligatorio_con_check_oficial() -> None:
    columna = Usuario.__table__.c.tipo_usuario
    checks = {
        restriccion
        for restriccion in Usuario.__table__.constraints
        if isinstance(restriccion, CheckConstraint)
    }

    assert isinstance(columna.type, String)
    assert not isinstance(columna.type, Enum)
    assert columna.type.length == 7
    assert not columna.nullable
    assert len(checks) == 1
    assert str(checks.pop().sqltext) == "tipo_usuario IN ('INTERNO', 'EXTERNO')"


def test_modelo_usa_el_tipo_usuario_canonico() -> None:
    assert modulo_usuario.TipoUsuario is TipoUsuario


def test_unidad_organizacional_id_es_fk_nullable_sin_ondelete() -> None:
    columna = Usuario.__table__.c.unidad_organizacional_id
    foreign_keys = list(columna.foreign_keys)

    assert isinstance(columna.type, Integer)
    assert columna.nullable
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "unidad_organizacional.id"
    assert foreign_keys[0].column is UnidadOrganizacional.__table__.c.id
    assert foreign_keys[0].ondelete is None


def test_activo_es_booleano_obligatorio_con_default_true() -> None:
    columna = Usuario.__table__.c.activo

    assert isinstance(columna.type, Boolean)
    assert not columna.nullable
    assert columna.default is not None
    assert columna.default.arg is True
    assert columna.server_default is not None


def test_ultimo_acceso_es_timestamp_nullable() -> None:
    columna = Usuario.__table__.c.ultimo_acceso

    assert isinstance(columna.type, DateTime)
    assert columna.type.timezone
    assert columna.nullable


def test_correo_verificado_es_timestamp_nullable() -> None:
    columna = Usuario.__table__.c.correo_verificado_en

    assert isinstance(columna.type, DateTime)
    assert columna.type.timezone
    assert columna.nullable
    assert columna.default is None


def test_timestamps_son_obligatorios_y_actualizado_en_tiene_onupdate() -> None:
    creado_en = Usuario.__table__.c.creado_en
    actualizado_en = Usuario.__table__.c.actualizado_en

    for columna in (creado_en, actualizado_en):
        assert isinstance(columna.type, DateTime)
        assert columna.type.timezone
        assert not columna.nullable
        assert columna.server_default is not None

    assert actualizado_en.onupdate is not None


def test_relaciones_bidireccionales_tienen_back_populates_coherente() -> None:
    relaciones_usuario = inspect(Usuario).relationships
    relaciones_rol = inspect(Rol).relationships
    relaciones_unidad = inspect(UnidadOrganizacional).relationships

    assert not relaciones_usuario["rol"].uselist
    assert relaciones_usuario["rol"].back_populates == "usuarios"
    assert relaciones_rol["usuarios"].uselist
    assert relaciones_rol["usuarios"].back_populates == "rol"

    assert not relaciones_usuario["unidad_organizacional"].uselist
    assert relaciones_usuario["unidad_organizacional"].back_populates == "usuarios"
    assert relaciones_unidad["usuarios"].uselist
    assert relaciones_unidad["usuarios"].back_populates == "unidad_organizacional"


def test_usuario_activo_puede_iniciar_sesion_y_desactivar_cambia_estado() -> None:
    usuario = Usuario(activo=True, tipo_usuario=TipoUsuario.INTERNO)

    assert usuario.puede_iniciar_sesion()

    usuario.desactivar()

    assert not usuario.activo
    assert not usuario.puede_iniciar_sesion()


def test_es_interno_distingue_tipos_oficiales() -> None:
    interno = Usuario(tipo_usuario=TipoUsuario.INTERNO)
    externo = Usuario(tipo_usuario=TipoUsuario.EXTERNO)

    assert interno.es_interno()
    assert not externo.es_interno()


def test_metadata_resuelve_todas_las_foreign_keys_reales() -> None:
    assert {"rol", "unidad_organizacional", "usuario"}.issubset(Base.metadata.tables)

    destinos = {
        foreign_key.target_fullname: foreign_key.column
        for foreign_key in Usuario.__table__.foreign_keys
    }

    assert set(destinos) == {"rol.id", "unidad_organizacional.id"}
    assert destinos["rol.id"] is Rol.__table__.c.id
    assert destinos["unidad_organizacional.id"] is UnidadOrganizacional.__table__.c.id
    assert {
        "permiso",
        "rol_permiso",
        "sesion",
        "usuario_rol",
    }.isdisjoint(Base.metadata.tables)
