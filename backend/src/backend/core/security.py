import secrets

import bcrypt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def generate_session_token() -> str:
    """Generate a secure random session token."""
    return secrets.token_urlsafe(64)


def validar_password(password: str) -> str:
    """Regla única de contraseñas (API y CLI). bcrypt solo admite hasta 72 bytes."""
    if not 8 <= len(password.encode()) <= 72:
        raise ValueError("La contraseña debe tener entre 8 y 72 bytes")
    return password
