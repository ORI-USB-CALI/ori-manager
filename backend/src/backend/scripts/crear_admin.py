"""Crea el primer administrador o promueve un usuario interno existente."""

import argparse
import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import hash_contrasena
from backend.db.session import SessionLocal
from backend.models.rol import Rol
from backend.models.usuario import Usuario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--correo", required=True)
    parser.add_argument("--nombre", required=True)
    argumentos = parser.parse_args()

    try:
        correo = str(TypeAdapter(EmailStr).validate_python(argumentos.correo))
    except ValidationError as exc:
        raise SystemExit("El correo no es válido") from exc

    with SessionLocal() as db:
        rol = db.scalar(
            select(Rol).where(Rol.codigo == CodigoRol.ADMINISTRADOR_ORI.value)
        )
        if rol is None:
            raise SystemExit(
                "No existe ADMINISTRADOR_ORI; aplique primero las migraciones"
            )
        if not rol.activo:
            raise SystemExit("El rol ADMINISTRADOR_ORI está inactivo")

        usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
        if usuario is None:
            contrasena = getpass.getpass("Contraseña: ")
            try:
                contrasena_hash = hash_contrasena(contrasena)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            usuario = Usuario(
                correo=correo,
                hash_contrasena=contrasena_hash,
                nombre_completo=argumentos.nombre,
                rol=rol,
                tipo_usuario=TipoUsuario.INTERNO.value,
                activo=True,
            )
            db.add(usuario)
            accion = "creado"
        else:
            if usuario.tipo_usuario != TipoUsuario.INTERNO.value:
                raise SystemExit(
                    "No se puede promover un usuario externo a un rol interno"
                )
            usuario.rol = rol
            usuario.activo = True
            accion = "promovido"
        db.commit()

    print(f"Administrador {accion}: {correo}")


if __name__ == "__main__":
    main()
