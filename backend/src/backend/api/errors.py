from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from backend.services.exceptions import (
    AliadoConConveniosVigentesError,
    AliadoDuplicadoError,
    NoEncontradoError,
    PermisoDenegadoError,
    SectorEconomicoRequeridoError,
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

    @app.exception_handler(AliadoDuplicadoError)
    def _duplicado(request: Request, exc: AliadoDuplicadoError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
        )

    @app.exception_handler(AliadoConConveniosVigentesError)
    def _convenios_vigentes(
        request: Request, exc: AliadoConConveniosVigentesError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
        )

    @app.exception_handler(SectorEconomicoRequeridoError)
    def _sector_requerido(
        request: Request, exc: SectorEconomicoRequeridoError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)}
        )
