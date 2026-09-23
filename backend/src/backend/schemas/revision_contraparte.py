from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HistorialEtapaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convenio_id: int
    etapa_origen_id: int | None
    etapa_destino_id: int
    usuario_id: int
    numero_ciclo: int
    fecha_cambio: datetime
