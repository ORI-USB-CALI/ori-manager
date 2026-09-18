import hashlib
import secrets

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def validar_contrasena(contrasena: str) -> str:
    if len(contrasena) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    return contrasena


def hash_contrasena(contrasena: str) -> str:
    return _password_hash.hash(validar_contrasena(contrasena))


def verificar_contrasena(contrasena: str, hash_almacenado: str) -> bool:
    return _password_hash.verify(contrasena, hash_almacenado)


def generar_token_sesion() -> str:
    return secrets.token_urlsafe(64)


def digest_token_sesion(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
