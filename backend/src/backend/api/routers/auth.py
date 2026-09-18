from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.api.deps import (
    UsuarioActual,
    get_session_token,
    permisos_de_usuario,
)
from backend.core.config import settings
from backend.db.session import get_db
from backend.schemas.auth import (
    LoginSolicitud,
    MensajeAutenticacion,
    UsuarioActualLeer,
)
from backend.services.auth import (
    CredencialesInvalidasError,
    ServicioAutenticacion,
    UsuarioInactivoError,
)
from backend.services.sesiones import (
    RepositorioSesiones,
    get_repositorio_sesiones,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
MAX_AGE_SESION = 7 * 24 * 60 * 60

DatabaseSession = Annotated[Session, Depends(get_db)]
SessionRepository = Annotated[
    RepositorioSesiones,
    Depends(get_repositorio_sesiones),
]


@router.post("/login", response_model=MensajeAutenticacion)
def login(
    datos: LoginSolicitud,
    response: Response,
    db: DatabaseSession,
    sesiones: SessionRepository,
) -> MensajeAutenticacion:
    try:
        _, token = ServicioAutenticacion(db, sesiones).iniciar_sesion(
            str(datos.correo),
            datos.contrasena,
        )
    except CredencialesInvalidasError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        ) from exc
    except UsuarioInactivoError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        ) from exc

    response.set_cookie(
        key="session_id",
        value=token,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        path="/",
        max_age=MAX_AGE_SESION,
    )
    return MensajeAutenticacion(status="ok", message="Sesión iniciada")


@router.post("/logout", response_model=MensajeAutenticacion)
def logout(
    response: Response,
    token: Annotated[str, Depends(get_session_token)],
    db: DatabaseSession,
    sesiones: SessionRepository,
) -> MensajeAutenticacion:
    ServicioAutenticacion(db, sesiones).cerrar_sesion(token)
    response.delete_cookie(
        key="session_id",
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        path="/",
    )
    return MensajeAutenticacion(status="ok", message="Sesión cerrada")


@router.get("/me", response_model=UsuarioActualLeer)
def obtener_usuario_actual(usuario: UsuarioActual) -> UsuarioActualLeer:
    return UsuarioActualLeer(
        id=usuario.id,
        correo=usuario.correo,
        nombre_completo=usuario.nombre_completo,
        activo=usuario.activo,
        tipo_usuario=usuario.tipo_usuario,
        rol=usuario.rol,
        permisos=sorted(permisos_de_usuario(usuario), key=str),
    )
