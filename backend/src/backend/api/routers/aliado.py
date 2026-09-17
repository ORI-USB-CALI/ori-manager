from typing import Annotated

from fastapi import APIRouter, Query, status

from backend.api.deps import DatabaseSession, RolActual
from backend.api.schemas.aliado import (
    AliadoCrear,
    AliadoEditar,
    AliadoLeer,
    AliadoListado,
)
from backend.api.schemas.convenio import ConvenioDeAliadoLeer
from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.enums import EstadoAliado, TipoAliado
from backend.services import aliado as aliado_service

router = APIRouter(prefix="/aliados", tags=["Aliados"])


@router.get("", response_model=AliadoListado)
def listar_aliados(
    db: DatabaseSession,
    rol: RolActual,
    buscar: Annotated[str | None, Query(max_length=200)] = None,
    tipo: TipoAliado | None = None,
    estado: EstadoAliado | None = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
) -> AliadoListado:
    items, total = aliado_service.listar_aliados(
        db,
        aliado_service.FiltrosAliado(
            buscar=buscar,
            tipo=tipo,
            estado=estado,
            limite=limite,
            desplazamiento=desplazamiento,
        ),
        rol,
    )
    return AliadoListado(
        items=[AliadoLeer.model_validate(aliado) for aliado in items],
        total=total,
    )


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


@router.get("/{aliado_id}/convenios", response_model=list[ConvenioDeAliadoLeer])
def listar_convenios_de_aliado(
    aliado_id: int, db: DatabaseSession, rol: RolActual
) -> list[Convenio]:
    return list(aliado_service.listar_convenios_de_aliado(db, aliado_id, rol))


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
