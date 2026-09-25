import hashlib
import secrets

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()

MENSAJE_POLITICA_CONTRASENA = (
    "La contraseña debe tener al menos 8 caracteres, una mayúscula, una "
    "minúscula, un número y un carácter especial."
)


def validar_contrasena(contrasena: str) -> str:
    cumple_politica = (
        len(contrasena) >= 8
        and any(caracter.isupper() for caracter in contrasena)
        and any(caracter.islower() for caracter in contrasena)
        and any(caracter.isdigit() for caracter in contrasena)
        and any(
            not caracter.isalnum() and not caracter.isspace()
            for caracter in contrasena
        )
    )
    if not cumple_politica:
        raise ValueError(MENSAJE_POLITICA_CONTRASENA)
    return contrasena


def hash_contrasena(contrasena: str) -> str:
    return _password_hash.hash(validar_contrasena(contrasena))


def verificar_contrasena(contrasena: str, hash_almacenado: str) -> bool:
    return _password_hash.verify(contrasena, hash_almacenado)


def generar_token_sesion() -> str:
    return secrets.token_urlsafe(64)


def digest_token_sesion(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
