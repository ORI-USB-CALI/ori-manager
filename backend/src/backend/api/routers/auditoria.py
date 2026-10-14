from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import requiere
from backend.core.permisos import Permiso
from backend.core.roles import CodigoRol
from backend.db.session import get_db
from backend.models.enums import AccionAuditoria
from backend.models.usuario import Usuario
from backend.schemas.auditoria import AuditoriaListado, RegistroAuditoriaLeer
from backend.services.auditoria import FiltrosBitacora, Orden, listar_auditoria

# Solo expone consulta: la bitácora se escribe automáticamente y no se edita ni borra.
router = APIRouter(prefix="/auditoria", tags=["Auditoría"])
DatabaseSession = Annotated[Session, Depends(get_db)]
PuedeVerAuditoria = Annotated[Usuario, requiere(Permiso.AUDITORIA_VER)]


@router.get("", response_model=AuditoriaListado)
def listar_bitacora(
    db: DatabaseSession,
    _: PuedeVerAuditoria,
    entidad: Annotated[str | None, Query(max_length=80)] = None,
    registro_id: int | None = None,
    usuario_id: int | None = None,
    rol: CodigoRol | None = None,
    accion: AccionAuditoria | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    orden: Orden = "asc",
    limite: Annotated[int, Query(ge=1, le=100)] = 50,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
) -> AuditoriaListado:
    if desde is not None and hasta is not None and desde > hasta:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "La fecha inicial no puede ser posterior a la fecha final",
        )
    items, total = listar_auditoria(
        db,
        FiltrosBitacora(
            entidad=entidad,
            registro_id=registro_id,
            usuario_id=usuario_id,
            rol=rol,
            accion=accion,
            desde=desde,
            hasta=hasta,
            orden=orden,
            limite=limite,
            desplazamiento=desplazamiento,
        ),
    )
    return AuditoriaListado(
        items=[RegistroAuditoriaLeer.model_validate(item) for item in items],
        total=total,
    )
