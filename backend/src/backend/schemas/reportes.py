from datetime import date

from pydantic import BaseModel, ConfigDict


class ActividadResumenLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    estado: str
    fecha_planificada: date | None
    fecha_ejecucion: date | None


class ConvenioReporteActivoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str | None
    objeto: str | None
    estado: str
    aliado: str | None
    tipo_convenio: str | None
    unidad_organizacional: str | None
    responsable: str | None
    fecha_inicio: date | None
    fecha_vencimiento: date | None
    actividades: list[ActividadResumenLeer]
