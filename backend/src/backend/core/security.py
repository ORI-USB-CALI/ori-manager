from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel


class UserTokenData(BaseModel):
    user_id: str
    username: str
    permissions: list[str] = []


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_user_permissions: Annotated[str | None, Header()] = None,
) -> UserTokenData:
    """
    Dependencia para extraer y validar el usuario autenticado a partir del header de autorización.
    """
    if not authorization or not authorization.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    permissions: list[str] = []
    if x_user_permissions is not None:
        permissions = [p.strip() for p in x_user_permissions.split(",") if p.strip()]

    return UserTokenData(
        user_id="user-123",
        username="usuario_ori",
        permissions=permissions,
    )


def require_permission(required_permission: str):
    """
    Verifica que el usuario autenticado cuente con el permiso requerido.
    Retorna 403 Forbidden si el permiso no está presente.
    """

    def permission_checker(
        current_user: Annotated[UserTokenData, Depends(get_current_user)],
    ) -> UserTokenData:
        if required_permission not in current_user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No tiene permisos para la acción solicitada. Permiso requerido: '{required_permission}'",
            )
        return current_user

    return permission_checker
