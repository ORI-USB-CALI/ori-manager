from fastapi import APIRouter, status

from backend.api.deps import DatabaseSession, RolActual
from backend.schemas.convenio import ConvenioCreate, ConvenioRead
from backend.services.convenio import crear_convenio, obtener_convenio

router = APIRouter(prefix="/convenios", tags=["Convenios"])


@router.post("", response_model=ConvenioRead, status_code=status.HTTP_201_CREATED)
def registrar_convenio(datos: ConvenioCreate, db: DatabaseSession, rol: RolActual) -> ConvenioRead:
    """CA-01: crea el registro base de un convenio."""
    convenio = crear_convenio(db, datos, rol)
    return ConvenioRead.model_validate(convenio)


@router.get("/{convenio_id}", response_model=ConvenioRead)
def consultar_convenio(convenio_id: int, db: DatabaseSession, rol: RolActual) -> ConvenioRead:
    """CA-06: consulta el registro base de un convenio."""
    convenio = obtener_convenio(db, convenio_id, rol)
    return ConvenioRead.model_validate(convenio)
