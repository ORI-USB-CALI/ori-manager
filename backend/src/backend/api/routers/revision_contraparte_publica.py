from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.revision_contraparte import (
    AccesoRevisionContraparteLeer,
    AprobarRevisionContrapartePublica,
    DecisionRevisionContraparteLeer,
    DevolverRevisionContrapartePublica,
    TokenRevisionContraparte,
)
from backend.services.contraparte_externa import (
    DecisionContraparteInvalida,
    EnlaceContraparteError,
    ServicioContraparteExterna,
)

router = APIRouter(
    prefix="/public/revision-contraparte",
    tags=["Revisión pública de contraparte"],
)
DatabaseSession = Annotated[Session, Depends(get_db)]


def _error_enlace(exc: EnlaceContraparteError) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"codigo": exc.codigo},
    ) from exc


@router.post("/acceso", response_model=AccesoRevisionContraparteLeer)
def acceder(datos: TokenRevisionContraparte, db: DatabaseSession):
    try:
        contexto = ServicioContraparteExterna(db).acceder(datos.token)
    except EnlaceContraparteError as exc:
        _error_enlace(exc)
    solicitud = contexto.convenio.solicitud
    return AccesoRevisionContraparteLeer(
        codigo_convenio=contexto.convenio.codigo,
        objeto=contexto.convenio.objeto,
        contraparte=solicitud.nombre_aliado_propuesto,
        version_numero=contexto.version.numero,
        contenido=contexto.version.contenido,
        estado=contexto.revision.estado,
        expira_en=contexto.invitacion.expira_en,
        correo_destino=contexto.invitacion.correo_destino,
    )


@router.post("/aprobar", response_model=DecisionRevisionContraparteLeer)
def aprobar(datos: AprobarRevisionContrapartePublica, db: DatabaseSession):
    try:
        revision = ServicioContraparteExterna(db).aprobar(
            datos.token,
            datos.nombre_firmante,
            datos.cargo_firmante,
            datos.firma,
        )
    except EnlaceContraparteError as exc:
        _error_enlace(exc)
    except DecisionContraparteInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return DecisionRevisionContraparteLeer(
        estado=revision.estado,
        resultado=revision.resultado or "",
    )


@router.post("/devolver", response_model=DecisionRevisionContraparteLeer)
def devolver(datos: DevolverRevisionContrapartePublica, db: DatabaseSession):
    try:
        revision = ServicioContraparteExterna(db).devolver(
            datos.token,
            datos.nombre_firmante,
            datos.cargo_firmante,
            datos.observaciones,
        )
    except EnlaceContraparteError as exc:
        _error_enlace(exc)
    except DecisionContraparteInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return DecisionRevisionContraparteLeer(
        estado=revision.estado,
        resultado=revision.resultado or "",
    )
