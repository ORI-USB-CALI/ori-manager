from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.models.enums import AccionAuditoria


class UsuarioAuditoriaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_completo: str
    correo: str


class RegistroAuditoriaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_hora: datetime
    usuario: UsuarioAuditoriaLeer
    rol: str | None
    entidad: str
    registro_id: int
    accion: AccionAuditoria
    campo: str | None
    valor_anterior: str | None
    valor_nuevo: str | None
    contexto: str | None


class AuditoriaListado(BaseModel):
    items: list[RegistroAuditoriaLeer]
    total: int
