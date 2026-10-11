import secrets
from datetime import UTC, datetime, timedelta
from threading import Lock

DURACION_TICKET_WS = timedelta(seconds=20)


class EmisorTicketsWebSocket:
    """HU-33 tarea 5 (ajuste de code review).

    En Render el frontend es un static site: no puede alojar ni hacer
    proxy de un WebSocket (solo puede iniciar conexiones salientes hacia
    la URL pública del backend). Eso vuelve la conexión del WS un origen
    distinto al del frontend, y la cookie de sesión —que el navegador
    asoció al dominio del frontend cuando se hizo login a través del
    rewrite /api/*— no viaja a un dominio distinto.

    Por eso el WS no se autentica con la cookie: el frontend primero pide
    un ticket de un solo uso por REST (esa llamada sí es mismo origen, la
    cookie sí funciona ahí) y lo manda como query param al conectar el
    WebSocket directo al backend. El ticket expira rápido y se consume una
    sola vez, para que no sirva de credencial de sesión por sí solo.
    """

    def __init__(self) -> None:
        self._tickets: dict[str, tuple[int, str, datetime]] = {}
        self._lock = Lock()

    def emitir(self, usuario_id: int, token_sesion: str) -> str:
        ticket = secrets.token_urlsafe(32)
        ahora = datetime.now(UTC)
        with self._lock:
            self._tickets = {
                t: v for t, v in self._tickets.items() if v[2] > ahora
            }
            self._tickets[ticket] = (usuario_id, token_sesion, ahora + DURACION_TICKET_WS)
        return ticket

    def consumir(self, ticket: str) -> tuple[int, str] | None:
        """Devuelve (usuario_id, token_sesion) y consume el ticket. El
        token de sesión se reenvía para que el WebSocket pueda revalidar
        contra `RepositorioSesiones` mientras dure la conexión (ver
        `_sesion_valida` en el router): el ticket solo prueba la identidad
        al conectar, no sustituye el control de expiración de la sesión.
        """
        with self._lock:
            entrada = self._tickets.pop(ticket, None)
        if entrada is None:
            return None
        usuario_id, token_sesion, expira_en = entrada
        if expira_en <= datetime.now(UTC):
            return None
        return usuario_id, token_sesion


emisor_tickets_ws = EmisorTicketsWebSocket()


def get_emisor_tickets_ws() -> EmisorTicketsWebSocket:
    return emisor_tickets_ws


class GestorNotificacionesTiempoReal:
    """HU-33 tarea 5: WebSocket nativo de FastAPI (no SignalR, fuera del stack).

    No reenvía el contenido de la notificación: solo lleva un contador por
    usuario que el endpoint de WebSocket sondea periódicamente. Cuando
    cambia, el cliente sabe que debe refrescar su lista vía la API REST ya
    existente (GET /notificaciones). Evita duplicar la lógica de
    autorización/formato de esa API dentro del canal en tiempo real.
    """

    def __init__(self) -> None:
        self._version: dict[int, int] = {}
        self._lock = Lock()

    def marcar_cambio(self, usuario_id: int) -> None:
        with self._lock:
            self._version[usuario_id] = self._version.get(usuario_id, 0) + 1

    def version_actual(self, usuario_id: int) -> int:
        with self._lock:
            return self._version.get(usuario_id, 0)


gestor_notificaciones_tiempo_real = GestorNotificacionesTiempoReal()


def get_gestor_notificaciones_tiempo_real() -> GestorNotificacionesTiempoReal:
    return gestor_notificaciones_tiempo_real
