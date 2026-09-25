from __future__ import annotations

from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Protocol
from urllib.parse import quote

import httpx

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
    def leer(self, clave: str) -> bytes: ...
    def eliminar(self, clave: str) -> None: ...
    def existe(self, clave: str) -> bool: ...


class ErrorAlmacenDocumentos(RuntimeError):
    """Error explícito de acceso al almacenamiento documental durable."""


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

    def leer(self, clave: str) -> bytes:
        ruta = self._ruta(clave)
        try:
            return ruta.read_bytes()
        except OSError as exc:
            raise ErrorAlmacenDocumentos(
                "El documento almacenado no está disponible"
            ) from exc

    def eliminar(self, clave: str) -> None:
        ruta = self._ruta(clave)
        ruta.unlink(missing_ok=True)

    def existe(self, clave: str) -> bool:
        return self._ruta(clave).is_file()


class AlmacenDocumentosMicrosoftGraph:
    TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    GRAPH_URL = "https://graph.microsoft.com/v1.0"
    SCOPE = "https://graph.microsoft.com/Files.ReadWrite.AppFolder offline_access"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        storage_root: str,
        *,
        cliente: httpx.Client | None = None,
    ):
        if storage_root not in {"staging", "production"}:
            raise ValueError("MICROSOFT_STORAGE_ROOT debe ser staging o production")
        self.storage_root = storage_root
        self.cliente = cliente or httpx.Client(timeout=30.0, follow_redirects=True)
        self._credenciales = (client_id, client_secret, refresh_token)
        self._headers = {"Authorization": f"Bearer {self._obtener_token()}"}
        approot = self._json(
            self._solicitar("GET", "/me/drive/special/approot"), "AppFolder"
        )
        try:
            self._drive_id = approot["parentReference"]["driveId"]
            approot_id = approot["id"]
        except (KeyError, TypeError) as exc:
            raise ErrorAlmacenDocumentos(
                "Microsoft Graph devolvió un AppFolder inválido"
            ) from exc
        raiz = self._json(
            self._solicitar("GET", self._ruta_item(approot_id, (storage_root,))),
            "raíz de almacenamiento",
        )
        try:
            self._root_id = raiz["id"]
        except (KeyError, TypeError) as exc:
            raise ErrorAlmacenDocumentos(
                "Microsoft Graph devolvió una raíz de almacenamiento inválida"
            ) from exc

    def _obtener_token(self) -> str:
        client_id, client_secret, refresh_token = self._credenciales
        try:
            respuesta = self.cliente.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "scope": self.SCOPE,
                },
            )
            respuesta.raise_for_status()
            token = respuesta.json()["access_token"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ErrorAlmacenDocumentos(
                "No fue posible obtener el token de Microsoft Graph"
            ) from exc
        if not isinstance(token, str) or not token:
            raise ErrorAlmacenDocumentos(
                "Microsoft Graph no devolvió un access token válido"
            )
        return token

    def _solicitar(
        self, metodo: str, ruta: str, *, aceptar_404: bool = False, **kwargs
    ) -> httpx.Response:
        try:
            headers = {**self._headers, **kwargs.pop("headers", {})}
            respuesta = self.cliente.request(
                metodo,
                f"{self.GRAPH_URL}{ruta}",
                headers=headers,
                **kwargs,
            )
            if respuesta.status_code == 401:
                self._headers = {"Authorization": f"Bearer {self._obtener_token()}"}
                headers["Authorization"] = self._headers["Authorization"]
                respuesta = self.cliente.request(
                    metodo,
                    f"{self.GRAPH_URL}{ruta}",
                    headers=headers,
                    **kwargs,
                )
            if aceptar_404 and respuesta.status_code == 404:
                return respuesta
            respuesta.raise_for_status()
            return respuesta
        except httpx.HTTPError as exc:
            raise ErrorAlmacenDocumentos(
                f"Microsoft Graph falló al ejecutar {metodo} sobre el almacenamiento"
            ) from exc

    @staticmethod
    def _json(respuesta: httpx.Response, recurso: str) -> dict:
        try:
            datos = respuesta.json()
        except ValueError as exc:
            raise ErrorAlmacenDocumentos(
                f"Microsoft Graph devolvió {recurso} sin JSON válido"
            ) from exc
        if not isinstance(datos, dict):
            raise ErrorAlmacenDocumentos(
                f"Microsoft Graph devolvió {recurso} con formato inválido"
            )
        return datos

    @staticmethod
    def _partes(clave: str) -> tuple[str, ...]:
        if not clave or clave.startswith(("/", "\\")) or "\\" in clave:
            raise ValueError("Clave de almacenamiento inválida")
        partes = tuple(clave.split("/"))
        if any(parte in {"", ".", ".."} for parte in partes):
            raise ValueError("Clave de almacenamiento inválida")
        return partes

    def _ruta_item(self, item_id: str, partes: tuple[str, ...]) -> str:
        ruta = "/".join(quote(parte, safe="") for parte in partes)
        return f"/drives/{quote(self._drive_id, safe='')}/items/{quote(item_id, safe='')}:/{ruta}"

    def _buscar(self, partes: tuple[str, ...]) -> httpx.Response:
        return self._solicitar(
            "GET", self._ruta_item(self._root_id, partes), aceptar_404=True
        )

    def guardar(self, clave: str, contenido: bytes) -> None:
        partes = self._partes(clave)
        parent_id = self._root_id
        for carpeta in partes[:-1]:
            respuesta = self._solicitar(
                "GET", self._ruta_item(parent_id, (carpeta,)), aceptar_404=True
            )
            if respuesta.status_code == 404:
                respuesta = self._solicitar(
                    "POST",
                    f"/drives/{quote(self._drive_id, safe='')}/items/"
                    f"{quote(parent_id, safe='')}/children",
                    json={
                        "name": carpeta,
                        "folder": {},
                        "@microsoft.graph.conflictBehavior": "fail",
                    },
                )
            try:
                parent_id = respuesta.json()["id"]
            except (KeyError, TypeError, ValueError) as exc:
                raise ErrorAlmacenDocumentos(
                    "Microsoft Graph devolvió una carpeta inválida"
                ) from exc
        self._solicitar(
            "PUT",
            f"{self._ruta_item(parent_id, (partes[-1],))}:/content",
            content=contenido,
            headers={"Content-Type": "application/octet-stream"},
        )

    def existe(self, clave: str) -> bool:
        return self._buscar(self._partes(clave)).status_code != 404

    def leer(self, clave: str) -> bytes:
        respuesta = self._buscar(self._partes(clave))
        if respuesta.status_code == 404:
            raise ErrorAlmacenDocumentos(
                "El documento almacenado no está disponible"
            )
        try:
            item_id = respuesta.json()["id"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ErrorAlmacenDocumentos(
                "Microsoft Graph devolvió un documento inválido"
            ) from exc
        return self._solicitar(
            "GET",
            f"/drives/{quote(self._drive_id, safe='')}/items/"
            f"{quote(item_id, safe='')}/content",
        ).content

    def eliminar(self, clave: str) -> None:
        respuesta = self._buscar(self._partes(clave))
        if respuesta.status_code == 404:
            return
        try:
            item_id = respuesta.json()["id"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ErrorAlmacenDocumentos(
                "Microsoft Graph devolvió un documento inválido"
            ) from exc
        self._solicitar(
            "DELETE",
            f"/drives/{quote(self._drive_id, safe='')}/items/{quote(item_id, safe='')}",
        )


@lru_cache
def get_almacen_documentos() -> AlmacenDocumentos:
    proveedor = settings.document_storage_provider
    if proveedor == "local":
        if settings.app_env != "development":
            raise RuntimeError(
                "DOCUMENT_STORAGE_PROVIDER=local solo está permitido en development"
            )
        return AlmacenDocumentosLocal(settings.document_storage_path)
    if proveedor != "microsoft_graph":
        raise RuntimeError("DOCUMENT_STORAGE_PROVIDER debe ser local o microsoft_graph")
    configuracion: dict[str, str | None] = {
        "MICROSOFT_CLIENT_ID": settings.microsoft_client_id,
        "MICROSOFT_CLIENT_SECRET": (
            settings.microsoft_client_secret.get_secret_value()
            if settings.microsoft_client_secret is not None
            else None
        ),
        "MICROSOFT_REFRESH_TOKEN": (
            settings.microsoft_refresh_token.get_secret_value()
            if settings.microsoft_refresh_token is not None
            else None
        ),
        "MICROSOFT_STORAGE_ROOT": settings.microsoft_storage_root,
    }
    faltantes = [nombre for nombre, valor in configuracion.items() if not valor]
    if faltantes:
        raise RuntimeError(
            "Configuración incompleta de Microsoft Graph: " + ", ".join(faltantes)
        )
    if settings.microsoft_storage_root not in {"staging", "production"}:
        raise RuntimeError("MICROSOFT_STORAGE_ROOT debe ser staging o production")
    return AlmacenDocumentosMicrosoftGraph(
        client_id=configuracion["MICROSOFT_CLIENT_ID"],
        client_secret=configuracion["MICROSOFT_CLIENT_SECRET"],
        refresh_token=configuracion["MICROSOFT_REFRESH_TOKEN"],
        storage_root=settings.microsoft_storage_root,
    )
