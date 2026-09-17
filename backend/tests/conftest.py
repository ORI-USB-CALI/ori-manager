import pytest
from sqlalchemy import Column, Integer, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db.base import Base
from backend.models.convenio import (
    Convenio,  # noqa: F401  (registra la tabla en Base.metadata)
)

# Tablas minimas de apoyo para poder crear el esquema en SQLite durante
# las pruebas. `convenio` referencia por FK a `aliado`, `solicitud_convenio`,
# `tipo_convenio`, `etapa`, `unidad_organizacional` y `usuario`, que
# pertenecen a otras HU todavia no fusionadas a esta rama. Aqui se
# declaran como tablas minimas (solo id) unicamente para que SQLAlchemy
# pueda generar las FKs al crear el esquema de prueba; no representan el
# modelo real de esas entidades.
_TABLAS_DE_APOYO = [
    "aliado",
    "solicitud_convenio",
    "tipo_convenio",
    "etapa",
    "unidad_organizacional",
    "usuario",
]

for _nombre_tabla in _TABLAS_DE_APOYO:
    if _nombre_tabla not in Base.metadata.tables:
        Table(_nombre_tabla, Base.metadata, Column("id", Integer, primary_key=True))


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
