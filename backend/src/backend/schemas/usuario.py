from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CodigoRol(StrEnum):
    """Roles internos definidos por el sistema (HU-03, CA-05)."""

    ADMINISTRADOR_ORI = "ADMINISTRADOR_ORI"
    GESTOR_ORI = "GESTOR_ORI"
    REVISOR_ORI = "REVISOR_ORI"


class RolLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: CodigoRol
    nombre: str


class UsuarioCrear(BaseModel):
    """Datos obligatorios para crear un usuario interno (CA-02, CA-03)."""

    correo: EmailStr
    contrasena: str = Field(min_length=8)
    nombre_completo: str = Field(min_length=1, max_length=160)
    rol: CodigoRol
    documento_identidad: str | None = Field(default=None, max_length=40)
    telefono: str | None = Field(default=None, max_length=40)
    cargo: str | None = Field(default=None, max_length=120)


class UsuarioActualizar(BaseModel):
    """Campos editables. Los no enviados conservan su valor (CA-06)."""

    nombre_completo: str | None = Field(default=None, min_length=1, max_length=160)
    documento_identidad: str | None = Field(default=None, max_length=40)
    telefono: str | None = Field(default=None, max_length=40)
    cargo: str | None = Field(default=None, max_length=120)


class UsuarioCambiarRol(BaseModel):
    """Cambio de rol de un usuario interno (CA-07)."""

    rol: CodigoRol


class UsuarioLeer(BaseModel):
    """Representación de un usuario. Nunca expone la contraseña."""

    model_config = ConfigDict(from_attributes=True)

    correo: EmailStr
    nombre_completo: str
    documento_identidad: str | None
    telefono: str | None
    cargo: str | None
    rol: RolLeer
    activo: bool
    ultimo_acceso: datetime | None


class UsuarioListar(BaseModel):
    """Fila del listado de usuarios internos (CA-01)."""

    model_config = ConfigDict(from_attributes=True)

    correo: EmailStr
    nombre_completo: str
    rol: RolLeer
    activo: bool