from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ContactoCrear(BaseModel):
    nombre: str
    cargo: str | None = None
    correo: str | None = None
    telefono: str | None = None
    extension: str | None = None
    es_principal: bool = False


class ContactoEditar(BaseModel):
    nombre: str | None = None
    cargo: str | None = None
    correo: str | None = None
    telefono: str | None = None
    extension: str | None = None
    es_principal: bool | None = None
    activo: bool | None = None


class ContactoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    aliado_id: int
    nombre: str
    cargo: str | None
    correo: str | None
    telefono: str | None
    extension: str | None
    es_principal: bool
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
