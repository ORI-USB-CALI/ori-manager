from fastapi import APIRouter, status

from backend.api.deps import DatabaseSession, RolActual
from backend.api.schemas.contacto_aliado import (
    ContactoCrear,
    ContactoEditar,
    ContactoLeer,
)
from backend.models.contacto_aliado import ContactoAliado
from backend.services import contacto_aliado as contacto_service

router = APIRouter(prefix="/aliados/{aliado_id}/contactos", tags=["Contactos de aliado"])


@router.get("", response_model=list[ContactoLeer])
def listar_contactos(
    aliado_id: int, db: DatabaseSession, rol: RolActual
) -> list[ContactoAliado]:
    return list(contacto_service.listar_contactos(db, aliado_id, rol))


@router.post("", response_model=ContactoLeer, status_code=status.HTTP_201_CREATED)
def crear_contacto(
    aliado_id: int, datos: ContactoCrear, db: DatabaseSession, rol: RolActual
) -> ContactoAliado:
    contacto = contacto_service.crear_contacto(
        db, aliado_id, contacto_service.DatosContacto(**datos.model_dump()), rol
    )
    db.commit()
    return contacto


@router.get("/{contacto_id}", response_model=ContactoLeer)
def consultar_contacto(
    aliado_id: int, contacto_id: int, db: DatabaseSession, rol: RolActual
) -> ContactoAliado:
    return contacto_service.consultar_contacto(db, aliado_id, contacto_id, rol)


@router.patch("/{contacto_id}", response_model=ContactoLeer)
def editar_contacto(
    aliado_id: int,
    contacto_id: int,
    datos: ContactoEditar,
    db: DatabaseSession,
    rol: RolActual,
) -> ContactoAliado:
    contacto = contacto_service.editar_contacto(
        db,
        aliado_id,
        contacto_id,
        contacto_service.DatosEdicionContacto(**datos.model_dump(exclude_unset=True)),
        rol,
    )
    db.commit()
    return contacto
