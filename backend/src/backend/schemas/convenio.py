from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ConvenioCreate(BaseModel):
    """Datos de entrada para crear un convenio (CA-01), con el esquema
    completo de "convenio" segun el MER.

    """

    solicitud_id: int
    aliado_id: int | None = None
    creado_por_id: int

    codigo: str | None = None
    tipo_convenio_id: int | None = None
    etapa_actual_id: int | None = None
    objeto: str | None = None
    alcance: str | None = None
    unidad_organizacional_id: int | None = None
    implicacion_financiera: str | None = None
    fecha_inicio: date | None = None
    fecha_vencimiento: date | None = None
    fecha_firma: date | None = None
    duracion_meses: int | None = None
    porcentaje_avance: int | None = None
    convenio_origen_id: int | None = None
    numero_renovacion: int | None = None


class ConvenioRead(BaseModel):
    """Datos de salida al consultar un convenio (CA-06), con el esquema
    completo de "convenio" segun el MER.

    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str | None
    solicitud_id: int
    aliado_id: int | None
    tipo_convenio_id: int | None
    etapa_actual_id: int | None
    estado: str
    objeto: str | None
    alcance: str | None
    unidad_organizacional_id: int | None
    implicacion_financiera: str | None
    fecha_inicio: date | None
    fecha_vencimiento: date | None
    fecha_firma: date | None
    duracion_meses: int | None
    porcentaje_avance: int | None
    convenio_origen_id: int | None
    numero_renovacion: int | None
    creado_por_id: int
    creado_en: datetime
    actualizado_en: datetime


__all__ = ["ConvenioCreate", "ConvenioRead"]
