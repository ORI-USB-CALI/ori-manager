from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import requiere
from backend.core.permisos import Permiso
from backend.db.session import get_db
from backend.models.convenio import Convenio
from backend.models.usuario import Usuario
from backend.schemas.convenio import ConvenioActualizar, ConvenioCrear, ConvenioLeer
from backend.services.convenios import (
    ConvenioDuplicado,
    ConvenioNoEncontrado,
    ErrorConvenio,
    ReferenciaConvenioInvalida,
    ServicioConvenios,
    SolicitudNoAprobada,
)

router = APIRouter(prefix="/convenios", tags=["Convenios"])
DatabaseSession = Annotated[Session, Depends(get_db)]
PuedeVer = Annotated[Usuario, requiere(Permiso.CONVENIOS_VER)]
PuedeCrear = Annotated[Usuario, requiere(Permiso.CONVENIOS_CREAR)]
PuedeEditar = Annotated[Usuario, requiere(Permiso.CONVENIOS_EDITAR)]


def _lanzar_http(exc: ErrorConvenio) -> NoReturn:
    if isinstance(exc, ConvenioNoEncontrado):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, (ConvenioDuplicado, SolicitudNoAprobada)):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if isinstance(exc, ReferenciaConvenioInvalida):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    raise exc


@router.post("", response_model=ConvenioLeer, status_code=status.HTTP_201_CREATED)
def crear_convenio(
    datos: ConvenioCrear, db: DatabaseSession, usuario: PuedeCrear
) -> Convenio:
    try:
        return ServicioConvenios(db).crear(datos, usuario)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get("/{convenio_id}", response_model=ConvenioLeer)
def obtener_convenio(
    convenio_id: int, db: DatabaseSession, _: PuedeVer
) -> Convenio:
    try:
        return ServicioConvenios(db).obtener(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.patch("/{convenio_id}", response_model=ConvenioLeer)
def actualizar_convenio(
    convenio_id: int,
    datos: ConvenioActualizar,
    db: DatabaseSession,
    _: PuedeEditar,
) -> Convenio:
    try:
        return ServicioConvenios(db).actualizar(convenio_id, datos)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
