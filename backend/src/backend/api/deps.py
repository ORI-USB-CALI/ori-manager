from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.models.enums import RolUsuario

DatabaseSession = Annotated[Session, Depends(get_db)]


def obtener_rol_actual(
    x_rol_usuario: Annotated[str | None, Header()] = None,
) -> RolUsuario:
    """Dependencia temporal: el rol llega por header hasta que exista
    autenticacion real (misma convencion que feature/HU-04-aliados).

    CA-08: si no se indica un rol, o el rol indicado no existe, se
    rechaza la operacion en vez de asumir un rol por defecto.
    """
    if x_rol_usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el header X-Rol-Usuario",
        )
    try:
        return RolUsuario(x_rol_usuario)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rol '{x_rol_usuario}' no es válido",
        ) from exc


RolActual = Annotated[RolUsuario, Depends(obtener_rol_actual)]
