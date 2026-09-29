from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.firma_convenio import (
    AccesoFirmaConvenioLeer,
    FirmaConvenioRegistradaLeer,
    FirmarConvenioPublico,
    TokenFirmaConvenio,
)
from backend.services.firma_electronica import (
    EnlaceFirmaConvenioError,
    FirmaElectronicaInvalida,
    ServicioFirmaElectronica,
)

router = APIRouter(
    prefix="/public/firma-convenio",
    tags=["Firma electrónica pública de convenio"],
)
DatabaseSession = Annotated[Session, Depends(get_db)]


def _error_enlace(exc: EnlaceFirmaConvenioError) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"codigo": exc.codigo},
    ) from exc


@router.post("/acceso", response_model=AccesoFirmaConvenioLeer)
def acceder(datos: TokenFirmaConvenio, db: DatabaseSession) -> AccesoFirmaConvenioLeer:
    try:
        contexto = ServicioFirmaElectronica(db).acceder(datos.token)
    except EnlaceFirmaConvenioError as exc:
        _error_enlace(exc)
    firma = contexto.firma
    if not firma.nombre_firmante or not firma.cargo_firmante or not firma.correo_firmante:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La identidad de la firma electrónica no está configurada",
        )
    return AccesoFirmaConvenioLeer(
        identificador=contexto.convenio.codigo or f"#{contexto.convenio.id}",
        rol=firma.rol_firmante,
        nombre_firmante=firma.nombre_firmante,
        cargo_firmante=firma.cargo_firmante,
        correo_firmante=firma.correo_firmante,
        version_numero=contexto.version.numero,
        contenido=contexto.version.contenido,
        expira_en=contexto.invitacion.expira_en,
        estado=firma.estado,
    )


@router.post("/firmar", response_model=FirmaConvenioRegistradaLeer)
def firmar(
    datos: FirmarConvenioPublico, db: DatabaseSession
) -> FirmaConvenioRegistradaLeer:
    try:
        firma = ServicioFirmaElectronica(db).firmar(
            datos.token, datos.firma, datos.confirmacion
        )
    except EnlaceFirmaConvenioError as exc:
        _error_enlace(exc)
    except FirmaElectronicaInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if firma.fecha_firma is None:
        raise RuntimeError("La firma no registró su fecha de evidencia")
    return FirmaConvenioRegistradaLeer(
        estado=firma.estado,
        fecha_firma=firma.fecha_firma,
    )
