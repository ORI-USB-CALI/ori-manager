from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from backend.core.permisos import Permiso
from backend.core.roles import TipoUsuario
from backend.core.unidades_organizacionales import TipoUnidad
from backend.schemas.usuario import Contrasena, RolLeer


class LoginSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correo: EmailStr
    contrasena: str


class RegistroSolicitante(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    correo: EmailStr
    contrasena: Contrasena
    confirmacion_contrasena: str
    nombre_completo: str = Field(min_length=1, max_length=160)
    cargo: str = Field(min_length=1, max_length=120)
    unidad_organizacional_id: int | None = None
    documento_identidad: str | None = Field(default=None, max_length=40)
    entidad_externa: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validar_registro(self) -> "RegistroSolicitante":
        if self.contrasena != self.confirmacion_contrasena:
            raise ValueError("Las contraseñas no coinciden")
        dominio = str(self.correo).rsplit("@", 1)[1].lower()
        es_interno = dominio in {"correo.usbcali.edu.co", "usbcali.edu.co"}
        if es_interno and self.unidad_organizacional_id is None:
            raise ValueError("La unidad organizacional es obligatoria")
        if not es_interno:
            if not self.documento_identidad:
                raise ValueError("El documento de identidad es obligatorio")
            if not self.entidad_externa:
                raise ValueError("La entidad externa es obligatoria")
        return self


class UnidadRegistroLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoUnidad


class TokenVerificacionSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)


class ReenvioVerificacionSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correo: EmailStr


class MensajePublico(BaseModel):
    message: str


class RegistroSolicitanteRespuesta(BaseModel):
    estado: Literal["VERIFICACION_PENDIENTE"]
    mensaje: str
    tipo_usuario: TipoUsuario


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
