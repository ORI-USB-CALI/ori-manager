import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.security import require_permission
from backend.db.session import get_db
from backend.models.aliado import Aliado, Convenio, EstadoConvenio
from backend.schemas.convenio import ConvenioCreate, ConvenioEstadoUpdate, ConvenioRead

router = APIRouter(prefix="/convenios", tags=["Convenios"])

DatabaseSession = Annotated[Session, Depends(get_db)]

PERMISO_CONVENIOS_GESTIONAR = "convenios:gestionar"

# Un convenio finalizado o cancelado es un estado terminal: no existe ninguna
# regla de negocio aprobada que permita reabrirlo. La matriz completa de
# transiciones válidas (EN_TRAMITE -> VIGENTE -> VENCIDO, etc.) depende de
# reglas que todavía no están definidas para este esquema (ej. RN-14 requiere
# entidades de etapa/observación que no existen en esta rama), así que
# deliberadamente solo se bloquea lo que sí es una regla segura y general.
ESTADOS_TERMINALES = {EstadoConvenio.FINALIZADO, EstadoConvenio.CANCELADO}


@router.post(
    "",
    response_model=ConvenioRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un convenio nuevo",
    description="Crea un convenio asociado a un aliado existente. El convenio siempre nace en estado EN_TRAMITE.",
)
def crear_convenio(
    datos: ConvenioCreate,
    db: DatabaseSession,
    _: Annotated[object, Depends(require_permission(PERMISO_CONVENIOS_GESTIONAR))],
) -> ConvenioRead:
    aliado = db.get(Aliado, datos.aliado_id)
    if not aliado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aliado no encontrado",
        )

    convenio = Convenio(
        id=uuid.uuid4(),
        aliado_id=datos.aliado_id,
        codigo=datos.codigo,
        titulo=datos.titulo,
        tipo_convenio=datos.tipo_convenio,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin,
        estado=EstadoConvenio.EN_TRAMITE,
    )
    db.add(convenio)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un convenio registrado con ese código",
        ) from exc

    db.refresh(convenio)
    return ConvenioRead.model_validate(convenio)


@router.patch(
    "/{convenio_id}/estado",
    response_model=ConvenioRead,
    summary="Cambiar el estado de un convenio",
    description="Actualiza el estado de un convenio existente. Un convenio FINALIZADO o CANCELADO no puede cambiar de estado.",
)
def cambiar_estado_convenio(
    convenio_id: uuid.UUID,
    datos: ConvenioEstadoUpdate,
    db: DatabaseSession,
    _: Annotated[object, Depends(require_permission(PERMISO_CONVENIOS_GESTIONAR))],
) -> ConvenioRead:
    convenio = db.get(Convenio, convenio_id)
    if not convenio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Convenio no encontrado",
        )

    if convenio.estado in ESTADOS_TERMINALES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El convenio está en estado {convenio.estado.value} y no "
                "admite cambios de estado adicionales"
            ),
        )

    convenio.estado = datos.estado
    db.commit()
    db.refresh(convenio)
    return ConvenioRead.model_validate(convenio)
