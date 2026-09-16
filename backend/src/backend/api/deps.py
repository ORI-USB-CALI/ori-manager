from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from backend.core.permisos import PERMISOS_POR_ROL, Permiso
from backend.db.session import get_db
from backend.models.user import User
from backend.services.auth import get_valid_session


def get_session_token(session_id: Annotated[str | None, Cookie(alias="session_id")] = None) -> str:
    """Extract session token from HTTP-Only cookie."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return session_id


def get_current_user(
    db: Annotated[DBSession, Depends(get_db)],
    token: Annotated[str, Depends(get_session_token)],
) -> User:
    """Retrieve current user from session token."""
    session_db = get_valid_session(db, token)
    
    if not session_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
        
    if not session_db.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
        
    return session_db.user


UsuarioActual = Annotated[User, Depends(get_current_user)]


def requiere(permiso: Permiso):
    """Dependencia de autorización: 401 sin sesión, 403 si el rol no tiene el permiso."""

    def verificar(usuario: UsuarioActual) -> User:
        if permiso not in PERMISOS_POR_ROL[usuario.rol]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permiso para esta operación",
            )
        return usuario

    return Depends(verificar)
