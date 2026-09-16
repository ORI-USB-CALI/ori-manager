from backend.services.exceptions.aliado import (
    AliadoConConveniosVigentesError,
    AliadoDuplicadoError,
    AliadoNoEncontradoError,
    SectorEconomicoRequeridoError,
)
from backend.services.exceptions.base import NoEncontradoError, PermisoDenegadoError

__all__ = [
    "AliadoConConveniosVigentesError",
    "AliadoDuplicadoError",
    "AliadoNoEncontradoError",
    "NoEncontradoError",
    "PermisoDenegadoError",
    "SectorEconomicoRequeridoError",
]
