from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.enums import EstadoConvenio
from backend.schemas.convenio import UsuarioResumen


class EvaluacionConvenioCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fue_funcional: bool
    # RN-08: 1 es cumplimiento muy bajo, 10 cumplimiento total. El rango también
    # vive como CheckConstraint en la tabla.
    calificacion: int = Field(ge=1, le=10)
    observaciones: str = Field(min_length=1, max_length=4000)

    @field_validator("observaciones")
    @classmethod
    def validar_observaciones(cls, valor: str) -> str:
        normalizada = valor.strip()
        if not normalizada:
            raise ValueError("Los comentarios de la evaluación son obligatorios")
        return normalizada


class EvaluacionConvenioLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convenio_id: int
    fue_funcional: bool
    calificacion: int
    observaciones: str
    evaluado_por_id: int
    evaluado_por: UsuarioResumen
    creado_en: datetime


class EstadoEvaluacionLeer(BaseModel):
    """Estado de la evaluación de un convenio.

    Expone `evaluable` para que el frontend no reimplemente la regla de
    elegibilidad: cuando se amplíen los estados evaluables, la interfaz sigue
    funcionando sin cambios.
    """

    evaluable: bool
    estado_convenio: EstadoConvenio
    evaluacion: EvaluacionConvenioLeer | None
