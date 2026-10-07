from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.models.enums import EstadoConvenio, EstadoSeguimientoRenovacion


class SeguimientoRenovacionLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    convenio_id: int
    codigo: str | None
    objeto: str | None
    aliado: str | None
    fecha_inicio: date | None
    fecha_vencimiento: date | None
    estado_convenio: EstadoConvenio
    estado_seguimiento: EstadoSeguimientoRenovacion
    tipo_convenio: str | None
    convenio_renovacion_id: int | None
    codigo_renovacion: str | None
    numero_renovacion: int | None
    etapa_renovacion: str | None


class RenovacionIniciadaLeer(BaseModel):
    convenio_origen_id: int
    convenio_renovacion_id: int
    codigo: str | None
    numero_renovacion: int
    estado: EstadoConvenio
    etapa: str


class DecisionNoRenovacionLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    convenio_id: int
    fecha_vencimiento_origen: date
    decidida_por_id: int
    decidida_en: datetime
    estado_seguimiento: Literal[EstadoSeguimientoRenovacion.NO_SE_RENOVARA] = (
        EstadoSeguimientoRenovacion.NO_SE_RENOVARA
    )
