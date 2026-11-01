import pytest
from sqlalchemy import func, inspect, select, text

from backend.models.pais import Pais


def test_solicitud_tiene_tipo_documento_del_solicitante_y_pais_por_id(db_engine):
    inspector = inspect(db_engine)
    columnas = {
        columna["name"]: columna for columna in inspector.get_columns("solicitud_convenio")
    }
    assert columnas["solicitante_tipo_documento"]["nullable"] is True
    assert columnas["solicitante_digito_verificacion"]["nullable"] is True
    assert columnas["digito_verificacion_aliado_propuesto"]["nullable"] is True
    assert columnas["pais_aliado_propuesto_id"]["nullable"] is True
    # El texto se conserva para el historial y los consumidores existentes.
    assert "pais_aliado_propuesto" in columnas
    claves = {
        tuple(fk["constrained_columns"]): fk["referred_table"]
        for fk in inspector.get_foreign_keys("solicitud_convenio")
    }
    assert claves[("pais_aliado_propuesto_id",)] == "pais"


def test_restriccion_de_tipo_documento_lista_los_tipos_de_identificacion(db):
    definicion = db.scalar(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
            " WHERE conname = 'ck_solicitud_solicitante_tipo_documento'"
        )
    )
    assert definicion is not None
    for tipo in (
        "NIT",
        "CEDULA_CIUDADANIA",
        "CEDULA_EXTRANJERIA",
        "PASAPORTE",
        "IDENTIFICACION_FISCAL_EXTRANJERA",
        "OTRO",
    ):
        assert f"'{tipo}'" in definicion


def test_aliado_guarda_el_digito_de_verificacion_aparte(db_engine):
    columnas = {
        columna["name"]: columna for columna in inspect(db_engine).get_columns("aliado")
    }
    assert columnas["digito_verificacion"]["nullable"] is True


@pytest.mark.parametrize(
    ("restriccion", "definicion_esperada"),
    [
        ("ck_aliado_digito_verificacion", "tipo_identificacion"),
        ("ck_solicitud_digito_verificacion_aliado_propuesto", "tipo_identificacion_aliado_propuesto"),
        ("ck_solicitud_solicitante_digito_verificacion", "solicitante_tipo_documento"),
    ],
)
def test_digito_de_verificacion_es_un_digito_y_solo_aplica_a_nit(
    db, restriccion, definicion_esperada
):
    definicion = db.scalar(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :nombre"
        ),
        {"nombre": restriccion},
    )
    assert definicion is not None
    assert definicion_esperada in definicion
    assert "'NIT'" in definicion
    assert "[0-9]" in definicion


def test_catalogo_de_paises_esta_poblado_sin_duplicados(db):
    total = db.scalar(select(func.count()).select_from(Pais))
    assert total >= 240
    assert db.scalar(select(func.count(func.distinct(Pais.codigo_iso)))) == total
    assert db.scalar(select(func.count(func.distinct(func.lower(Pais.nombre))))) == total


@pytest.mark.parametrize(
    ("codigo", "nombre"),
    [
        ("CO", "Colombia"),
        ("ES", "España"),
        ("US", "Estados Unidos"),
        ("MX", "México"),
        ("BR", "Brasil"),
        ("DE", "Alemania"),
        ("PE", "Perú"),
    ],
)
def test_catalogo_de_paises_usa_codigo_iso_y_nombre_en_espanol(db, codigo, nombre):
    assert db.scalar(select(Pais.nombre).where(Pais.codigo_iso == codigo)) == nombre
