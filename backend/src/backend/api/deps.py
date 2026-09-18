from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.core.permisos import PERMISOS_POR_ROL, Permiso
from backend.core.roles import CodigoRol
from backend.db.session import get_db
from backend.models.usuario import Usuario
from backend.services.sesiones import (
    RepositorioSesiones,
    get_repositorio_sesiones,
)


def get_session_token(
    session_id: Annotated[str | None, Cookie(alias="session_id")] = None,
) -> str:
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
        )
    return session_id


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str, Depends(get_session_token)],
    sesiones: Annotated[RepositorioSesiones, Depends(get_repositorio_sesiones)],
) -> Usuario:
    sesion = sesiones.obtener_por_token(token)
    if sesion is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
        )

    usuario = db.scalar(
        select(Usuario)
        .options(joinedload(Usuario.rol))
        .where(Usuario.id == sesion.usuario_id)
    )
    if usuario is None:
        sesiones.invalidar(token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida",
        )
    if not usuario.activo:
        sesiones.invalidar(token)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )
    return usuario


UsuarioActual = Annotated[Usuario, Depends(get_current_user)]


def permisos_de_usuario(usuario: Usuario) -> frozenset[Permiso]:
    try:
        codigo = CodigoRol(usuario.rol.codigo)
        return PERMISOS_POR_ROL[codigo]
    except (AttributeError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol sin permisos reconocidos",
        ) from exc


def requiere(permiso: Permiso):
    def verificar(usuario: UsuarioActual) -> Usuario:
        if permiso not in permisos_de_usuario(usuario):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permiso para esta operación",
            )
        return usuario

    return Depends(verificar)
