from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import httpx

from backend.core.config import settings

BREVO_EMAIL_URL = "https://api.brevo.com/v3/smtp/email"


@dataclass(frozen=True)
class MensajeCorreo:
    destinatario: str
    asunto: str
    texto: str
    html: str


class EnviadorCorreo(Protocol):
    def enviar(self, mensaje: MensajeCorreo) -> None: ...


class ErrorEnvioCorreo(Exception):
    pass


class CorreoLocal:
    """Adaptador sin red para desarrollo y pruebas."""

    def __init__(self) -> None:
        self.mensajes: list[MensajeCorreo] = []

    def enviar(self, mensaje: MensajeCorreo) -> None:
        self.mensajes.append(mensaje)


class CorreoBrevo:
    def __init__(
        self,
        api_key: str,
        remitente_correo: str,
        remitente_nombre: str,
        cliente: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._remitente_correo = remitente_correo
        self._remitente_nombre = remitente_nombre
        self._cliente = cliente or httpx.Client(timeout=15.0)

    def enviar(self, mensaje: MensajeCorreo) -> None:
        try:
            respuesta = self._cliente.post(
                BREVO_EMAIL_URL,
                headers={
                    "api-key": self._api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "sender": {
                        "name": self._remitente_nombre,
                        "email": self._remitente_correo,
                    },
                    "to": [{"email": mensaje.destinatario}],
                    "subject": mensaje.asunto,
                    "htmlContent": mensaje.html,
                    "textContent": mensaje.texto,
                },
            )
            respuesta.raise_for_status()
        except httpx.HTTPError as exc:
            raise ErrorEnvioCorreo(
                "No fue posible enviar el correo transaccional"
            ) from exc


@lru_cache
def get_enviador_correo() -> EnviadorCorreo:
    proveedor = settings.email_provider
    if proveedor == "local":
        if settings.app_env != "development":
            raise RuntimeError(
                "EMAIL_PROVIDER=local solo está permitido en development"
            )
        return CorreoLocal()
    if proveedor != "brevo":
        raise RuntimeError("EMAIL_PROVIDER debe ser local o brevo")

    configuracion = {
        "BREVO_API_KEY": (
            settings.brevo_api_key.get_secret_value()
            if settings.brevo_api_key is not None
            else None
        ),
        "EMAIL_FROM_ADDRESS": settings.email_from_address,
        "EMAIL_FROM_NAME": settings.email_from_name,
        "PUBLIC_FRONTEND_URL": settings.public_frontend_url,
    }
    faltantes = [nombre for nombre, valor in configuracion.items() if not valor]
    if faltantes:
        raise RuntimeError(
            "Configuración incompleta de correo Brevo: " + ", ".join(faltantes)
        )
    return CorreoBrevo(
        api_key=configuracion["BREVO_API_KEY"],
        remitente_correo=configuracion["EMAIL_FROM_ADDRESS"],
        remitente_nombre=configuracion["EMAIL_FROM_NAME"],
    )
