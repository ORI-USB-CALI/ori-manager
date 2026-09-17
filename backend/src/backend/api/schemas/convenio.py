from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.models.enums import EstadoConvenio


class ConvenioDeAliadoLeer(BaseModel):
    """Convenio visto desde la ficha del aliado.

    La tabla `convenio` es mínima por ahora: código, título y vigencia se
    agregarán cuando la HU de convenios cree esas columnas.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    aliado_id: int | None
    estado: EstadoConvenio
    creado_en: datetime
    actualizado_en: datetime
