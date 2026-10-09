from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import UsuarioActual
from backend.db.session import get_db
from backend.models.notificacion import Notificacion
from backend.schemas.notificacion import NotificacionLeer
from backend.services.notificaciones import (
    NotificacionNoEncontrada,
    ServicioNotificaciones,
)

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[NotificacionLeer])
def listar_mis_notificaciones(
    db: DatabaseSession,
    usuario: UsuarioActual,
) -> list[Notificacion]:
    return ServicioNotificaciones(db).listar_para_usuario(usuario)


@router.patch("/{notificacion_id}/leida", response_model=NotificacionLeer)
def marcar_notificacion_leida(
    notificacion_id: int,
    db: DatabaseSession,
    usuario: UsuarioActual,
) -> Notificacion:
    try:
        return ServicioNotificaciones(db).marcar_leida(notificacion_id, usuario)
    except NotificacionNoEncontrada as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No existe esa notificación"
        ) from exc
