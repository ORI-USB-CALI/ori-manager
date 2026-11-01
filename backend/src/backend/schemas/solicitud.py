from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
)

from backend.core.roles import TipoUsuario
from backend.core.unidades_organizacionales import TipoUnidad
from backend.core.validaciones import identificacion_completa
from backend.models.enums import (
    EstadoConvenio,
    EstadoSolicitud,
    TipoAliado,
    TipoDocumentoSolicitud,
    TipoIdentificacion,
    TipoSolicitante,
)
from backend.schemas.convenio import EtapaResumen


class SolicitudCamposEditables(BaseModel):
    """Campos que el solicitante escribe. HT-14: el país se elige por id del
    catálogo y el DV del NIT va aparte de la identificación."""

    solicitante_nombre: str | None = Field(default=None, max_length=160)
    solicitante_correo: EmailStr | None = None
    solicitante_tipo_documento: TipoIdentificacion | None = None
    solicitante_documento: str | None = Field(default=None, max_length=40)
    solicitante_digito_verificacion: str | None = Field(default=None, max_length=1)
    solicitante_cargo: str | None = Field(default=None, max_length=120)
    solicitante_entidad: str | None = Field(default=None, max_length=160)
    solicitante_unidad: str | None = Field(default=None, max_length=160)
    solicitante_programa: str | None = Field(default=None, max_length=160)
    nombre_aliado_propuesto: str | None = Field(default=None, max_length=200)
    tipo_identificacion_aliado_propuesto: TipoIdentificacion | None = None
    identificacion_aliado_propuesto: str | None = Field(default=None, max_length=40)
    digito_verificacion_aliado_propuesto: str | None = Field(default=None, max_length=1)
    tipo_aliado_propuesto: TipoAliado | None = None
    correo_aliado_propuesto: EmailStr | None = None
    pais_aliado_propuesto_id: int | None = None
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


class SolicitudCampos(SolicitudCamposEditables):
    """Campos que se guardan en cada versión radicada. El nombre del país lo
    completa el backend desde el catálogo (HT-14)."""

    pais_aliado_propuesto: str | None = Field(default=None, max_length=80)


class SolicitudCrear(SolicitudCamposEditables):
    model_config = ConfigDict(extra="forbid")


class SolicitudActualizar(SolicitudCamposEditables):
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
    motivo_rechazo: str | None
    observaciones_devolucion: str | None
    decidida_por_id: int | None
    fecha_decision: datetime | None
    documentos: list[DocumentoSolicitudLeer]
    creado_en: datetime
    actualizado_en: datetime

    @computed_field
    @property
    def identificacion_aliado_propuesto_completa(self) -> str | None:
        return identificacion_completa(
            self.tipo_identificacion_aliado_propuesto,
            self.identificacion_aliado_propuesto,
            self.digito_verificacion_aliado_propuesto,
        )

    @computed_field
    @property
    def solicitante_documento_completo(self) -> str | None:
        return identificacion_completa(
            self.solicitante_tipo_documento,
            self.solicitante_documento,
            self.solicitante_digito_verificacion,
        )


class SolicitudListado(BaseModel):
    items: list[SolicitudLeer]
    total: int


class SolicitudRecibidaLeer(SolicitudLeer):
    convenio_id: int | None
    convenio_estado: EstadoConvenio | None
    convenio_etapa: EtapaResumen | None
    tipo_convenio_nombre: str | None
    decidida_por_nombre: str | None


class SolicitudRechazar(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    motivo: str = Field(min_length=1, max_length=2000)


class SolicitudDevolver(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    observaciones: str = Field(min_length=1, max_length=2000)


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


class DevolucionSolicitudLeer(BaseModel):
    observaciones: str
    devuelta_por_nombre: str
    devuelta_en: datetime
    corregida_en_version: int | None


class VersionSolicitudHistorialLeer(BaseModel):
    numero: int
    radicada_en: datetime
    devolucion: DevolucionSolicitudLeer | None


class HistorialSolicitudLeer(BaseModel):
    solicitud_id: int
    consecutivo: str
    estado: str
    versiones: list[VersionSolicitudHistorialLeer]
