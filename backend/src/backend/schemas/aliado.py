import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.models.aliado import EstadoAliado, EstadoConvenio


class ConvenioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    titulo: str
    tipo_convenio: str | None = None
    estado: EstadoConvenio
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    creado_en: datetime


class AliadoDetalleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    nit_o_identificacion: str | None = None
    tipo_aliado: str | None = None
    estado: EstadoAliado
    descripcion: str | None = None
    creado_en: datetime
    convenios: list[ConvenioRead] = []
