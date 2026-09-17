import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.core.security import UserTokenData, require_permission
from backend.db.session import get_db
from backend.models.aliado import Aliado
from backend.schemas.aliado import AliadoDetalleRead

router = APIRouter(prefix="/aliados", tags=["Aliados"])

DatabaseSession = Annotated[Session, Depends(get_db)]

PERMISO_CONVENIOS_READ = "convenios:read"


@router.get(
    "/{aliado_id}",
    response_model=AliadoDetalleRead,
    summary="Consultar detalle de un aliado y sus convenios",
    description="Obtiene la información registrada de un aliado específico y la lista de sus convenios asociados independientemente de su estado.",
)
def obtener_detalle_aliado(
    aliado_id: uuid.UUID,
    db: DatabaseSession,
    current_user: Annotated[UserTokenData, Depends(require_permission("aliados:read"))],
) -> AliadoDetalleRead:
    """
    Endpoint para consultar el perfil del aliado y sus convenios (CA-01 a CA-08).

    Requiere el permiso 'aliados:read' para consultar el aliado. La lista de
    convenios asociados solo se incluye si, además, el usuario cuenta con el
    permiso 'convenios:read'; en caso contrario se devuelve el aliado con la
    lista de convenios vacía en lugar de denegar toda la consulta.
    """
    query = (
        select(Aliado)
        .options(selectinload(Aliado.convenios))
        .where(Aliado.id == aliado_id)
    )
    aliado = db.execute(query).scalar_one_or_none()

    if not aliado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aliado no encontrado",
        )

    detalle = AliadoDetalleRead.model_validate(aliado)
    if PERMISO_CONVENIOS_READ not in current_user.permissions:
        detalle.convenios = []

    return detalle
