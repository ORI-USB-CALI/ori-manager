from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.enums import EstadoActividadConvenio


class ActividadUtilizacionCrear(BaseModel):
    """HU-35: actividad ya realizada, registrada en `actividad_convenio`."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fecha_ejecucion: date
    titulo: str = Field(min_length=1, max_length=200)
    descripcion: str = Field(min_length=1)
    responsable_nombre: str = Field(min_length=1, max_length=200)
    observaciones: str | None = None

    @field_validator("observaciones")
    @classmethod
    def observaciones_vacias_como_nulas(cls, valor: str | None) -> str | None:
        return valor or None


class ActividadUtilizacionLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convenio_id: int
    estado: EstadoActividadConvenio
    fecha_ejecucion: date | None
    titulo: str
    descripcion: str
    responsable_nombre: str | None
    observaciones: str | None
    registrado_por_id: int
    creado_en: datetime
