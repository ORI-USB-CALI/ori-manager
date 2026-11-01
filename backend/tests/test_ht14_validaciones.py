"""HT-14 BE01. Matriz de reglas de formato para los datos de la solicitud.

Cada caso documenta un valor válido (con su forma canónica) o inválido.
"""

import pytest

from backend.core.validaciones import (
    calcular_digito_verificacion_nit,
    normalizar_ciudad,
    normalizar_digito_verificacion_nit,
    normalizar_direccion,
    normalizar_identificacion,
    normalizar_telefono,
)
from backend.models.enums import TipoIdentificacion

NIT = TipoIdentificacion.NIT
CC = TipoIdentificacion.CEDULA_CIUDADANIA
CE = TipoIdentificacion.CEDULA_EXTRANJERIA
PASAPORTE = TipoIdentificacion.PASAPORTE
FISCAL = TipoIdentificacion.IDENTIFICACION_FISCAL_EXTRANJERA
OTRO = TipoIdentificacion.OTRO


# --- NIT: dígito de verificación (algoritmo DIAN) ---------------------------


@pytest.mark.parametrize(
    ("base", "dv"),
    [
        ("800197268", 4),  # DIAN
        ("899999068", 1),  # Ecopetrol
    ],
)
def test_calcula_digito_verificacion_de_nits_reales(base, dv):
    assert calcular_digito_verificacion_nit(base) == dv


@pytest.mark.parametrize(
    ("base", "dv", "canonico"),
    [("800197268", "4", "4"), ("899999068", " 1 ", "1")],
)
def test_digito_verificacion_correcto_se_acepta(base, dv, canonico):
    assert normalizar_digito_verificacion_nit(base, dv) == canonico


@pytest.mark.parametrize(
    ("base", "dv"),
    [
        ("800197268", "5"),  # no coincide con el algoritmo DIAN
        ("800197268", "45"),
        ("800197268", "A"),
        ("800197268", ""),
        ("800197268", "-4"),
    ],
)
def test_digito_verificacion_incorrecto_se_rechaza(base, dv):
    with pytest.raises(ValueError):
        normalizar_digito_verificacion_nit(base, dv)


# --- Identificación según el tipo (CA-01, RN-04) ----------------------------


@pytest.mark.parametrize(
    ("tipo", "valor", "canonico"),
    [
        # El NIT guarda solo la base; el DV va en su propio campo.
        (NIT, "800197268", "800197268"),
        (NIT, "800.197.268", "800197268"),
        (NIT, " 800 197 268 ", "800197268"),
        (NIT, "12345", "12345"),  # persona natural
        (NIT, "1144123456", "1144123456"),
        (CC, "1144123456", "1144123456"),
        (CC, "1.144.123.456", "1144123456"),
        (CC, "12345", "12345"),
        (CC, " 79 123 456 ", "79123456"),
        (CE, "e123456", "E123456"),
        (CE, "123", "123"),
        (CE, "AB 12 34", "AB1234"),
        (PASAPORTE, "ab123456", "AB123456"),
        (PASAPORTE, "X 1234 567", "X1234567"),
        (FISCAL, "B-12345678", "B-12345678"),
        (FISCAL, "12-3456789", "12-3456789"),
        (FISCAL, "RFC  ABC010101/AB1", "RFC ABC010101/AB1"),
        (OTRO, "Registro 123.45", "Registro 123.45"),
    ],
)
def test_identificacion_valida_se_normaliza(tipo, valor, canonico):
    assert normalizar_identificacion(tipo, valor) == canonico


@pytest.mark.parametrize(
    ("tipo", "valor"),
    [
        (NIT, "800197268-4"),  # el DV no se escribe en la identificación
        (NIT, "800197268-45"),
        (NIT, "1234"),  # base muy corta
        (NIT, "12345678901"),  # base muy larga
        (NIT, "80019726A-4"),
        (NIT, "-4"),
        (CC, "1234"),
        (CC, "12345678901"),
        (CC, "1144123456A"),
        (CC, "1144-123456"),
        (CE, "12"),
        (CE, "1234567890123456"),
        (CE, "E-12345"),
        (PASAPORTE, "AB12"),
        (PASAPORTE, "A" * 21),
        (PASAPORTE, "AB#12345"),
        (FISCAL, "AB"),
        (FISCAL, "A" * 41),
        (FISCAL, "ABC@123"),
        (OTRO, "1*2*3"),
        (NIT, ""),
        (CC, "   "),
    ],
)
def test_identificacion_invalida_se_rechaza(tipo, valor):
    with pytest.raises(ValueError):
        normalizar_identificacion(tipo, valor)


# --- Teléfonos (CA-02, RN-05) -----------------------------------------------


@pytest.mark.parametrize(
    ("valor", "canonico"),
    [
        ("3001234567", "+573001234567"),
        ("300 123 4567", "+573001234567"),
        ("300-123-4567", "+573001234567"),
        ("+57 300 123 4567", "+573001234567"),
        ("6025551234", "+576025551234"),
        ("(602) 555-1234", "+576025551234"),
        ("602 555 1234 ext. 123", "+576025551234;ext=123"),
        ("6025551234 ext 45", "+576025551234;ext=45"),
        ("+1 650 253 0000", "+16502530000"),
        ("+34 912 345 678", "+34912345678"),
        ("+44 20 7946 0958", "+442079460958"),
    ],
)
def test_telefono_valido_se_normaliza_a_e164(valor, canonico):
    assert normalizar_telefono(valor) == canonico


@pytest.mark.parametrize(
    "valor",
    [
        "abc3001234567",  # letras (phonenumbers las convertiría en dígitos)
        "300-ABC-4567",
        "12345",
        "300123456",  # le falta un dígito
        "30012345678",  # le sobra un dígito
        "5551234",  # fijo antiguo de 7 dígitos
        "+999 1234567",  # indicativo inexistente
        "+57 300 123 4567 +1",
        "300 123 4567 ext.",
        "",
    ],
)
def test_telefono_invalido_se_rechaza(valor):
    with pytest.raises(ValueError):
        normalizar_telefono(valor)


# --- Ciudad (CA-03) ---------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "canonico"),
    [
        ("Cali", "Cali"),
        ("  Santiago   de  Cali ", "Santiago de Cali"),
        ("Bogotá D.C.", "Bogotá D.C."),
        ("São Paulo", "São Paulo"),
        ("L'Aquila", "L'Aquila"),
        ("Saint-Étienne", "Saint-Étienne"),
        ("Cúcuta", "Cúcuta"),
    ],
)
def test_ciudad_valida_se_normaliza(valor, canonico):
    assert normalizar_ciudad(valor) == canonico


@pytest.mark.parametrize(
    "valor", ["C", "Cali 123", "Cali!", "-Cali", "A" * 121, "", "   "]
)
def test_ciudad_invalida_se_rechaza(valor):
    with pytest.raises(ValueError):
        normalizar_ciudad(valor)


# --- Dirección (CA-04, RN-07, RN-08) ----------------------------------------


@pytest.mark.parametrize(
    ("valor", "canonico"),
    [
        ("Calle 5 # 38-25", "Calle 5 # 38-25"),
        ("Cra. 122 No. 6-65, Pance", "Cra. 122 No. 6-65, Pance"),
        ("Vereda La Esperanza, Finca El Roble", "Vereda La Esperanza, Finca El Roble"),
        ("1600 Amphitheatre Pkwy, Mountain View", "1600 Amphitheatre Pkwy, Mountain View"),
        ("Av.  Paulista   1578", "Av. Paulista 1578"),
        ("Km 3 vía Cali/Jamundí (Ed. 2)", "Km 3 vía Cali/Jamundí (Ed. 2)"),
        ("Calle 10 N° 4-20", "Calle 10 N° 4-20"),
    ],
)
def test_direccion_valida_se_normaliza(valor, canonico):
    assert normalizar_direccion(valor) == canonico


@pytest.mark.parametrize(
    "valor",
    [
        "Cl 5",  # muy corta
        "12345 # 67",  # sin letras
        "Calle 5 <script>",
        "Calle 5 @ 38",
        "A" * 201,
        "",
    ],
)
def test_direccion_invalida_se_rechaza(valor):
    with pytest.raises(ValueError):
        normalizar_direccion(valor)
