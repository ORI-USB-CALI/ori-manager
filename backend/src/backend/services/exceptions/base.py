class PermisoDenegadoError(PermissionError):
    """El rol indicado no tiene permiso para realizar la operación."""


class NoEncontradoError(LookupError):
    """No existe un registro con el identificador solicitado."""
