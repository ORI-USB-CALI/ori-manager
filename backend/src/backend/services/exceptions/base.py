# NOTA DE INTEGRACION: mismo contenido que
# backend.services.exceptions.base en feature/HU-04-aliados. Se duplica
# aqui porque esa rama aun no esta fusionada con
# feature/hu-06-registro-base-convenio; al integrar, dejar una sola
# definicion compartida.


class PermisoDenegadoError(PermissionError):
    """El rol indicado no tiene permiso para realizar la operación."""


class NoEncontradoError(LookupError):
    """No existe un registro con el identificador solicitado."""
