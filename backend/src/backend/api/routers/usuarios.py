from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import requiere
from backend.core.permisos import Permiso
from backend.db.session import get_db
from backend.models.usuario import Usuario
from backend.schemas.usuario import (
    UsuarioActualizar,
    UsuarioCambiarEstado,
    UsuarioCambiarRol,
    UsuarioCrear,
    UsuarioLeer,
)
from backend.services.sesiones import (
    RepositorioSesiones,
    get_repositorio_sesiones,
)
from backend.services.usuarios import (
    ConflictoUsuarioError,
    CorreoDuplicadoError,
    ErrorGestionUsuarios,
    ReferenciaUsuarioInvalidaError,
    ServicioUsuarios,
    UsuarioNoEncontradoError,
)

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

DatabaseSession = Annotated[Session, Depends(get_db)]
SessionRepository = Annotated[
    RepositorioSesiones,
    Depends(get_repositorio_sesiones),
]
PuedeVerUsuarios = Annotated[Usuario, requiere(Permiso.USUARIOS_VER)]
PuedeCrearUsuarios = Annotated[Usuario, requiere(Permiso.USUARIOS_CREAR)]
PuedeEditarUsuarios = Annotated[Usuario, requiere(Permiso.USUARIOS_EDITAR)]
PuedeCambiarRol = Annotated[Usuario, requiere(Permiso.USUARIOS_CAMBIAR_ROL)]
PuedeCambiarEstado = Annotated[
    Usuario,
    requiere(Permiso.USUARIOS_CAMBIAR_ESTADO),
]


def _servicio(db: Session, sesiones: RepositorioSesiones) -> ServicioUsuarios:
    return ServicioUsuarios(db, sesiones)


def _lanzar_http(exc: ErrorGestionUsuarios) -> NoReturn:
    if isinstance(exc, UsuarioNoEncontradoError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado") from exc
    if isinstance(exc, CorreoDuplicadoError):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya existe un usuario con ese correo",
        ) from exc
    if isinstance(exc, ConflictoUsuarioError):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if isinstance(exc, ReferenciaUsuarioInvalidaError):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            str(exc),
        ) from exc
    raise exc


@router.get("", response_model=list[UsuarioLeer])
def listar_usuarios(
    db: DatabaseSession,
    sesiones: SessionRepository,
    _: PuedeVerUsuarios,
) -> list[Usuario]:
    return _servicio(db, sesiones).listar()


@router.get("/{usuario_id}", response_model=UsuarioLeer)
def obtener_usuario(
    usuario_id: int,
    db: DatabaseSession,
    sesiones: SessionRepository,
    _: PuedeVerUsuarios,
) -> Usuario:
    try:
        return _servicio(db, sesiones).obtener(usuario_id)
    except ErrorGestionUsuarios as exc:
        _lanzar_http(exc)


@router.post("", response_model=UsuarioLeer, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos: UsuarioCrear,
    db: DatabaseSession,
    sesiones: SessionRepository,
    _: PuedeCrearUsuarios,
) -> Usuario:
    try:
        return _servicio(db, sesiones).crear(datos)
    except ErrorGestionUsuarios as exc:
        _lanzar_http(exc)


@router.patch("/{usuario_id}", response_model=UsuarioLeer)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioActualizar,
    db: DatabaseSession,
    sesiones: SessionRepository,
    _: PuedeEditarUsuarios,
) -> Usuario:
    try:
        return _servicio(db, sesiones).actualizar(usuario_id, datos)
    except ErrorGestionUsuarios as exc:
        _lanzar_http(exc)


@router.patch("/{usuario_id}/rol", response_model=UsuarioLeer)
def cambiar_rol_usuario(
    usuario_id: int,
    datos: UsuarioCambiarRol,
    db: DatabaseSession,
    sesiones: SessionRepository,
    actor: PuedeCambiarRol,
) -> Usuario:
    try:
        return _servicio(db, sesiones).cambiar_rol(usuario_id, datos.rol, actor)
    except ErrorGestionUsuarios as exc:
        _lanzar_http(exc)


@router.patch("/{usuario_id}/estado", response_model=UsuarioLeer)
def cambiar_estado_usuario(
    usuario_id: int,
    datos: UsuarioCambiarEstado,
    db: DatabaseSession,
    sesiones: SessionRepository,
    actor: PuedeCambiarEstado,
) -> Usuario:
    try:
        return _servicio(db, sesiones).cambiar_estado(
            usuario_id,
            datos.activo,
            actor,
        )
    except ErrorGestionUsuarios as exc:
        _lanzar_http(exc)
