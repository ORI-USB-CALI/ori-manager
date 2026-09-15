from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import requiere_gestor_convenio
from backend.db.session import get_db
from backend.schemas.convenio import ConvenioCreate, ConvenioRead
from backend.services.convenio import crear_convenio, obtener_convenio

router = APIRouter(prefix="/convenios", tags=["Convenios"])

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=ConvenioRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requiere_gestor_convenio)],
)
def registrar_convenio(datos: ConvenioCreate, db: DatabaseSession) -> ConvenioRead:
    """CA-01: crea el registro base de un convenio."""
    convenio = crear_convenio(db, datos)
    return ConvenioRead.model_validate(convenio)


@router.get("/{convenio_id}", response_model=ConvenioRead)
def consultar_convenio(convenio_id: int, db: DatabaseSession) -> ConvenioRead:
    """CA-06: consulta el registro base de un convenio."""
    convenio = obtener_convenio(db, convenio_id)
    if convenio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Convenio no encontrado",
        )
    return ConvenioRead.model_validate(convenio)
