from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActividadUtilizacionCrear(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fecha: date
    actividad: str = Field(min_length=1, max_length=200)
    descripcion: str = Field(min_length=1)
    responsable: str = Field(min_length=1, max_length=200)
    observaciones: str | None = None

    @field_validator("observaciones")
    @classmethod
    def observaciones_vacias_como_nulas(cls, valor: str | None) -> str | None:
        return valor or None


class ActividadUtilizacionLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convenio_id: int
    fecha: date
    actividad: str
    descripcion: str
    responsable: str
    observaciones: str | None
    registrado_por_id: int
    creado_en: datetime
