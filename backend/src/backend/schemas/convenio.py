import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator

from backend.models.aliado import EstadoConvenio
from backend.schemas.aliado import ConvenioRead

__all__ = ["ConvenioCreate", "ConvenioEstadoUpdate", "ConvenioRead"]


class ConvenioCreate(BaseModel):
    """
    Datos para registrar un convenio nuevo.

    El estado no se recibe del cliente: todo convenio nuevo nace en
    EN_TRAMITE (nunca "vigente" desde su creación), de forma consistente
    con el MER de ORI Manager.
    """

    aliado_id: uuid.UUID
    codigo: str
    titulo: str
    tipo_convenio: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None

    @model_validator(mode="after")
    def _validar_fechas(self) -> "ConvenioCreate":
        if (
            self.fecha_inicio is not None
            and self.fecha_fin is not None
            and self.fecha_inicio > self.fecha_fin
        ):
            raise ValueError("fecha_inicio no puede ser posterior a fecha_fin")
        return self


class ConvenioEstadoUpdate(BaseModel):
    """Solicitud de cambio de estado de un convenio existente."""

    estado: EstadoConvenio
