from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import requiere
from backend.core.permisos import Permiso
from backend.db.session import get_db
from backend.models.aliado import Aliado
from backend.models.enums import TipoAliado
from backend.models.usuario import Usuario
from backend.schemas.aliado import (
    AliadoActualizar,
    AliadoCambiarEstado,
    AliadoLeer,
    AliadoListado,
    AliadoPerfil,
)
from backend.services.aliados import (
    AliadoNoEncontrado,
    ConflictoAliado,
    ErrorAliado,
    FiltrosAliado,
    ReferenciaAliadoInvalida,
    ServicioAliados,
)

router = APIRouter(prefix="/aliados", tags=["Aliados"])
DatabaseSession = Annotated[Session, Depends(get_db)]
PuedeVer = Annotated[Usuario, requiere(Permiso.ALIADOS_VER)]
PuedeEditar = Annotated[Usuario, requiere(Permiso.ALIADOS_EDITAR)]
PuedeCambiarEstado = Annotated[Usuario, requiere(Permiso.ALIADOS_CAMBIAR_ESTADO)]


def _lanzar_http(exc: ErrorAliado) -> NoReturn:
    if isinstance(exc, AliadoNoEncontrado):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, ConflictoAliado):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if isinstance(exc, ReferenciaAliadoInvalida):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    raise exc


@router.get("", response_model=AliadoListado)
def listar_aliados(
    db: DatabaseSession,
    _: PuedeVer,
    buscar: Annotated[str | None, Query(max_length=200)] = None,
    tipo: TipoAliado | None = None,
    activo: bool | None = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
) -> AliadoListado:
    items, total = ServicioAliados(db).listar(
        FiltrosAliado(buscar, tipo, activo, limite, desplazamiento)
    )
    return AliadoListado(
        items=[AliadoLeer.model_validate(item) for item in items], total=total
    )


@router.get("/{aliado_id}", response_model=AliadoPerfil)
def obtener_aliado(
    aliado_id: int, db: DatabaseSession, _: PuedeVer
) -> Aliado:
    try:
        return ServicioAliados(db).obtener(aliado_id, perfil=True)
    except ErrorAliado as exc:
        _lanzar_http(exc)


@router.patch("/{aliado_id}", response_model=AliadoLeer)
def actualizar_aliado(
    aliado_id: int,
    datos: AliadoActualizar,
    db: DatabaseSession,
    _: PuedeEditar,
) -> Aliado:
    try:
        return ServicioAliados(db).actualizar(aliado_id, datos)
    except ErrorAliado as exc:
        _lanzar_http(exc)


@router.patch("/{aliado_id}/estado", response_model=AliadoLeer)
def cambiar_estado_aliado(
    aliado_id: int,
    datos: AliadoCambiarEstado,
    db: DatabaseSession,
    _: PuedeCambiarEstado,
) -> Aliado:
    try:
        return ServicioAliados(db).cambiar_estado(aliado_id, datos.activo)
    except ErrorAliado as exc:
        _lanzar_http(exc)
