from pydantic import BaseModel, ConfigDict, EmailStr

from backend.core.permisos import Permiso
from backend.core.roles import TipoUsuario
from backend.schemas.usuario import RolLeer


class LoginSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correo: EmailStr
    contrasena: str


class MensajeAutenticacion(BaseModel):
    status: str
    message: str


class UsuarioActualLeer(BaseModel):
    id: int
    correo: EmailStr
    nombre_completo: str
    activo: bool
    tipo_usuario: TipoUsuario
    rol: RolLeer
    permisos: list[Permiso]
