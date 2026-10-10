import asyncio
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from backend.api.deps import UsuarioActual
from backend.db.session import get_db
from backend.models.notificacion import Notificacion
from backend.schemas.notificacion import NotificacionLeer
from backend.services.notificaciones import (
    NotificacionNoEncontrada,
    ServicioNotificaciones,
)
from backend.services.notificaciones_realtime import (
    GestorNotificacionesTiempoReal,
    get_gestor_notificaciones_tiempo_real,
)

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])
DatabaseSession = Annotated[Session, Depends(get_db)]
GestorTiempoReal = Annotated[
    GestorNotificacionesTiempoReal, Depends(get_gestor_notificaciones_tiempo_real)
]

INTERVALO_SONDEO_SEGUNDOS = 2


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


@router.websocket("/ws")
async def notificaciones_tiempo_real(
    websocket: WebSocket,
    usuario: UsuarioActual,
    gestor: GestorTiempoReal,
) -> None:
    """HU-33 tarea 5. No empuja el contenido de la notificación: avisa que
    algo cambió para que el cliente vuelva a pedir GET /notificaciones. Así
    el canal en tiempo real no duplica la autorización ni el formato que ya
    resuelve la API REST.
    """
    await websocket.accept()
    vista = gestor.version_actual(usuario.id)
    try:
        while True:
            await asyncio.sleep(INTERVALO_SONDEO_SEGUNDOS)
            actual = gestor.version_actual(usuario.id)
            if actual != vista:
                vista = actual
                await websocket.send_json({"evento": "notificaciones_actualizadas"})
    except WebSocketDisconnect:
        pass
