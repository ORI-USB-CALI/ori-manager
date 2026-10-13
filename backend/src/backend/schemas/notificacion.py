from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificacionLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    entidad_tipo: str
    entidad_id: int
    mensaje: str
    leida: bool
    leida_en: datetime | None
    resuelta: bool
    resuelta_en: datetime | None
    creado_en: datetime
