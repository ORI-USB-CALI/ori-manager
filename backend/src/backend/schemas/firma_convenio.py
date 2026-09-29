from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.models.enums import EstadoFirmaConvenio, RolFirmanteConvenio


class TokenFirmaConvenio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=512)


class AccesoFirmaConvenioLeer(BaseModel):
    identificador: str
    rol: RolFirmanteConvenio
    nombre_firmante: str
    cargo_firmante: str
    correo_firmante: str
    version_numero: int
    contenido: dict[str, Any]
    expira_en: datetime
    estado: EstadoFirmaConvenio


class FirmarConvenioPublico(TokenFirmaConvenio):
    firma: str = Field(min_length=1, max_length=1_500_000)
    confirmacion: Literal[True]


class FirmaConvenioRegistradaLeer(BaseModel):
    estado: EstadoFirmaConvenio
    fecha_firma: datetime
