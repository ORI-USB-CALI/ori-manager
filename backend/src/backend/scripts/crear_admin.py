"""Crea el primer administrador, o promueve a administrador un usuario existente.

Uso: uv run python -m backend.scripts.crear_admin --email admin@usb.edu.co
"""

import argparse
import getpass

from sqlalchemy import select

from backend.core.permisos import Rol
from backend.core.security import get_password_hash, validar_password
from backend.db.session import SessionLocal
from backend.models.session import Session  # noqa: F401  (resuelve User.sessions)
from backend.models.user import User


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    email = parser.parse_args().email

    with SessionLocal() as db:
        usuario = db.scalars(select(User).where(User.email == email)).one_or_none()
        if usuario is None:
            try:
                password = validar_password(getpass.getpass("Contraseña: "))
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            usuario = User(email=email, hashed_password=get_password_hash(password))
            db.add(usuario)
            accion = "creado"
        else:
            accion = "promovido"
        usuario.rol = Rol.ADMINISTRADOR
        usuario.is_active = True
        db.commit()

    print(f"Administrador {accion}: {email}")


if __name__ == "__main__":
    main()
