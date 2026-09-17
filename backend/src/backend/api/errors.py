from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from backend.services.exceptions import (
    AliadoInvalidoError,
    ConvenioDuplicadoError,
    NoEncontradoError,
    PermisoDenegadoError,
    SolicitudInvalidaError,
    UnidadOrganizacionalRequeridaError,
)


def registrar_manejadores_de_errores(app: FastAPI) -> None:
    """Traduce las excepciones de dominio/servicio a respuestas HTTP."""

    @app.exception_handler(PermisoDenegadoError)
    def _permiso_denegado(request: Request, exc: PermisoDenegadoError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)}
        )

    @app.exception_handler(NoEncontradoError)
    def _no_encontrado(request: Request, exc: NoEncontradoError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
        )

    @app.exception_handler(ConvenioDuplicadoError)
    def _convenio_duplicado(request: Request, exc: ConvenioDuplicadoError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
        )

    @app.exception_handler(AliadoInvalidoError)
    def _aliado_invalido(request: Request, exc: AliadoInvalidoError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)}
        )

    @app.exception_handler(SolicitudInvalidaError)
    def _solicitud_invalida(request: Request, exc: SolicitudInvalidaError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)}
        )

    @app.exception_handler(UnidadOrganizacionalRequeridaError)
    def _unidad_requerida(
        request: Request, exc: UnidadOrganizacionalRequeridaError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)}
        )
