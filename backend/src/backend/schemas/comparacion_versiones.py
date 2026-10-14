from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from backend.schemas.convenio import UsuarioResumen


class DocumentoVersionLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    nombre_archivo: str
    tipo_mime: str
    tamano_bytes: int


class VersionComparadaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    numero: int
    radicada_en: datetime
    radicada_por: UsuarioResumen


class CambioCampo(BaseModel):
    campo: str
    etiqueta: str
    valor_anterior: Any = None
    valor_nuevo: Any = None


class DocumentoSustituido(BaseModel):
    tipo: str
    anterior: DocumentoVersionLeer
    nuevo: DocumentoVersionLeer


class CambiosDocumentos(BaseModel):
    agregados: list[DocumentoVersionLeer] = []
    eliminados: list[DocumentoVersionLeer] = []
    sustituidos: list[DocumentoSustituido] = []


class ComparacionVersiones(BaseModel):
    solicitud_id: int
    version_base: VersionComparadaLeer
    version_comparada: VersionComparadaLeer
    hay_cambios: bool
    campos: list[CambioCampo]
    documentos: CambiosDocumentos
