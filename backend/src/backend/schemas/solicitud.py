from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend.core.roles import TipoUsuario
from backend.core.unidades_organizacionales import TipoUnidad
from backend.models.enums import (
    EstadoSolicitud,
    TipoAliado,
    TipoDocumentoSolicitud,
    TipoIdentificacion,
    TipoSolicitante,
)


class SolicitudCampos(BaseModel):
    solicitante_nombre: str | None = Field(default=None, max_length=160)
    solicitante_correo: EmailStr | None = None
    solicitante_documento: str | None = Field(default=None, max_length=40)
    solicitante_cargo: str | None = Field(default=None, max_length=120)
    solicitante_entidad: str | None = Field(default=None, max_length=160)
    solicitante_unidad: str | None = Field(default=None, max_length=160)
    solicitante_programa: str | None = Field(default=None, max_length=160)
    nombre_aliado_propuesto: str | None = Field(default=None, max_length=200)
    tipo_identificacion_aliado_propuesto: TipoIdentificacion | None = None
    identificacion_aliado_propuesto: str | None = Field(default=None, max_length=40)
    tipo_aliado_propuesto: TipoAliado | None = None
    correo_aliado_propuesto: EmailStr | None = None
    pais_aliado_propuesto: str | None = Field(default=None, max_length=80)
    ciudad_aliado_propuesto: str | None = Field(default=None, max_length=120)
    telefono_aliado_propuesto: str | None = Field(default=None, max_length=40)
    direccion_aliado_propuesto: str | None = Field(default=None, max_length=200)
    sector_economico_aliado_propuesto: str | None = Field(default=None, max_length=120)
    contacto_contraparte_nombre: str | None = Field(default=None, max_length=160)
    contacto_contraparte_cargo: str | None = Field(default=None, max_length=120)
    contacto_contraparte_telefono: str | None = Field(default=None, max_length=40)
    contacto_contraparte_correo: EmailStr | None = None
    tipo_convenio_id: int | None = None
    justificacion: str | None = None
    objeto: str | None = None
    actividades_por_parte: str | None = None
    metas_esperadas: str | None = None
    implicacion_financiera: str | None = None
    vigencia_estimada: str | None = Field(default=None, max_length=120)
    requisitos_renovacion: str | None = None
    supervisor_usb_nombre: str | None = Field(default=None, max_length=160)
    supervisor_usb_cargo: str | None = Field(default=None, max_length=120)
    supervisor_usb_telefono: str | None = Field(default=None, max_length=40)
    supervisor_usb_correo: EmailStr | None = None
    supervisor_contraparte_nombre: str | None = Field(default=None, max_length=160)
    supervisor_contraparte_cargo: str | None = Field(default=None, max_length=120)
    supervisor_contraparte_telefono: str | None = Field(default=None, max_length=40)
    supervisor_contraparte_correo: EmailStr | None = None
    observaciones: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def limpiar_texto(cls, valor: object) -> object:
        if isinstance(valor, str):
            return valor.strip() or None
        return valor


class SolicitudCrear(SolicitudCampos):
    model_config = ConfigDict(extra="forbid")


class SolicitudActualizar(SolicitudCampos):
    model_config = ConfigDict(extra="forbid")


class DocumentoSolicitudLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    tipo_documento: TipoDocumentoSolicitud = Field(validation_alias="tipo")
    nombre_original: str = Field(validation_alias="nombre_archivo")
    tipo_mime: str
    tamano_bytes: int
    creado_en: datetime


class SolicitudLeer(SolicitudCampos):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consecutivo: str
    tipo_solicitante: TipoSolicitante
    solicitante_id: int
    unidad_organizacional_id: int | None
    estado: EstadoSolicitud
    fecha_radicacion: datetime | None
    fecha_recibido_ori: datetime | None
    documentos: list[DocumentoSolicitudLeer]
    creado_en: datetime
    actualizado_en: datetime


class SolicitudListado(BaseModel):
    items: list[SolicitudLeer]
    total: int


class SolicitudRecibidaLeer(SolicitudLeer):
    convenio_id: int | None
    tipo_convenio_nombre: str | None


class SolicitudRecibidaListado(BaseModel):
    items: list[SolicitudRecibidaLeer]
    total: int


class TipoConvenioOpcion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nombre: str
    naturaleza: str | None


class TipoDocumentoOpcion(BaseModel):
    codigo: TipoDocumentoSolicitud
    nombre: str
    es_representacion_legal: bool


class PerfilSolicitante(BaseModel):
    tipo_usuario: TipoUsuario
    tipo_unidad: TipoUnidad | None
    nombre: str
    correo: str
    identificacion: str | None
    entidad: str | None
    cargo: str | None
    unidad: str | None
    programa: str | None


class CatalogosSolicitud(BaseModel):
    solicitante: PerfilSolicitante
    tipos_convenio: list[TipoConvenioOpcion]
    tipos_documento: list[TipoDocumentoOpcion]
    requiere_documento_representacion: bool = True
