from fastapi import APIRouter, status

from backend.api.deps import DatabaseSession, RolActual
from backend.api.schemas.aliado import AliadoCrear, AliadoEditar, AliadoLeer
from backend.models.aliado import Aliado
from backend.services import aliado as aliado_service

router = APIRouter(prefix="/aliados", tags=["Aliados"])


@router.post("", response_model=AliadoLeer, status_code=status.HTTP_201_CREATED)
def crear_aliado(datos: AliadoCrear, db: DatabaseSession, rol: RolActual) -> Aliado:
    aliado = aliado_service.crear_aliado(
        db, aliado_service.DatosAliado(**datos.model_dump()), rol
    )
    db.commit()
    return aliado


@router.get("/{aliado_id}", response_model=AliadoLeer)
def consultar_aliado(aliado_id: int, db: DatabaseSession, rol: RolActual) -> Aliado:
    return aliado_service.consultar_aliado(db, aliado_id, rol)


@router.patch("/{aliado_id}", response_model=AliadoLeer)
def editar_aliado(
    aliado_id: int, datos: AliadoEditar, db: DatabaseSession, rol: RolActual
) -> Aliado:
    aliado = aliado_service.editar_aliado(
        db,
        aliado_id,
        aliado_service.DatosEdicionAliado(**datos.model_dump(exclude_unset=True)),
        rol,
    )
    db.commit()
    return aliado


@router.post("/{aliado_id}/inactivar", response_model=AliadoLeer)
def inactivar_aliado(aliado_id: int, db: DatabaseSession, rol: RolActual) -> Aliado:
    aliado = aliado_service.inactivar_aliado(db, aliado_id, rol)
    db.commit()
    return aliado


@router.post("/{aliado_id}/reactivar", response_model=AliadoLeer)
def reactivar_aliado(aliado_id: int, db: DatabaseSession, rol: RolActual) -> Aliado:
    aliado = aliado_service.reactivar_aliado(db, aliado_id, rol)
    db.commit()
    return aliado
