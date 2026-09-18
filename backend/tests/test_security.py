from backend.core.security import (
    digest_token_sesion,
    generar_token_sesion,
    hash_contrasena,
    validar_contrasena,
    verificar_contrasena,
)


def test_hash_contrasena_usa_hash_no_reversible() -> None:
    contrasena = "ClaveSegura123"
    resultado = hash_contrasena(contrasena)

    assert resultado != contrasena
    assert verificar_contrasena(contrasena, resultado)
    assert not verificar_contrasena("ClaveIncorrecta", resultado)


def test_contrasena_exige_minimo_ocho_caracteres() -> None:
    try:
        validar_contrasena("corta")
    except ValueError as exc:
        assert "8" in str(exc)
    else:
        raise AssertionError("Se aceptó una contraseña corta")


def test_token_y_digest_son_seguros() -> None:
    token = generar_token_sesion()
    digest = digest_token_sesion(token)

    assert len(token) > 64
    assert len(digest) == 64
    assert digest != token
    assert digest_token_sesion(token) == digest
