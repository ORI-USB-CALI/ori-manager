import inspect

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text

from backend.db.base import Base
from backend.models import Rol
from backend.models import rol as modulo_rol

CAMPOS_ROL = {
    "id",
    "codigo",
    "nombre",
    "descripcion",
    "es_interno",
    "activo",
    "creado_en",
    "actualizado_en",
}


def test_rol_usa_tabla_singular_y_base_oficial() -> None:
    assert Rol.__tablename__ == "rol"
    assert issubclass(Rol, Base)
    assert Rol.__table__ is Base.metadata.tables["rol"]
    assert set(Rol.__table__.columns.keys()) == CAMPOS_ROL


def test_id_es_primary_key_entera() -> None:
    columna = Rol.__table__.c.id

    assert columna.primary_key
    assert isinstance(columna.type, Integer)


def test_codigo_es_varchar_40_obligatorio_y_unico() -> None:
    columna = Rol.__table__.c.codigo

    assert isinstance(columna.type, String)
    assert not isinstance(columna.type, Enum)
    assert columna.type.length == 40
    assert not columna.nullable
    assert columna.unique


def test_nombre_es_varchar_80_obligatorio() -> None:
    columna = Rol.__table__.c.nombre

    assert isinstance(columna.type, String)
    assert columna.type.length == 80
    assert not columna.nullable


def test_descripcion_es_texto_nullable() -> None:
    columna = Rol.__table__.c.descripcion

    assert isinstance(columna.type, Text)
    assert columna.nullable


def test_flags_son_booleanos_obligatorios_con_default_true() -> None:
    for nombre in ("es_interno", "activo"):
        columna = Rol.__table__.c[nombre]

        assert isinstance(columna.type, Boolean)
        assert not columna.nullable
        assert columna.default is not None
        assert columna.default.arg is True
        assert columna.server_default is not None


def test_timestamps_tienen_zona_horaria_y_defaults_apropiados() -> None:
    creado_en = Rol.__table__.c.creado_en
    actualizado_en = Rol.__table__.c.actualizado_en

    for columna in (creado_en, actualizado_en):
        assert isinstance(columna.type, DateTime)
        assert columna.type.timezone
        assert not columna.nullable
        assert columna.server_default is not None

    assert actualizado_en.onupdate is not None


def test_rol_no_declara_foreign_keys() -> None:
    assert not Rol.__table__.foreign_keys


def test_modelo_no_redefine_codigo_rol() -> None:
    assert not hasattr(modulo_rol, "CodigoRol")
    assert "class CodigoRol" not in inspect.getsource(modulo_rol)


def test_metadata_registra_unicamente_la_tabla_propia_del_modelo_rol() -> None:
    tablas_del_modulo = {
        mapper.local_table.name
        for mapper in Base.registry.mappers
        if mapper.class_.__module__ == modulo_rol.__name__
    }

    assert "rol" in Base.metadata.tables
    assert Base.metadata.tables["rol"] is Rol.__table__
    assert tablas_del_modulo == {"rol"}
    assert {"permiso", "rol_permiso", "sesion"}.isdisjoint(Base.metadata.tables)
