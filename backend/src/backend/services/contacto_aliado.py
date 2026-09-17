from collections.abc import Sequence
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.contacto_aliado import ContactoAliado
from backend.models.enums import RolUsuario
from backend.services.aliado import ROLES_CONSULTA, ROLES_GESTION, consultar_aliado
from backend.services.exceptions import ContactoNoEncontradoError
from backend.services.permisos import validar_rol

# Los contactos pertenecen al aliado, no al convenio: se reutilizan en cada
# trámite de la misma entidad.


@dataclass
class DatosContacto:
    nombre: str
    cargo: str | None = None
    correo: str | None = None
    telefono: str | None = None
    extension: str | None = None
    es_principal: bool = False


@dataclass
class DatosEdicionContacto:
    nombre: str | None = None
    cargo: str | None = None
    correo: str | None = None
    telefono: str | None = None
    extension: str | None = None
    es_principal: bool | None = None
    activo: bool | None = None


def listar_contactos(db: Session, aliado_id: int, rol: RolUsuario) -> Sequence[ContactoAliado]:
    consultar_aliado(db, aliado_id, rol)

    return db.scalars(
        select(ContactoAliado)
        .where(ContactoAliado.aliado_id == aliado_id)
        .order_by(ContactoAliado.es_principal.desc(), ContactoAliado.nombre)
    ).all()


def consultar_contacto(
    db: Session, aliado_id: int, contacto_id: int, rol: RolUsuario
) -> ContactoAliado:
    validar_rol(rol, ROLES_CONSULTA)

    contacto = db.get(ContactoAliado, contacto_id)
    if contacto is None or contacto.aliado_id != aliado_id:
        raise ContactoNoEncontradoError(
            f"No existe el contacto {contacto_id} para el aliado {aliado_id}"
        )
    return contacto


def crear_contacto(
    db: Session, aliado_id: int, datos: DatosContacto, rol: RolUsuario
) -> ContactoAliado:
    validar_rol(rol, ROLES_GESTION)
    consultar_aliado(db, aliado_id, rol)

    contacto = ContactoAliado(aliado_id=aliado_id, **asdict(datos))
    db.add(contacto)
    db.flush()
    return contacto


def editar_contacto(
    db: Session,
    aliado_id: int,
    contacto_id: int,
    datos: DatosEdicionContacto,
    rol: RolUsuario,
) -> ContactoAliado:
    validar_rol(rol, ROLES_GESTION)
    contacto = consultar_contacto(db, aliado_id, contacto_id, rol)

    cambios = {campo: valor for campo, valor in asdict(datos).items() if valor is not None}
    for campo, valor in cambios.items():
        setattr(contacto, campo, valor)

    db.flush()
    return contacto
