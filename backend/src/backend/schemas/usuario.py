from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from backend.core.roles import CodigoRol, TipoUsuario

Contrasena = Annotated[str, Field(min_length=8)]


class RolLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: CodigoRol
    nombre: str


class UsuarioCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correo: EmailStr
    contrasena: Contrasena
    nombre_completo: str = Field(min_length=1, max_length=160)
    rol: CodigoRol
    tipo_usuario: TipoUsuario
    documento_identidad: str | None = Field(default=None, max_length=40)
    telefono: str | None = Field(default=None, max_length=40)
    cargo: str | None = Field(default=None, max_length=120)
    unidad_organizacional_id: int | None = None
    entidad_externa: str | None = Field(default=None, max_length=160)


class UsuarioActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correo: EmailStr | None = None
    contrasena: Contrasena | None = None
    nombre_completo: str | None = Field(default=None, min_length=1, max_length=160)
    documento_identidad: str | None = Field(default=None, max_length=40)
    telefono: str | None = Field(default=None, max_length=40)
    cargo: str | None = Field(default=None, max_length=120)
    unidad_organizacional_id: int | None = None
    entidad_externa: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validar_campos_no_nulos(self) -> "UsuarioActualizar":
        for campo in ("correo", "contrasena", "nombre_completo"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"{campo} no puede ser nulo")
        return self


class UsuarioCambiarRol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rol: CodigoRol


class UsuarioCambiarEstado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activo: bool


class UsuarioLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    correo: EmailStr
    nombre_completo: str
    documento_identidad: str | None
    telefono: str | None
    cargo: str | None
    tipo_usuario: TipoUsuario
    entidad_externa: str | None
    activo: bool
    ultimo_acceso: datetime | None
    rol: RolLeer
    unidad_organizacional_id: int | None
