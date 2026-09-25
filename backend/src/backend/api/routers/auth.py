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
    MensajePublico,
    RecuperacionContrasenaSolicitud,
    ReenvioVerificacionSolicitud,
    RegistroSolicitante,
    RegistroSolicitanteRespuesta,
    RestablecimientoContrasenaSolicitud,
    TokenRecuperacionSolicitud,
    TokenVerificacionSolicitud,
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
from backend.services.correo import EnviadorCorreo, get_enviador_correo
from backend.services.recuperacion_contrasena import (
    MENSAJE_RECUPERACION,
    ContrasenaReutilizadaError,
    ServicioRecuperacionContrasena,
    TokenRecuperacionInvalidoError,
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
from backend.services.verificacion_correo import (
    MENSAJE_REENVIO,
    ServicioVerificacionCorreo,
    TokenVerificacionInvalidoError,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

DatabaseSession = Annotated[Session, Depends(get_db)]
SessionRepository = Annotated[
    RepositorioSesiones,
    Depends(get_repositorio_sesiones),
]
Correo = Annotated[EnviadorCorreo, Depends(get_enviador_correo)]


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
    correo: Correo,
) -> RegistroSolicitanteRespuesta:
    verificacion = ServicioVerificacionCorreo(db, correo, settings.public_frontend_url)
    try:
        resultado = ServicioRegistro(db).registrar(datos, verificacion)
        usuario = resultado.usuario
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
        mensaje=(
            "Cuenta creada. Revisa tu correo para verificar tu cuenta."
            if resultado.correo_enviado
            else "Cuenta creada, pero no fue posible enviar el correo. Puede reenviar la verificación."
        ),
        tipo_usuario=clasificar_correo(usuario.correo),
    )


@router.post("/verificar-correo", response_model=MensajePublico)
def verificar_correo(
    datos: TokenVerificacionSolicitud,
    db: DatabaseSession,
    correo: Correo,
) -> MensajePublico:
    try:
        ServicioVerificacionCorreo(db, correo, settings.public_frontend_url).verificar(
            datos.token
        )
    except TokenVerificacionInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"codigo": exc.codigo, "message": str(exc)},
        ) from exc
    return MensajePublico(message="Correo verificado correctamente.")


@router.post("/reenviar-verificacion", response_model=MensajePublico)
def reenviar_verificacion(
    datos: ReenvioVerificacionSolicitud,
    db: DatabaseSession,
    correo: Correo,
) -> MensajePublico:
    ServicioVerificacionCorreo(db, correo, settings.public_frontend_url).reenviar(
        str(datos.correo)
    )
    return MensajePublico(message=MENSAJE_REENVIO)


@router.post("/recuperar-contrasena", response_model=MensajePublico)
def recuperar_contrasena(
    datos: RecuperacionContrasenaSolicitud,
    db: DatabaseSession,
    correo: Correo,
    sesiones: SessionRepository,
) -> MensajePublico:
    ServicioRecuperacionContrasena(
        db, correo, sesiones, settings.public_frontend_url
    ).solicitar(str(datos.correo))
    return MensajePublico(message=MENSAJE_RECUPERACION)


@router.post("/validar-recuperacion-contrasena", response_model=MensajePublico)
def validar_recuperacion_contrasena(
    datos: TokenRecuperacionSolicitud,
    db: DatabaseSession,
    correo: Correo,
    sesiones: SessionRepository,
) -> MensajePublico:
    try:
        ServicioRecuperacionContrasena(
            db, correo, sesiones, settings.public_frontend_url
        ).validar(datos.token)
    except TokenRecuperacionInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"codigo": exc.codigo, "message": str(exc)},
        ) from exc
    return MensajePublico(message="Enlace válido.")


@router.post("/restablecer-contrasena", response_model=MensajePublico)
def restablecer_contrasena(
    datos: RestablecimientoContrasenaSolicitud,
    db: DatabaseSession,
    correo: Correo,
    sesiones: SessionRepository,
) -> MensajePublico:
    try:
        ServicioRecuperacionContrasena(
            db, correo, sesiones, settings.public_frontend_url
        ).restablecer(datos.token, datos.nueva_contrasena)
    except TokenRecuperacionInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"codigo": exc.codigo, "message": str(exc)},
        ) from exc
    except ContrasenaReutilizadaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "codigo": "CONTRASENA_REUTILIZADA",
                "message": str(exc),
            },
        ) from exc
    return MensajePublico(message="Contraseña actualizada correctamente.")


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
