from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TokenRevisionContraparte(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=512)


class AccesoRevisionContraparteLeer(BaseModel):
    codigo_convenio: str | None
    objeto: str | None
    contraparte: str | None
    version_numero: int
    contenido: dict[str, Any]
    estado: str
    expira_en: datetime
    correo_destino: str


class DecisionRevisionContraparteBase(TokenRevisionContraparte):
    nombre_firmante: str = Field(min_length=1, max_length=160)
    cargo_firmante: str = Field(min_length=1, max_length=160)

    @field_validator("nombre_firmante", "cargo_firmante")
    @classmethod
    def normalizar_actor(cls, valor: str) -> str:
        normalizado = valor.strip()
        if not normalizado:
            raise ValueError("El nombre y el cargo son obligatorios")
        return normalizado


class AprobarRevisionContrapartePublica(DecisionRevisionContraparteBase):
    firma: str = Field(min_length=1, max_length=1_500_000)


class DevolverRevisionContrapartePublica(DecisionRevisionContraparteBase):
    observaciones: list[str] = Field(min_length=1, max_length=50)

    @field_validator("observaciones")
    @classmethod
    def normalizar_observaciones(cls, valores: list[str]) -> list[str]:
        normalizadas = [valor.strip() for valor in valores]
        if any(not valor for valor in normalizadas):
            raise ValueError("Cada observación debe tener contenido")
        return normalizadas


class DecisionRevisionContraparteLeer(BaseModel):
    estado: str
    resultado: str


class InvitacionRevisionContraparteLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    revision_convenio_id: int
    generada_por_id: int
    correo_destino: str
    correo_cc: str | None
    expira_en: datetime
    enviado_en: datetime | None
    utilizado_en: datetime | None
    revocado_en: datetime | None
    creado_en: datetime
