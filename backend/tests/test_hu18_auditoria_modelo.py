import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from backend.core.roles import CodigoRol
from backend.models.auditoria import Auditoria
from backend.models.enums import AccionAuditoria


def test_auditoria_tiene_rol_e_indice_entidad_fecha(db_engine):
    inspector = inspect(db_engine)
    columnas = {columna["name"] for columna in inspector.get_columns("auditoria")}
    assert "rol" in columnas
    indices = {
        indice["name"]: indice["column_names"]
        for indice in inspector.get_indexes("auditoria")
    }
    assert indices["ix_auditoria_entidad_fecha_hora"] == ["entidad", "fecha_hora"]


def _registrar(db, usuario) -> Auditoria:
    registro = Auditoria(
        usuario_id=usuario.id,
        rol=usuario.rol.codigo,
        entidad="convenio",
        registro_id=1,
        accion=AccionAuditoria.UPDATE.value,
        campo="objeto",
        valor_anterior="antes",
        valor_nuevo="después",
    )
    db.add(registro)
    db.commit()
    return registro


def test_auditoria_guarda_el_rol_del_responsable(db, crear_usuario):
    usuario = crear_usuario(CodigoRol.GESTOR_ORI)
    registro = _registrar(db, usuario)
    db.expire_all()
    assert db.get(Auditoria, registro.id).rol == CodigoRol.GESTOR_ORI.value


def test_auditoria_no_admite_sobrescribir_registros(db, crear_usuario):
    registro = _registrar(db, crear_usuario(CodigoRol.ADMINISTRADOR_ORI))
    with pytest.raises(DBAPIError, match="no admite"):
        db.execute(
            text("UPDATE auditoria SET valor_nuevo = 'alterado' WHERE id = :id"),
            {"id": registro.id},
        )
    db.rollback()
