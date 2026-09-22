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
    RegistroSolicitante,
    RegistroSolicitanteRespuesta,
    UnidadRegistroLeer,
    UsuarioActualLeer,
)
from backend.services.auth import (
    DURACION_SESION,
    CorreoNoVerificadoError,
    CredencialesInvalidasError,
    ServicioAutenticacion,
    UsuarioInactivoError,
)
from backend.services.registro import (
    CorreoRegistradoError,
    ReferenciaRegistroInvalidaError,
    ServicioRegistro,
    clasificar_correo,
)
from backend.services.sesiones import (
    RepositorioSesiones,
    get_repositorio_sesiones,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

DatabaseSession = Annotated[Session, Depends(get_db)]
SessionRepository = Annotated[
    RepositorioSesiones,
    Depends(get_repositorio_sesiones),
]


@router.get("/registro/unidades", response_model=list[UnidadRegistroLeer])
def listar_unidades_registro(db: DatabaseSession):
    return ServicioRegistro(db).listar_unidades()


@router.post(
    "/registro",
    response_model=RegistroSolicitanteRespuesta,
    status_code=status.HTTP_201_CREATED,
)
def registrar_solicitante(
    datos: RegistroSolicitante,
    db: DatabaseSession,
) -> RegistroSolicitanteRespuesta:
    try:
        usuario = ServicioRegistro(db).registrar(datos)
    except CorreoRegistradoError as exc:
        siguiente_paso = (
            "INICIAR_SESION" if exc.correo_verificado else "VERIFICAR_CORREO"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "codigo": "CORREO_REGISTRADO",
                "message": str(exc),
                "siguiente_paso": siguiente_paso,
            },
        ) from exc
    except ReferenciaRegistroInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return RegistroSolicitanteRespuesta(
        estado="VERIFICACION_PENDIENTE",
        mensaje="Cuenta creada. Debe verificar su correo antes de iniciar sesión.",
        tipo_usuario=clasificar_correo(usuario.correo),
    )


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
    except CorreoNoVerificadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debe verificar su correo antes de iniciar sesión",
        ) from exc

    response.set_cookie(
        key="session_id",
        value=token,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        path="/",
        max_age=int(DURACION_SESION.total_seconds()),
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
