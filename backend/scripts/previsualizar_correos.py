"""Genera cuatro correos ficticios usando los servicios reales y CorreoLocal.

Ejecutar desde backend: uv run python scripts/previsualizar_correos.py --salida RUTA
No consulta la base de datos ni utiliza el proveedor configurado.
"""

import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from backend.services.contraparte_externa import enviar_invitacion_contraparte
from backend.services.correo import CorreoLocal, MensajeCorreo
from backend.services.firma_electronica import ServicioFirmaElectronica
from backend.services.recuperacion_contrasena import ServicioRecuperacionContrasena
from backend.services.verificacion_correo import ServicioVerificacionCorreo


def mensajes_ficticios(
    token: str = "FICTICIO_SIN_VALIDEZ_123",
    referencia: str = "USB-ORI-2026-EJEMPLO",
    cargo: str = "Representante de cooperación académica internacional",
) -> dict[str, MensajeCorreo]:
    local = CorreoLocal()
    db = Mock()
    url = "https://ori.example.invalid"
    usuario = SimpleNamespace(correo="usuario@example.invalid")
    convenio = SimpleNamespace(id=41, codigo=referencia)
    firma = SimpleNamespace(
        correo_firmante="firmante@example.invalid",
        rol_firmante="REPRESENTANTE_LEGAL",
        cargo_firmante=cargo,
    )
    ServicioFirmaElectronica(db, local, url)._enviar(
        SimpleNamespace(),
        token,
        firma,
        convenio,
    )
    enviar_invitacion_contraparte(
        local,
        url,
        SimpleNamespace(
            correo_destino="contraparte@example.invalid",
            correo_cc="copia@example.invalid",
        ),
        token,
        convenio,
    )
    ServicioVerificacionCorreo(db, local, url).enviar(usuario, token)
    ServicioRecuperacionContrasena(db, local, Mock(), url)._enviar(usuario, token)
    return dict(
        zip(
            ("firma", "contraparte", "verificacion", "recuperacion"),
            local.mensajes,
            strict=True,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    destino = parser.parse_args().salida
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, mensaje in mensajes_ficticios().items():
        (destino / f"{nombre}.html").write_text(mensaje.html, encoding="utf-8")
        (destino / f"{nombre}.txt").write_text(mensaje.texto, encoding="utf-8")
