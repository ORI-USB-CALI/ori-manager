from backend.services.exceptions.base import NoEncontradoError


class AliadoNoEncontradoError(NoEncontradoError):
    """No existe un aliado con el identificador solicitado."""


class AliadoDuplicadoError(ValueError):
    """Ya existe un aliado registrado con esa identificación (NIT/documento)."""


class AliadoConConveniosVigentesError(ValueError):
    """El aliado no puede inactivarse porque tiene convenios vigentes."""


class SectorEconomicoRequeridoError(ValueError):
    """El sector económico es obligatorio para aliados de tipo empresa."""
