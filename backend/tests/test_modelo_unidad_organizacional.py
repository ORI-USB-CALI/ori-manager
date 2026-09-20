from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    String,
    inspect,
)

from backend.core.unidades_organizacionales import TipoUnidad
from backend.db.base import Base
from backend.models import UnidadOrganizacional
from backend.models import unidad_organizacional as modulo_unidad

TIPOS_UNIDAD_OFICIALES = {
    "FACULTAD",
    "PROGRAMA",
    "UNIDAD_ADMINISTRATIVA",
}


def test_tipo_unidad_coincide_exactamente_con_el_mer() -> None:
    assert len(TipoUnidad) == 3
    assert {tipo.value for tipo in TipoUnidad} == TIPOS_UNIDAD_OFICIALES


def test_unidad_organizacional_usa_tabla_y_base_oficiales() -> None:
    assert UnidadOrganizacional.__tablename__ == "unidad_organizacional"
    assert issubclass(UnidadOrganizacional, Base)
    assert (
        Base.metadata.tables["unidad_organizacional"] is UnidadOrganizacional.__table__
    )


def test_id_es_primary_key_entera_autoincremental() -> None:
    columna = UnidadOrganizacional.__table__.c.id

    assert columna.primary_key
    assert isinstance(columna.type, Integer)
    assert columna.autoincrement in (True, "auto")


def test_codigo_es_varchar_40_obligatorio_y_unico() -> None:
    columna = UnidadOrganizacional.__table__.c.codigo

    assert isinstance(columna.type, String)
    assert columna.type.length == 40
    assert not columna.nullable
    assert columna.unique


def test_nombre_es_varchar_160_obligatorio() -> None:
    columna = UnidadOrganizacional.__table__.c.nombre

    assert isinstance(columna.type, String)
    assert columna.type.length == 160
    assert not columna.nullable


def test_tipo_es_varchar_obligatorio_con_check_oficial() -> None:
    columna = UnidadOrganizacional.__table__.c.tipo
    checks = {
        restriccion
        for restriccion in UnidadOrganizacional.__table__.constraints
        if isinstance(restriccion, CheckConstraint)
    }

    assert isinstance(columna.type, String)
    assert not isinstance(columna.type, Enum)
    assert columna.type.length >= len(TipoUnidad.UNIDAD_ADMINISTRATIVA.value)
    assert not columna.nullable
    assert len(checks) == 1
    assert str(checks.pop().sqltext) == (
        "tipo IN ('FACULTAD', 'PROGRAMA', 'UNIDAD_ADMINISTRATIVA')"
    )


def test_unidad_padre_id_es_fk_autorreferenciada_nullable() -> None:
    columna = UnidadOrganizacional.__table__.c.unidad_padre_id
    foreign_keys = list(columna.foreign_keys)

    assert isinstance(columna.type, Integer)
    assert columna.nullable
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "unidad_organizacional.id"
    assert foreign_keys[0].column is UnidadOrganizacional.__table__.c.id
    assert foreign_keys[0].ondelete is None


def test_autorrelaciones_configuran_padre_e_hijas() -> None:
    relaciones = inspect(UnidadOrganizacional).relationships
    unidad_padre = relaciones["unidad_padre"]
    subunidades = relaciones["subunidades"]

    assert not unidad_padre.uselist
    assert unidad_padre.back_populates == "subunidades"
    assert unidad_padre.remote_side == {UnidadOrganizacional.__table__.c.id}
    assert subunidades.uselist
    assert subunidades.back_populates == "unidad_padre"


def test_autorrelacion_sincroniza_padre_y_multiples_hijas() -> None:
    facultad = UnidadOrganizacional(
        codigo="FAC",
        nombre="Facultad",
        tipo=TipoUnidad.FACULTAD,
    )
    programa_a = UnidadOrganizacional(
        codigo="PROG-A",
        nombre="Programa A",
        tipo=TipoUnidad.PROGRAMA,
    )
    programa_b = UnidadOrganizacional(
        codigo="PROG-B",
        nombre="Programa B",
        tipo=TipoUnidad.PROGRAMA,
    )

    facultad.subunidades.extend([programa_a, programa_b])

    assert facultad.unidad_padre is None
    assert programa_a.unidad_padre is facultad
    assert programa_b.unidad_padre is facultad


def test_activa_es_booleana_obligatoria_con_default_true() -> None:
    columna = UnidadOrganizacional.__table__.c.activa

    assert isinstance(columna.type, Boolean)
    assert not columna.nullable
    assert columna.default is not None
    assert columna.default.arg is True
    assert columna.server_default is not None


def test_timestamps_tienen_zona_horaria_y_defaults_apropiados() -> None:
    creado_en = UnidadOrganizacional.__table__.c.creado_en
    actualizado_en = UnidadOrganizacional.__table__.c.actualizado_en

    for columna in (creado_en, actualizado_en):
        assert isinstance(columna.type, DateTime)
        assert columna.type.timezone
        assert not columna.nullable
        assert columna.server_default is not None

    assert actualizado_en.onupdate is not None


def test_metadata_registra_solo_la_tabla_propia_del_modelo() -> None:
    tablas_del_modulo = {
        mapper.local_table.name
        for mapper in Base.registry.mappers
        if mapper.class_.__module__ == modulo_unidad.__name__
    }

    assert "unidad_organizacional" in Base.metadata.tables
    assert tablas_del_modulo == {"unidad_organizacional"}
    assert {"permiso", "rol_permiso", "sesion"}.isdisjoint(Base.metadata.tables)
