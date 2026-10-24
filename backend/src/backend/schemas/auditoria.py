from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.models.enums import AccionAuditoria, EjecucionAuditoria


class UsuarioAuditoriaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_completo: str
    correo: str


class RegistroAuditoriaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_hora: datetime
    # HT-09, CA-03: nulo únicamente en procesos automáticos sin usuario
    # originador (no se usa un usuario ficticio para representarlos).
    usuario: UsuarioAuditoriaLeer | None
    rol: str | None
    entidad: str
    registro_id: int
    accion: AccionAuditoria
    campo: str | None
    valor_anterior: str | None
    valor_nuevo: str | None
    contexto: str | None
    # HT-09: nulos en los registros previos a HT-09 (CA-07) y en los cambios
    # que no declaran una acción de negocio estructurada.
    evento: str | None
    etapa: str | None
    version: int | None
    ejecucion: EjecucionAuditoria | None
    responsable: UsuarioAuditoriaLeer | None


class AuditoriaListado(BaseModel):
    items: list[RegistroAuditoriaLeer]
    total: int
