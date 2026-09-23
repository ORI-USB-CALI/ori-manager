from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HistorialEtapaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convenio_id: int
    etapa_origen_id: int | None
    etapa_destino_id: int
    usuario_id: int
    numero_ciclo: int
    fecha_cambio: datetime


class DevolucionContraparteCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observaciones: list[str] = Field(min_length=1)


class RevisionPendienteLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convenio_id: int
    historial_etapa_id: int
    responsable_id: int
    estado: str
    resultado: str | None
    creado_en: datetime
    resuelta_en: datetime | None
