from pydantic import BaseModel, ConfigDict


class ConteoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    etiqueta: str
    cantidad: int


class ReporteEstadisticoConveniosLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    datos_suficientes: bool
    total_convenios: int
    por_estado_contractual: list[ConteoLeer]
    por_vigencia_activa: list[ConteoLeer]
    por_estado_aliado: list[ConteoLeer]
    por_tipo_aliado: list[ConteoLeer]
    por_pais: list[ConteoLeer]
