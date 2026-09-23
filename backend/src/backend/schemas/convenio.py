from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.enums import AlcanceConvenio, EstadoConvenio


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
