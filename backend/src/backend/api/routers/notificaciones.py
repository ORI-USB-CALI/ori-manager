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

from backend.api.deps import UsuarioActual, get_session_token
from backend.core.config import settings
from backend.db.session import get_db
from backend.models.notificacion import Notificacion
from backend.schemas.notificacion import NotificacionLeer
from backend.services.notificaciones import (
    NotificacionNoEncontrada,
    ServicioNotificaciones,
)
from backend.services.notificaciones_realtime import (
    EmisorTicketsWebSocket,
    GestorNotificacionesTiempoReal,
    get_emisor_tickets_ws,
    get_gestor_notificaciones_tiempo_real,
)
from backend.services.sesiones import RepositorioSesiones, get_repositorio_sesiones

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])
DatabaseSession = Annotated[Session, Depends(get_db)]
GestorTiempoReal = Annotated[
    GestorNotificacionesTiempoReal, Depends(get_gestor_notificaciones_tiempo_real)
]
EmisorTickets = Annotated[
    EmisorTicketsWebSocket, Depends(get_emisor_tickets_ws)
]
Sesiones = Annotated[RepositorioSesiones, Depends(get_repositorio_sesiones)]
SesionToken = Annotated[str, Depends(get_session_token)]

INTERVALO_SONDEO_SEGUNDOS = 2
# Cada cuántos sondeos se revalida que la sesión original siga vigente, sin
# mantener ninguna conexión de base de datos abierta mientras tanto (punto 3
# de la revisión: ciclo de vida de la conexión). RepositorioSesiones vive en
# memoria, así que esta revalidación no toca Postgres en absoluto.
SONDEOS_POR_REVALIDACION = 15


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


@router.post("/ws-ticket")
def emitir_ticket_websocket(
    usuario: UsuarioActual, token: SesionToken, emisor: EmisorTickets
) -> dict[str, str]:
    """HU-33 tarea 5 (ajuste de code review).

    En Render el frontend (static site) no puede alojar ni hacer proxy de
    un WebSocket, así que el cliente conecta directo a la URL pública del
    backend — un origen distinto al del frontend, donde la cookie de
    sesión no viaja. Esta llamada sí es del mismo origen (pasa por el
    rewrite /api/* del frontend), así que la cookie funciona aquí; devuelve
    un ticket de un solo uso que el cliente manda como query param al abrir
    el WebSocket, en vez de depender de la cookie para esa conexión.

    El ticket lleva también el token de sesión (no solo el usuario_id) para
    que el WebSocket pueda revalidar contra la sesión real mientras dure la
    conexión, y cerrarla si esa sesión expira o se invalida (ver
    `_sesion_valida`), sin necesidad de volver a depender de la cookie.
    """
    return {"ticket": emisor.emitir(usuario.id, token)}


def _sesion_valida(sesiones: RepositorioSesiones, token: str) -> bool:
    """Consulta en memoria, sin tocar Postgres: el WebSocket nunca debe
    mantener una sesión ni una transacción de base de datos abiertas
    mientras dure la conexión (punto 3 de la revisión).
    """
    return sesiones.obtener_por_token(token) is not None


@router.websocket("/ws")
async def notificaciones_tiempo_real(
    websocket: WebSocket,
    gestor: GestorTiempoReal,
    emisor: EmisorTickets,
    sesiones: Sesiones,
) -> None:
    """HU-33 tarea 5. No empuja el contenido de la notificación: avisa que
    algo cambió para que el cliente vuelva a pedir GET /notificaciones. Así
    el canal en tiempo real no duplica la autorización ni el formato que ya
    resuelve la API REST.

    Se autentica con un ticket de un solo uso (ver `emitir_ticket_websocket`),
    no con la cookie de sesión: en Render esta conexión llega directo al
    backend, en un origen distinto al del frontend, y la cookie no viaja
    entre orígenes. Mientras la conexión sigue abierta, se revalida
    periódicamente que la sesión original siga vigente (ni expirada ni
    invalidada por un cambio de estado del usuario), para contemplar
    desconexiones, expiración de sesión y reconexiones.
    """
    origen = websocket.headers.get("origin")
    if settings.public_frontend_url and origen and origen != settings.public_frontend_url:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    ticket = websocket.query_params.get("ticket")
    entrada = emisor.consumir(ticket) if ticket else None
    if entrada is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    usuario_id, token_sesion = entrada
    if not _sesion_valida(sesiones, token_sesion):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    vista = gestor.version_actual(usuario_id)
    sondeos_desde_revalidacion = 0
    try:
        while True:
            await asyncio.sleep(INTERVALO_SONDEO_SEGUNDOS)
            sondeos_desde_revalidacion += 1
            if sondeos_desde_revalidacion >= SONDEOS_POR_REVALIDACION:
                sondeos_desde_revalidacion = 0
                if not _sesion_valida(sesiones, token_sesion):
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return
            actual = gestor.version_actual(usuario_id)
            if actual != vista:
                vista = actual
                await websocket.send_json({"evento": "notificaciones_actualizadas"})
    except WebSocketDisconnect:
        pass
