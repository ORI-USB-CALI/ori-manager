import sys
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.rol import Rol
from backend.models.usuario import Usuario
from backend.scripts import crear_admin


def test_crear_primer_admin(db: Session, monkeypatch, capsys) -> None:
    @contextmanager
    def session_local():
        yield db

    monkeypatch.setattr(crear_admin, "SessionLocal", session_local)
    monkeypatch.setattr(crear_admin.getpass, "getpass", lambda _: "ClaveAdmin123")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crear_admin",
            "--correo",
            "primer.admin@example.com",
            "--nombre",
            "Primer Admin",
        ],
    )

    crear_admin.main()

    usuario = db.scalar(
        select(Usuario).where(Usuario.correo == "primer.admin@example.com")
    )
    assert usuario is not None
    assert usuario.nombre_completo == "Primer Admin"
    assert usuario.tipo_usuario == TipoUsuario.INTERNO.value
    assert usuario.rol.codigo == CodigoRol.ADMINISTRADOR_ORI.value
    assert usuario.activo
    assert "creado" in capsys.readouterr().out


def test_promover_usuario_existente_mantiene_datos(
    db: Session,
    crear_usuario,
    monkeypatch,
) -> None:
    usuario = crear_usuario(
        CodigoRol.GESTOR_ORI,
        activo=False,
        correo="promover@example.com",
    )
    nombre_original = usuario.nombre_completo

    @contextmanager
    def session_local():
        yield db

    monkeypatch.setattr(crear_admin, "SessionLocal", session_local)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crear_admin",
            "--correo",
            usuario.correo,
            "--nombre",
            "Nombre ignorado",
        ],
    )

    crear_admin.main()
    db.refresh(usuario)
    rol_admin = db.scalar(
        select(Rol).where(Rol.codigo == CodigoRol.ADMINISTRADOR_ORI.value)
    )

    assert usuario.rol == rol_admin
    assert usuario.activo
    assert usuario.nombre_completo == nombre_original
