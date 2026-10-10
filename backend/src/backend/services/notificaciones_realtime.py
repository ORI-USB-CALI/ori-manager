from threading import Lock


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
