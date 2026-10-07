import pytest

from backend.core.security import (
    digest_token_sesion,
    generar_token_sesion,
    hash_contrasena,
    validar_contrasena,
    verificar_contrasena,
)


def test_hash_contrasena_usa_hash_no_reversible() -> None:
    contrasena = "ClaveSegura123!"
    resultado = hash_contrasena(contrasena)

    assert resultado != contrasena
    assert verificar_contrasena(contrasena, resultado)
    assert not verificar_contrasena("ClaveIncorrecta", resultado)


def test_contrasena_segura_cumple_politica() -> None:
    assert validar_contrasena("ClaveSegura123!") == "ClaveSegura123!"


@pytest.mark.parametrize(
    "contrasena",
    [
        "Corta1!",
        "clavesegura123!",
        "CLAVESEGURA123!",
        "ClaveSegura!",
        "ClaveSegura123",
        "Clave Segura123",
    ],
)
def test_contrasena_rechaza_cada_incumplimiento(contrasena: str) -> None:
    with pytest.raises(ValueError, match="mayúscula"):
        validar_contrasena(contrasena)


def test_token_y_digest_son_seguros() -> None:
    token = generar_token_sesion()
    digest = digest_token_sesion(token)

    assert len(token) > 64
    assert len(digest) == 64
    assert digest != token
    assert digest_token_sesion(token) == digest
