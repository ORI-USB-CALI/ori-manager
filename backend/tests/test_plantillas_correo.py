import json
import runpy
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from backend.services.contraparte_externa import VIGENCIA_INVITACION_CONTRAPARTE
from backend.services.correo import CorreoBrevo, ErrorEnvioCorreo
from backend.services.firma_electronica import VIGENCIA_INVITACION_FIRMA
from backend.services.plantillas_correo import correo_institucional
from backend.services.recuperacion_contrasena import VIGENCIA_TOKEN_RECUPERACION
from backend.services.verificacion_correo import VIGENCIA_TOKEN_VERIFICACION

mensajes_ficticios = runpy.run_path("scripts/previsualizar_correos.py")[
    "mensajes_ficticios"
]


class InspeccionHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila = []
        self.enlaces = []
        self.texto = []
        self.etiquetas = []

    def handle_starttag(self, tag, attrs):
        self.etiquetas.append(tag)
        if tag not in {"meta", "br"}:
            self.pila.append(tag)
        if tag == "a":
            self.enlaces.append(dict(attrs)["href"])

    def handle_endtag(self, tag):
        assert self.pila.pop() == tag

    def handle_data(self, data):
        self.texto.append(data)


@pytest.mark.parametrize(
    "nombre,cta,duracion",
    [
        ("firma", "Revisar y firmar", "1 hora"),
        ("contraparte", "Revisar elaboración de convenio", "1 hora"),
        ("verificacion", "Verificar mi correo", "24 horas"),
        ("recuperacion", "Restablecer contraseña", "30 minutos"),
    ],
)
def test_correos_reales_conservan_html_texto_enlaces_y_destinatarios(
    nombre, cta, duracion
):
    token = 'FICTICIO_&<>"_123'
    mensajes = mensajes_ficticios(token=token)
    mensaje = mensajes[nombre]
    html = InspeccionHTML()
    html.feed(mensaje.html)
    assert html.pila == []
    assert "h1" in html.etiquetas and "title" in html.etiquetas
    assert cta in html.texto
    assert "ORI Manager" in mensaje.html
    assert "Universidad de San Buenaventura Cali" in mensaje.html
    assert "Oficina de Relaciones Interinstitucionales" in mensaje.html
    assert duracion in mensaje.html and duracion in mensaje.texto
    assert len(html.enlaces) == 1
    enlace = html.enlaces[0]
    assert enlace in mensaje.texto
    partes = urlsplit(enlace)
    if nombre in {"firma", "contraparte"}:
        assert partes.fragment == f"token={token}"
        assert not partes.query
        assert "USB-ORI-2026-EJEMPLO" in mensaje.texto
    else:
        assert parse_qs(partes.query)["token"] == [token]
        assert not partes.fragment
        assert "puede ignorar este mensaje" in mensaje.texto
    assert (
        mensaje.destinatario
        == {
            "firma": "firmante@example.invalid",
            "contraparte": "contraparte@example.invalid",
            "verificacion": "usuario@example.invalid",
            "recuperacion": "usuario@example.invalid",
        }[nombre]
    )
    assert mensaje.cc == (("copia@example.invalid",) if nombre == "contraparte" else ())


def test_vigencias_se_corresponden_con_las_reglas_existentes():
    assert (
        VIGENCIA_INVITACION_FIRMA
        == VIGENCIA_INVITACION_CONTRAPARTE
        == timedelta(hours=1)
    )
    assert VIGENCIA_TOKEN_VERIFICACION == timedelta(hours=24)
    assert VIGENCIA_TOKEN_RECUPERACION == timedelta(minutes=30)


def test_contenido_dinamico_no_puede_inyectar_html_o_atributos():
    ataque = '<img src=x onerror="alert(1)"> & <script>no</script>'
    for mensaje in mensajes_ficticios(referencia=ataque, cargo=ataque).values():
        html = InspeccionHTML()
        html.feed(mensaje.html)
        assert "img" not in html.etiquetas and "script" not in html.etiquetas
        assert (
            "&lt;img" in mensaje.html
            or mensaje.destinatario == "usuario@example.invalid"
        )
    html = correo_institucional(
        titulo=ataque,
        contenido=ataque,
        accion=ataque,
        enlace='https://example.invalid/#token=" onmouseover="no',
        vigencia=ataque,
        seguridad=ataque,
        contexto=((ataque, ataque),),
    )
    inspeccion = InspeccionHTML()
    inspeccion.feed(html)
    assert set(inspeccion.etiquetas) <= {
        "html",
        "head",
        "meta",
        "title",
        "body",
        "table",
        "tr",
        "td",
        "strong",
        "br",
        "span",
        "h1",
        "p",
        "a",
    }
    assert inspeccion.enlaces == ['https://example.invalid/#token=" onmouseover="no']
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("fallar", [False, True])
def test_brevo_recibe_ambas_versiones_y_conserva_errores_sin_filtrar_tokens(
    fallar, caplog
):
    mensaje = mensajes_ficticios()["contraparte"]
    solicitudes = []

    def recibir(request):
        solicitudes.append(json.loads(request.content))
        return httpx.Response(503 if fallar else 201, request=request)

    brevo = CorreoBrevo(
        "credencial-ficticia",
        "ori@example.invalid",
        "ORI Manager",
        httpx.Client(transport=httpx.MockTransport(recibir)),
    )
    if fallar:
        with pytest.raises(ErrorEnvioCorreo) as error:
            brevo.enviar(mensaje)
        assert error.value.__context__ is None
        assert "FICTICIO_SIN_VALIDEZ_123" not in str(error.value) + caplog.text
    else:
        brevo.enviar(mensaje)
    assert solicitudes[0]["htmlContent"] == mensaje.html
    assert solicitudes[0]["textContent"] == mensaje.texto
    assert solicitudes[0]["to"] == [{"email": mensaje.destinatario}]
    assert solicitudes[0]["cc"] == [{"email": "copia@example.invalid"}]
