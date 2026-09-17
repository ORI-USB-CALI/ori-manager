from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.models.enums import EstadoAliado, TipoAliado


class AliadoCrear(BaseModel):
    identificacion: str
    nombre: str
    tipo: TipoAliado
    sector_economico: str | None = None
    pais_id: int | None = None
    ciudad: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    correo: str | None = None
    sitio_web: str | None = None


class AliadoEditar(BaseModel):
    nombre: str | None = None
    tipo: TipoAliado | None = None
    sector_economico: str | None = None
    pais_id: int | None = None
    ciudad: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    correo: str | None = None
    sitio_web: str | None = None


class AliadoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identificacion: str
    nombre: str
    tipo: TipoAliado
    sector_economico: str | None
    pais_id: int | None
    ciudad: str | None
    direccion: str | None
    telefono: str | None
    correo: str | None
    sitio_web: str | None
    estado: EstadoAliado
    creado_en: datetime
    actualizado_en: datetime


class AliadoListado(BaseModel):
    """Página del listado más el total que cumple el filtro."""

    items: list[AliadoLeer]
    total: int
