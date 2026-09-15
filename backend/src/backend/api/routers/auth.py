from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session as DBSession

from backend.api.deps import get_current_user, get_session_token
from backend.db.session import get_db
from backend.models.user import User
from backend.services.auth import (
    InactiveUserError,
    InvalidCredentialsError,
    authenticate_user,
    create_session,
    invalidate_session,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    status: str
    message: str


@router.post("/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    response: Response,
    db: Annotated[DBSession, Depends(get_db)],
):
    try:
        user = authenticate_user(db, request.email, request.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )

    session = create_session(db, user.id)
    
    # HTTP-Only Cookie with Secure and Lax settings
    response.set_cookie(
        key="session_id",
        value=session.token,
        httponly=True,
        secure=True, 
        samesite="lax",
        max_age=7 * 24 * 60 * 60, # 7 days
    )
    
    return {"status": "ok", "message": "Login successful"}


@router.post("/logout")
def logout(
    response: Response,
    db: Annotated[DBSession, Depends(get_db)],
    token: Annotated[str, Depends(get_session_token)],
):
    invalidate_session(db, token)
    response.delete_cookie(key="session_id", httponly=True, secure=True, samesite="lax")
    return {"status": "ok", "message": "Logout successful"}


@router.get("/me")
def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
    }
