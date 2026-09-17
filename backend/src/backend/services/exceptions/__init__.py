from backend.services.exceptions.base import NoEncontradoError, PermisoDenegadoError
from backend.services.exceptions.convenio import (
    AliadoInvalidoError,
    ConvenioDuplicadoError,
    ConvenioNoEncontradoError,
    SolicitudInvalidaError,
    UnidadOrganizacionalRequeridaError,
)

__all__ = [
    "AliadoInvalidoError",
    "ConvenioDuplicadoError",
    "ConvenioNoEncontradoError",
    "NoEncontradoError",
    "PermisoDenegadoError",
    "SolicitudInvalidaError",
    "UnidadOrganizacionalRequeridaError",
]
