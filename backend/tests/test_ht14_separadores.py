"""H-07: separadores explícitos y rechazo de controles antes de normalizar."""

import pytest
from pydantic import ValidationError

from backend.core.validaciones import (
    normalizar_digito_verificacion_nit,
    normalizar_identificacion,
    normalizar_telefono,
)
from backend.models.enums import TipoIdentificacion
from backend.schemas.solicitud import SolicitudActualizar, SolicitudCrear

PROHIBIDOS = ["\u0085", "\u001c", "\ufeff", "\u200b", "\u202e", "\t"]
ESPACIOS = " \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
CASOS = [
    ("NIT", "900", "123456", "900123456"),
    ("CEDULA_CIUDADANIA", "1144", "123456", "1144123456"),
    ("CEDULA_EXTRANJERIA", "ab", "123", "AB123"),
    ("PASAPORTE", "ab", "12345", "AB12345"),
    ("IDENTIFICACION_FISCAL_EXTRANJERA", "RFC", "AB1", "RFC AB1"),
    ("OTRO", "Registro", "123", "Registro 123"),
]


@pytest.mark.parametrize(("tipo", "izquierda", "derecha", "_canonico"), CASOS)
@pytest.mark.parametrize("control", PROHIBIDOS)
@pytest.mark.parametrize("posicion", ["inicio", "interior", "final"])
def test_h07_identificacion_rechaza_controles(tipo, izquierda, derecha, _canonico, control, posicion):
    valor = {"inicio": control + izquierda + derecha,
             "interior": izquierda + control + derecha,
             "final": izquierda + derecha + control}[posicion]
    with pytest.raises(ValueError):
        normalizar_identificacion(TipoIdentificacion(tipo), valor)


@pytest.mark.parametrize(("tipo", "izquierda", "derecha", "canonico"), CASOS)
def test_h07_espacios_horizontales_legitimos_por_tipo(tipo, izquierda, derecha, canonico):
    for espacio in ESPACIOS:
        assert normalizar_identificacion(TipoIdentificacion(tipo), espacio + izquierda + espacio + derecha + espacio) == canonico
    assert normalizar_identificacion(TipoIdentificacion.NIT, "900.123.456") == "900123456"
    assert normalizar_identificacion(TipoIdentificacion.CEDULA_CIUDADANIA, "1.144 123.456") == "1144123456"


@pytest.mark.parametrize("control", PROHIBIDOS)
@pytest.mark.parametrize("valor", ["{c}8", "8{c}", "{c}8{c}"])
def test_h07_dv_no_oculta_controles(control, valor):
    with pytest.raises(ValueError):
        normalizar_digito_verificacion_nit("900123456", valor.format(c=control))


def test_h07_dv_admite_solo_espacios_legitimos_en_bordes():
    for espacio in ESPACIOS:
        assert normalizar_digito_verificacion_nit("900123456", espacio + "8" + espacio) == "8"
    with pytest.raises(ValueError):
        normalizar_digito_verificacion_nit(None, "8 8")


@pytest.mark.parametrize("control", PROHIBIDOS)
@pytest.mark.parametrize("valor", ["{c}3001234567", "300{c}1234567", "3001234567{c}"])
def test_h07_telefono_no_oculta_controles(control, valor):
    with pytest.raises(ValueError):
        normalizar_telefono(valor.format(c=control))


def test_h07_telefono_conserva_espacios_legitimos_extension_e_idempotencia():
    for espacio in ESPACIOS:
        canonico = normalizar_telefono(espacio + "+57" + espacio + "6025551234" + espacio + "ext" + espacio + "000123" + espacio)
        assert canonico == "+576025551234;ext=000123"
        assert normalizar_telefono(canonico) == canonico


@pytest.mark.parametrize("modelo", [SolicitudCrear, SolicitudActualizar])
@pytest.mark.parametrize(("campo", "valor"), [
    ("identificacion_aliado_propuesto", "900123456"), ("solicitante_documento", "1144123456"),
    ("digito_verificacion_aliado_propuesto", "8"), ("solicitante_digito_verificacion", "8"),
    ("telefono_aliado_propuesto", "3001234567"), ("contacto_contraparte_telefono", "3001234567"),
    ("supervisor_usb_telefono", "3001234567"), ("supervisor_contraparte_telefono", "3001234567"),
])
@pytest.mark.parametrize("control", PROHIBIDOS[:3])
def test_h07_pydantic_no_strippea_caracteres_indebidos(modelo, campo, valor, control):
    original = control + valor + control
    try:
        entrada = modelo.model_validate({campo: original})
    except ValidationError as error:
        assert error.errors()[0]["loc"] == (campo,)
    else:
        assert getattr(entrada, campo) == original


@pytest.mark.parametrize(("tipo", "izquierda", "derecha", "_canonico"), CASOS)
def test_h07_identificacion_no_admite_terminador_final(tipo, izquierda, derecha, _canonico):
    for terminador in ("\n", "\r", "\u2028", "\u2029"):
        with pytest.raises(ValueError):
            normalizar_identificacion(TipoIdentificacion(tipo), izquierda + derecha + terminador)


def test_h07_dv_y_telefono_no_admiten_terminador_final():
    for terminador in ("\n", "\r", "\u2028", "\u2029"):
        with pytest.raises(ValueError):
            normalizar_digito_verificacion_nit("900123456", "8" + terminador)
        with pytest.raises(ValueError):
            normalizar_telefono("3001234567" + terminador)
