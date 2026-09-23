from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import requiere
from backend.core.permisos import Permiso
from backend.db.session import get_db
from backend.models.historial_etapa import HistorialEtapa
from backend.models.revision_pendiente import RevisionPendiente
from backend.models.usuario import Usuario
from backend.schemas.revision_contraparte import (
    DevolucionContraparteCrear,
    HistorialEtapaLeer,
    RevisionPendienteLeer,
)
from backend.services.revision_contraparte import (
    ConvenioNoEncontrado,
    ErrorRevisionContraparte,
    ObservacionesRequeridas,
    RevisionJuridicaNoAprobada,
    RevisionPendienteNoEncontrada,
    ServicioRevisionContraparte,
    UsuarioNoAutorizado,
)

router = APIRouter(prefix="/convenios/{convenio_id}/revision-contraparte", tags=["Revisión de contraparte"])
DatabaseSession = Annotated[Session, Depends(get_db)]
PuedeGestionar = Annotated[Usuario, requiere(Permiso.CONVENIOS_GESTIONAR_REVISION_CONTRAPARTE)]
PuedeRevisarPropia = Annotated[Usuario, requiere(Permiso.CONVENIOS_REVISAR_CONTRAPARTE_PROPIA)]


def _lanzar_http(exc: ErrorRevisionContraparte) -> NoReturn:
    if isinstance(exc, (ConvenioNoEncontrado, RevisionPendienteNoEncontrada)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, UsuarioNoAutorizado):
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    if isinstance(exc, RevisionJuridicaNoAprobada):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if isinstance(exc, ObservacionesRequeridas):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    raise exc


@router.post("/envios", response_model=HistorialEtapaLeer, status_code=status.HTTP_201_CREATED)
def registrar_envio(
    convenio_id: int, db: DatabaseSession, usuario: PuedeGestionar
) -> HistorialEtapa:
    try:
        return ServicioRevisionContraparte(db).registrar_envio(convenio_id, usuario)
    except ErrorRevisionContraparte as exc:
        _lanzar_http(exc)


@router.post("/aprobacion", response_model=RevisionPendienteLeer, status_code=status.HTTP_201_CREATED)
def aprobar(
    convenio_id: int, db: DatabaseSession, usuario: PuedeRevisarPropia
) -> RevisionPendiente:
    try:
        return ServicioRevisionContraparte(db).aprobar(convenio_id, usuario)
    except ErrorRevisionContraparte as exc:
        _lanzar_http(exc)


@router.post("/devolucion", response_model=RevisionPendienteLeer, status_code=status.HTTP_201_CREATED)
def devolver_con_observaciones(
    convenio_id: int, datos: DevolucionContraparteCrear, db: DatabaseSession, usuario: PuedeRevisarPropia
) -> RevisionPendiente:
    try:
        return ServicioRevisionContraparte(db).devolver_con_observaciones(
            convenio_id, datos.observaciones, usuario
        )
    except ErrorRevisionContraparte as exc:
        _lanzar_http(exc)
