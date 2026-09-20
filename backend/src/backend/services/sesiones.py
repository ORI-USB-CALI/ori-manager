from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol

from backend.core.security import digest_token_sesion


@dataclass(frozen=True, slots=True)
class Sesion:
    usuario_id: int
    token_digest: str
    expira_en: datetime


class RepositorioSesiones(Protocol):
    def crear(self, usuario_id: int, token: str, expira_en: datetime) -> Sesion: ...

    def obtener_por_token(self, token: str) -> Sesion | None: ...

    def invalidar(self, token: str) -> bool: ...

    def invalidar_usuario(self, usuario_id: int) -> int: ...

    def eliminar_expiradas(self, ahora: datetime | None = None) -> int: ...


class RepositorioSesionesMemoria:
    def __init__(self) -> None:
        self._sesiones: dict[str, Sesion] = {}
        self._lock = RLock()

    def crear(self, usuario_id: int, token: str, expira_en: datetime) -> Sesion:
        token_digest = digest_token_sesion(token)
        sesion = Sesion(
            usuario_id=usuario_id,
            token_digest=token_digest,
            expira_en=expira_en,
        )
        with self._lock:
            self._sesiones[token_digest] = sesion
        return sesion

    def obtener_por_token(self, token: str) -> Sesion | None:
        token_digest = digest_token_sesion(token)
        with self._lock:
            sesion = self._sesiones.get(token_digest)
            if sesion is None:
                return None
            if sesion.expira_en <= datetime.now(UTC):
                self._sesiones.pop(token_digest, None)
                return None
            return sesion

    def invalidar(self, token: str) -> bool:
        token_digest = digest_token_sesion(token)
        with self._lock:
            return self._sesiones.pop(token_digest, None) is not None

    def invalidar_usuario(self, usuario_id: int) -> int:
        with self._lock:
            digests = [
                token_digest
                for token_digest, sesion in self._sesiones.items()
                if sesion.usuario_id == usuario_id
            ]
            for token_digest in digests:
                del self._sesiones[token_digest]
            return len(digests)

    def eliminar_expiradas(self, ahora: datetime | None = None) -> int:
        instante = ahora or datetime.now(UTC)
        with self._lock:
            digests = [
                token_digest
                for token_digest, sesion in self._sesiones.items()
                if sesion.expira_en <= instante
            ]
            for token_digest in digests:
                del self._sesiones[token_digest]
            return len(digests)

    def limpiar(self) -> None:
        with self._lock:
            self._sesiones.clear()


repositorio_sesiones = RepositorioSesionesMemoria()


def get_repositorio_sesiones() -> RepositorioSesiones:
    return repositorio_sesiones
