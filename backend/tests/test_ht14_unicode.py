"""H-06: Unicode y límites sobre el texto canónico, sin reescribir históricos."""

import pytest
from pydantic import ValidationError

from backend.core.validaciones import normalizar_ciudad, normalizar_direccion
from backend.schemas.solicitud import SolicitudActualizar, SolicitudCrear

CASOS_CANONICOS = [
    ("ciudad_aliado_propuesto", "A" * 59 + " " * 50 + "B" * 60, "A" * 59 + " " + "B" * 60),
    ("ciudad_aliado_propuesto", "e\u0301" * 120, "é" * 120),
    ("direccion_aliado_propuesto", "A" * 99 + " " * 80 + "B" * 98 + " 1", "A" * 99 + " " + "B" * 98 + " 1"),
    ("direccion_aliado_propuesto", "e\u0301" * 199 + "1", "é" * 199 + "1"),
]


@pytest.mark.parametrize("modelo", [SolicitudCrear, SolicitudActualizar])
@pytest.mark.parametrize(("campo", "valor", "canonico"), CASOS_CANONICOS)
def test_h06_normaliza_antes_de_max_length(modelo, campo, valor, canonico):
    assert getattr(modelo.model_validate({campo: valor}), campo) == canonico


@pytest.mark.parametrize("modelo", [SolicitudCrear, SolicitudActualizar])
@pytest.mark.parametrize(("campo", "valor"), [
    ("ciudad_aliado_propuesto", "e\u0301" * 121),
    ("direccion_aliado_propuesto", "e\u0301" * 200 + "1"),
])
def test_h06_max_length_sigue_vigente_despues_de_normalizar(modelo, campo, valor):
    with pytest.raises(ValidationError) as error:
        modelo.model_validate({campo: valor})
    assert error.value.errors()[0]["loc"] == (campo,)


@pytest.mark.parametrize("valor", ["Qq\u0323", "मुंबई", "q\u0323" * 60, "𐐀" * 120])
def test_h06_ciudad_admite_marcas_de_letras_y_maximo_en_puntos_de_codigo(valor):
    assert normalizar_ciudad(valor) == valor


@pytest.mark.parametrize("valor", ["Finca Qq\u0323, Pance", "मुंबई 12", "q\u0323" * 99 + "a1"])
def test_h06_direccion_admite_marcas_de_letras_sin_cambiar_su_estructura(valor):
    assert normalizar_direccion(valor) == valor


@pytest.mark.parametrize("valor", [
    "\u0323Cali", "Ca \u0323li", "Ca-\u0323li", "Ca\x00li", "Ca\x1cli",
    "Ca\u0085li", "Ca\u200bli", "Ca\u202eli", "\ufeffCali", "Cali@",
    "q\u0323" * 60 + "a",
])
def test_h06_ciudad_rechaza_marcas_huerfanas_controles_y_exceso(valor):
    with pytest.raises(ValueError):
        normalizar_ciudad(valor)


@pytest.mark.parametrize("valor", [
    "Casa \u0323, Pance", "Calle 1\u0323", "Casa\x001", "Casa\x1c1",
    "Casa\u00851", "Casa\u200b1", "\ufeffCasa 1", "Casa <b>1</b>",
    "q\u0323" * 99 + "aa1",
])
def test_h06_direccion_rechaza_marcas_huerfanas_controles_y_exceso(valor):
    with pytest.raises(ValueError):
        normalizar_direccion(valor)


def test_h06_espacios_de_presentacion_se_convierten_en_espacio_simple():
    assert normalizar_ciudad("\t São\u00a0\u00a0Paulo\r\n") == "São Paulo"
    assert normalizar_direccion("Casa\t\t12\u3000Pance") == "Casa 12 Pance"
