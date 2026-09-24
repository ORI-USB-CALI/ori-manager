from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.enums import (
    AlcanceConvenio,
    EstadoConvenio,
    EstadoSolicitud,
    TipoSolicitante,
)


class ConvenioCamposEditables(BaseModel):
    codigo: str | None = Field(default=None, max_length=40)
    tipo_convenio_id: int | None = None
    objeto: str | None = None
    alcance: AlcanceConvenio | None = None
    unidad_organizacional_id: int | None = None
    implicacion_financiera: str | None = None
    fecha_inicio: date | None = None
    fecha_vencimiento: date | None = None
    fecha_firma: date | None = None
    duracion_meses: int | None = Field(default=None, ge=0)
    porcentaje_avance: int | None = Field(default=None, ge=0, le=100)
    convenio_origen_id: int | None = None
    numero_renovacion: int | None = Field(default=None, ge=0)


class ConvenioCrear(ConvenioCamposEditables):
    model_config = ConfigDict(extra="forbid")
    solicitud_id: int
    objeto: str = Field(min_length=1)


class ConvenioActualizar(ConvenioCamposEditables):
    model_config = ConfigDict(extra="forbid")


class UsuarioResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre_completo: str
    correo: str


class AliadoResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    identificacion: str
    activo: bool


class ConvenioLeer(ConvenioCamposEditables):
    model_config = ConfigDict(from_attributes=True)

    id: int
    solicitud_id: int
    aliado_id: int | None
    etapa_actual_id: int | None
    estado: EstadoConvenio
    creado_por_id: int
    creado_por: UsuarioResumen
    aliado: AliadoResumen | None
    creado_en: datetime
    actualizado_en: datetime


class EtapaResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    orden: int
    codigo: str
    nombre: str


class TipoConvenioResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nombre: str
    naturaleza: str | None


class UnidadOrganizacionalResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nombre: str
    tipo: str


class SolicitudAntecedenteLeer(BaseModel):
    """Solicitud que originó el convenio, como antecedente de solo lectura.

    HU-12 nunca modifica estos datos: la ORI redacta sobre el convenio y la
    solicitud se conserva tal como la radicó el solicitante (CA-04).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    consecutivo: str
    tipo_solicitante: TipoSolicitante
    estado: EstadoSolicitud
    objeto: str | None
    justificacion: str | None
    actividades_por_parte: str | None
    metas_esperadas: str | None
    implicacion_financiera: str | None
    vigencia_estimada: str | None
    requisitos_renovacion: str | None
    observaciones: str | None
    fecha_radicacion: datetime | None

    solicitante_nombre: str | None
    solicitante_correo: str | None
    solicitante_cargo: str | None
    solicitante_unidad: str | None
    solicitante_programa: str | None
    solicitante_entidad: str | None

    # Contraparte tal como se propuso: sigue visible aunque ya exista aliado formal.
    nombre_aliado_propuesto: str | None
    identificacion_aliado_propuesto: str | None
    tipo_aliado_propuesto: str | None
    correo_aliado_propuesto: str | None
    pais_aliado_propuesto: str | None
    ciudad_aliado_propuesto: str | None

    contacto_contraparte_nombre: str | None
    contacto_contraparte_cargo: str | None
    contacto_contraparte_telefono: str | None
    contacto_contraparte_correo: str | None

    # Supervisores como contexto. Su registro formal corresponde a HU-19.
    supervisor_usb_nombre: str | None
    supervisor_usb_cargo: str | None
    supervisor_usb_telefono: str | None
    supervisor_usb_correo: str | None
    supervisor_contraparte_nombre: str | None
    supervisor_contraparte_cargo: str | None
    supervisor_contraparte_telefono: str | None
    supervisor_contraparte_correo: str | None


class ConvenioElaboracionLeer(ConvenioLeer):
    """Vista de la etapa de Elaboración: el convenio más su antecedente."""

    solicitud: SolicitudAntecedenteLeer
    etapa_actual: EtapaResumen | None
    tipo_convenio: TipoConvenioResumen | None
    unidad_organizacional: UnidadOrganizacionalResumen | None


class CampoFaltante(BaseModel):
    campo: str
    motivo: str


class ValidacionElaboracionLeer(BaseModel):
    completo: bool
    faltantes: list[CampoFaltante]
