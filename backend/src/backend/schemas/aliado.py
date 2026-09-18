from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from backend.models.enums import EstadoConvenio, TipoAliado


class AliadoActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    tipo: TipoAliado | None = None
    sector_economico: str | None = Field(default=None, max_length=120)
    pais_id: int | None = None
    ciudad: str | None = Field(default=None, max_length=120)
    direccion: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)
    correo: EmailStr | None = None
    sitio_web: str | None = Field(default=None, max_length=200)


class AliadoCambiarEstado(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activo: bool


class ConvenioAliadoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str | None
    estado: EstadoConvenio
    objeto: str | None
    fecha_inicio: date | None
    fecha_vencimiento: date | None
    fecha_firma: date | None
    tipo_convenio_id: int | None
    tipo_convenio: "TipoConvenioResumen | None"


class TipoConvenioResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nombre: str


class AliadoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoAliado
    sector_economico: str | None
    identificacion: str
    pais_id: int | None
    ciudad: str | None
    direccion: str | None
    telefono: str | None
    correo: EmailStr | None
    sitio_web: str | None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime


class AliadoPerfil(AliadoLeer):
    convenios: list[ConvenioAliadoLeer]


class AliadoListado(BaseModel):
    items: list[AliadoLeer]
    total: int


class DatosContraparteSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identificacion: str = Field(min_length=1, max_length=40)
    nombre: str = Field(min_length=1, max_length=200)
    tipo: TipoAliado
    correo: EmailStr | None = None
    sector_economico: str | None = Field(default=None, max_length=120)
    pais_id: int | None = None
    ciudad: str | None = Field(default=None, max_length=120)
    direccion: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)
    sitio_web: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validar_sector(self) -> "DatosContraparteSolicitud":
        if self.tipo == TipoAliado.EMPRESA and not self.sector_economico:
            raise ValueError("sector_economico es obligatorio para una EMPRESA")
        return self


ConvenioAliadoLeer.model_rebuild()
