"""Presentación compartida; recibe texto plano y enlaces construidos por servicios.

No envía mensajes ni transforma URLs, tokens, destinatarios o vigencias.
"""

from collections.abc import Sequence
from html import escape


def correo_institucional(
    *,
    titulo: str,
    contenido: str,
    enlace: str,
    accion: str,
    vigencia: str,
    seguridad: str,
    contexto: Sequence[tuple[str, str]] = (),
) -> str:
    """Todos los parámetros son texto, nunca fragmentos HTML sin escapar."""
    filas = "".join(
        '<tr><td style="padding:8px 0;border-bottom:1px solid #e2e8f0;'
        'overflow-wrap:anywhere;word-break:break-word">'
        f'<span style="color:#5a626a;font-size:14px">{escape(etiqueta)}</span><br>'
        f"<strong>{escape(valor)}</strong></td></tr>"
        for etiqueta, valor in contexto
    )
    datos = (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"'
        f' style="border-collapse:collapse;margin:16px 0">{filas}</table>'
        if filas
        else ""
    )
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(titulo)}</title></head>"
        '<body style="margin:0;padding:0;background:#f8f9fa;color:#1a1d20;'
        'font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.6">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"'
        ' style="border-collapse:collapse"><tr><td align="center" style="padding:16px 12px">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"'
        ' style="max-width:600px;border-collapse:collapse;background:#ffffff">'
        '<tr><td style="padding:24px;border-top:4px solid #d91a2a;'
        'border-bottom:1px solid #e2e8f0">'
        '<strong style="font-size:24px;color:#d91a2a">ORI Manager</strong><br>'
        '<span style="font-size:14px">Universidad de San Buenaventura Cali</span><br>'
        '<span style="font-size:14px;color:#5a626a">Oficina de Relaciones Interinstitucionales</span>'
        '</td></tr><tr><td style="padding:24px;overflow-wrap:anywhere;word-break:break-word">'
        f'<h1 style="margin:0 0 16px;font-size:24px;line-height:1.3">{escape(titulo)}</h1>'
        f'<p style="margin:0 0 16px">{escape(contenido)}</p>{datos}'
        '<table role="presentation" cellspacing="0" cellpadding="0"'
        ' style="margin:24px 0;border-collapse:collapse"><tr>'
        '<td bgcolor="#d91a2a" style="border-radius:6px;text-align:center">'
        f'<a href="{escape(enlace, quote=True)}" style="display:inline-block;'
        "padding:12px 20px;border:1px solid #d91a2a;border-radius:6px;"
        'color:#ffffff;background:#d91a2a;font-weight:bold;text-decoration:underline">'
        f"{escape(accion)}</a></td></tr></table>"
        f'<p style="margin:0 0 12px;font-weight:bold">{escape(vigencia)}</p>'
        f'<p style="margin:0;color:#5a626a;font-size:14px">{escape(seguridad)}</p>'
        '</td></tr><tr><td style="padding:20px 24px;background:#f8f9fa;'
        'border-top:1px solid #e2e8f0;color:#5a626a;font-size:13px">'
        "Universidad de San Buenaventura Cali · ORI<br>"
        "Comunicación transaccional de ORI Manager."
        "</td></tr></table></td></tr></table></body></html>"
    )
