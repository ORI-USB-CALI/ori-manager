from fastapi import APIRouter

from backend.api.deps import DatabaseSession, RolActual
from backend.api.schemas.pais import PaisLeer
from backend.models.pais import Pais
from backend.services import pais as pais_service

router = APIRouter(prefix="/paises", tags=["Países"])


@router.get("", response_model=list[PaisLeer])
def listar_paises(db: DatabaseSession, rol: RolActual) -> list[Pais]:
    """Catálogo para el selector de país. Basta con un rol válido."""
    return list(pais_service.listar_paises(db))
