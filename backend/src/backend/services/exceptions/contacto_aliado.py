from backend.services.exceptions.base import NoEncontradoError


class ContactoNoEncontradoError(NoEncontradoError):
    """No existe un contacto con ese identificador para el aliado indicado."""
