from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import UsuarioActual
from backend.db.session import get_db
from backend.models.enums import CodigoGuia
from backend.schemas.guia import EstadoGuiaActualizar, EstadoGuiaLeer
from backend.services.guias import ServicioGuias

router = APIRouter(prefix="/guias", tags=["Guías"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[EstadoGuiaLeer])
def listar_mis_guias(db: DatabaseSession, usuario: UsuarioActual) -> list[EstadoGuiaLeer]:
    return ServicioGuias(db).listar(usuario)


@router.get("/{guia}", response_model=EstadoGuiaLeer)
def obtener_mi_guia(
    guia: CodigoGuia, db: DatabaseSession, usuario: UsuarioActual
) -> EstadoGuiaLeer:
    return ServicioGuias(db).obtener(usuario, guia)


@router.put("/{guia}", response_model=EstadoGuiaLeer)
def registrar_estado_de_mi_guia(
    guia: CodigoGuia,
    datos: EstadoGuiaActualizar,
    db: DatabaseSession,
    usuario: UsuarioActual,
) -> EstadoGuiaLeer:
    return ServicioGuias(db).registrar(usuario, guia, datos.estado, datos.version)
