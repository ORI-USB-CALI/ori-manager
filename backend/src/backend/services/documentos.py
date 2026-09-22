from __future__ import annotations

from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Protocol

from backend.core.config import settings
from backend.models.enums import TipoDocumentoSolicitud

TAMANO_MAXIMO_DOCUMENTO = 10 * 1024 * 1024
TIPOS_MIME_PERMITIDOS = frozenset({"application/pdf", "image/jpeg", "image/png"})
EXTENSIONES_PERMITIDAS = frozenset({".pdf", ".jpg", ".jpeg", ".png"})
TIPOS_DOCUMENTO_REPRESENTACION = frozenset(
    {
        TipoDocumentoSolicitud.CAMARA_COMERCIO,
        TipoDocumentoSolicitud.RUT,
        TipoDocumentoSolicitud.CEDULA_REPRESENTANTE_LEGAL,
        TipoDocumentoSolicitud.OTRO_DOCUMENTO_REPRESENTACION,
    }
)


class AlmacenDocumentos(Protocol):
    def guardar(self, clave: str, contenido: bytes) -> None: ...
    def eliminar(self, clave: str) -> None: ...
    def existe(self, clave: str) -> bool: ...


class AlmacenDocumentosLocal:
    """Adaptador local de desarrollo; las claves nunca provienen del nombre cargado."""

    def __init__(self, raiz: str | Path):
        self.raiz = Path(raiz).resolve()
        self.raiz.mkdir(parents=True, exist_ok=True)

    def _ruta(self, clave: str) -> Path:
        partes = PurePosixPath(clave).parts
        if not partes or any(parte in {"", ".", ".."} for parte in partes):
            raise ValueError("Clave de almacenamiento inválida")
        ruta = self.raiz.joinpath(*partes).resolve()
        if not ruta.is_relative_to(self.raiz):
            raise ValueError("Clave de almacenamiento fuera de la raíz")
        return ruta

    def guardar(self, clave: str, contenido: bytes) -> None:
        ruta = self._ruta(clave)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(f"{ruta.suffix}.tmp")
        temporal.write_bytes(contenido)
        temporal.replace(ruta)

    def eliminar(self, clave: str) -> None:
        ruta = self._ruta(clave)
        ruta.unlink(missing_ok=True)

    def existe(self, clave: str) -> bool:
        return self._ruta(clave).is_file()


@lru_cache
def get_almacen_documentos() -> AlmacenDocumentos:
    if settings.app_env != "development":
        raise RuntimeError(
            "No hay un proveedor documental durable configurado para este ambiente"
        )
    return AlmacenDocumentosLocal(settings.document_storage_path)
