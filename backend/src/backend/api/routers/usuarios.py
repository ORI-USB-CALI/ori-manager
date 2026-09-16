import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from backend.api.deps import requiere
from backend.core.permisos import Permiso, Rol
from backend.core.security import get_password_hash, validar_password
from backend.db.session import get_db
from backend.models.user import User

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

Administrador = Annotated[User, requiere(Permiso.USUARIOS_GESTIONAR)]
DatabaseSession = Annotated[DBSession, Depends(get_db)]


Password = Annotated[str, AfterValidator(validar_password)]


class UsuarioLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_active: bool
    rol: Rol


class UsuarioCrear(BaseModel):
    email: EmailStr
    password: Password
    rol: Rol


class UsuarioEditar(BaseModel):
    email: EmailStr | None = None
    password: Password | None = None
    rol: Rol | None = None
    is_active: bool | None = None


def _guardar(db: DBSession, usuario: User) -> User:
    # Savepoint: un correo duplicado solo deshace este flush, no toda la sesión.
    try:
        with db.begin_nested():
            db.add(usuario)
            db.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo") from exc
    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("", response_model=list[UsuarioLeer])
def listar_usuarios(db: DatabaseSession, _: Administrador) -> list[User]:
    return list(db.scalars(select(User).order_by(User.email)))


@router.post("", response_model=UsuarioLeer, status_code=status.HTTP_201_CREATED)
def crear_usuario(datos: UsuarioCrear, db: DatabaseSession, _: Administrador) -> User:
    usuario = User(
        email=datos.email,
        hashed_password=get_password_hash(datos.password),
        rol=datos.rol,
    )
    return _guardar(db, usuario)


@router.patch("/{usuario_id}", response_model=UsuarioLeer)
def editar_usuario(
    usuario_id: uuid.UUID, datos: UsuarioEditar, db: DatabaseSession, admin: Administrador
) -> User:
    usuario = db.get(User, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")

    cambios = datos.model_dump(exclude_none=True)
    # Solo un admin gestiona usuarios y no puede quitarse el rol ni desactivarse:
    # siempre queda al menos un admin activo.
    if usuario.id == admin.id and (
        cambios.get("rol", usuario.rol) != usuario.rol or cambios.get("is_active") is False
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No puede cambiar su propio rol ni desactivarse"
        )

    if "password" in cambios:
        usuario.hashed_password = get_password_hash(cambios.pop("password"))
    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)
    return _guardar(db, usuario)
