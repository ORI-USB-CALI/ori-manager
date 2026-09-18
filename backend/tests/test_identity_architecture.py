import importlib.util

from backend.db.base import Base


def test_no_existen_tablas_legacy_de_identidad() -> None:
    assert {
        "users",
        "sessions",
        "sesion",
        "permiso",
        "rol_permiso",
        "usuario_rol",
    }.isdisjoint(Base.metadata.tables)


def test_no_existen_modelos_orm_user_o_session() -> None:
    assert importlib.util.find_spec("backend.models.user") is None
    assert importlib.util.find_spec("backend.models.session") is None
