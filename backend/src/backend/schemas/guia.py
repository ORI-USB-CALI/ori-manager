from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.models.enums import CodigoGuia, EstadoGuia


class EstadoGuiaLeer(BaseModel):
    """HU-38. Sin registro, la guía está PENDIENTE y no tiene versión (RN-03)."""

    guia: CodigoGuia
    estado: EstadoGuia
    version: int | None
    actualizado_en: datetime | None


class EstadoGuiaActualizar(BaseModel):
    """Solo se registran estados finales; el usuario es siempre el de la sesión."""

    model_config = ConfigDict(extra="forbid")

    estado: Literal[EstadoGuia.COMPLETADO, EstadoGuia.OMITIDO]
    version: int = Field(ge=1)
