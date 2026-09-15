import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from backend.core.security import generate_session_token, verify_password
from backend.models.session import Session
from backend.models.user import User


class AuthError(Exception):
    pass


class InvalidCredentialsError(AuthError):
    pass


class InactiveUserError(AuthError):
    pass


def authenticate_user(db: DBSession, email: str, password: str) -> User:
    """Authenticate a user and return the user object if valid."""
    stmt = select(User).where(User.email == email)
    user = db.execute(stmt).scalar_one_or_none()

    if not user:
        raise InvalidCredentialsError("Credenciales inválidas.")
    
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Credenciales inválidas.")
        
    if not user.is_active:
        raise InactiveUserError("El usuario se encuentra inactivo.")
        
    return user


def create_session(db: DBSession, user_id: str, expire_days: int = 7) -> Session:
    """Create a new session in the database."""
    token = generate_session_token()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=expire_days)
    
    session_db = Session(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        is_valid=True,
    )
    db.add(session_db)
    db.commit()
    db.refresh(session_db)
    
    return session_db


def invalidate_session(db: DBSession, token: str) -> bool:
    """Invalidate a session by token."""
    stmt = select(Session).where(Session.token == token)
    session_db = db.execute(stmt).scalar_one_or_none()
    
    if session_db:
        session_db.is_valid = False
        db.commit()
        return True
    return False


def get_valid_session(db: DBSession, token: str) -> Session | None:
    """Retrieve a session if it's valid and not expired."""
    stmt = select(Session).where(
        Session.token == token,
        Session.is_valid == True, # noqa: E712
    )
    session_db = db.execute(stmt).scalar_one_or_none()
    
    if not session_db:
        return None
        
    if session_db.expires_at < datetime.datetime.now(datetime.timezone.utc):
        # Invalidate expired session automatically
        session_db.is_valid = False
        db.commit()
        return None
        
    return session_db
