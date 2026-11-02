from pydantic import BaseModel, ConfigDict


class PaisLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_iso: str
    nombre: str
