from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import UsuarioActual
from backend.db.session import get_db
from backend.models.pais import Pais
from backend.schemas.pais import PaisLeer

router = APIRouter(prefix="/paises", tags=["Países"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[PaisLeer])
def listar_paises(db: DatabaseSession, usuario: UsuarioActual) -> list[Pais]:
    """HT-14. Catálogo ISO 3166-1 para cualquier formulario que pida un país."""
    return list(db.scalars(select(Pais).order_by(Pais.nombre)))
