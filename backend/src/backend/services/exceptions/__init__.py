from backend.services.exceptions.aliado import (
    AliadoConConveniosVigentesError,
    AliadoDuplicadoError,
    AliadoNoEncontradoError,
    SectorEconomicoRequeridoError,
)
from backend.services.exceptions.base import NoEncontradoError, PermisoDenegadoError
from backend.services.exceptions.contacto_aliado import ContactoNoEncontradoError

__all__ = [
    "AliadoConConveniosVigentesError",
    "AliadoDuplicadoError",
    "AliadoNoEncontradoError",
    "ContactoNoEncontradoError",
    "NoEncontradoError",
    "PermisoDenegadoError",
    "SectorEconomicoRequeridoError",
]
