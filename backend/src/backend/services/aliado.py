from collections.abc import Sequence
from dataclasses import asdict, dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.enums import EstadoAliado, EstadoConvenio, RolUsuario, TipoAliado
from backend.services.exceptions import (
    AliadoConConveniosVigentesError,
    AliadoDuplicadoError,
    AliadoNoEncontradoError,
    SectorEconomicoRequeridoError,
)
from backend.services.permisos import validar_rol

ROLES_GESTION = {RolUsuario.ADMINISTRADOR_ORI, RolUsuario.GESTOR_ORI}
ROLES_CONSULTA = ROLES_GESTION | {RolUsuario.REVISOR_ORI}

# RN-23: un convenio bloquea la inactivación del aliado mientras esté
# vigente o próximo a vencer (ver nota 3 del MER aprobado).
ESTADOS_CONVENIO_BLOQUEAN_INACTIVACION = {
    EstadoConvenio.VIGENTE,
    EstadoConvenio.POR_VENCER,
}


@dataclass
class DatosAliado:
    identificacion: str
    nombre: str
    tipo: TipoAliado
    sector_economico: str | None = None
    pais_id: int | None = None
    ciudad: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    correo: str | None = None
    sitio_web: str | None = None


@dataclass
class FiltrosAliado:
    """Criterios de búsqueda del listado de aliados."""

    buscar: str | None = None
    tipo: TipoAliado | None = None
    estado: EstadoAliado | None = None
    limite: int = 20
    desplazamiento: int = 0


@dataclass
class DatosEdicionAliado:
    nombre: str | None = None
    tipo: TipoAliado | None = None
    sector_economico: str | None = None
    pais_id: int | None = None
    ciudad: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    correo: str | None = None
    sitio_web: str | None = None


def _validar_sector_economico(tipo: TipoAliado, sector_economico: str | None) -> None:
    if tipo == TipoAliado.EMPRESA and not sector_economico:
        raise SectorEconomicoRequeridoError(
            "El sector económico es obligatorio cuando el tipo de aliado es empresa"
        )


def buscar_por_identificacion(db: Session, identificacion: str) -> Aliado | None:
    return db.scalar(select(Aliado).where(Aliado.identificacion == identificacion))


def listar_aliados(
    db: Session, filtros: FiltrosAliado, rol: RolUsuario
) -> tuple[Sequence[Aliado], int]:
    """Lista aliados filtrados y el total que cumple el filtro (sin paginar).

    Buscar antes de crear es lo que evita los registros duplicados, así que la
    búsqueda cubre identificación y nombre.
    """
    validar_rol(rol, ROLES_CONSULTA)

    condiciones = []
    if filtros.buscar:
        patron = f"%{filtros.buscar.strip()}%"
        condiciones.append(
            or_(Aliado.identificacion.ilike(patron), Aliado.nombre.ilike(patron))
        )
    if filtros.tipo is not None:
        condiciones.append(Aliado.tipo == filtros.tipo)
    if filtros.estado is not None:
        condiciones.append(Aliado.estado == filtros.estado)

    total = db.scalar(select(func.count()).select_from(Aliado).where(*condiciones)) or 0
    aliados = db.scalars(
        select(Aliado)
        .where(*condiciones)
        .order_by(Aliado.nombre)
        .limit(filtros.limite)
        .offset(filtros.desplazamiento)
    ).all()
    return aliados, total


def crear_aliado(db: Session, datos: DatosAliado, rol: RolUsuario) -> Aliado:
    validar_rol(rol, ROLES_GESTION)
    _validar_sector_economico(datos.tipo, datos.sector_economico)

    if buscar_por_identificacion(db, datos.identificacion) is not None:
        raise AliadoDuplicadoError(
            f"Ya existe un aliado con identificación '{datos.identificacion}'"
        )

    aliado = Aliado(**asdict(datos))
    db.add(aliado)
    db.flush()
    return aliado


def consultar_aliado(db: Session, aliado_id: int, rol: RolUsuario) -> Aliado:
    validar_rol(rol, ROLES_CONSULTA)

    aliado = db.get(Aliado, aliado_id)
    if aliado is None:
        raise AliadoNoEncontradoError(f"No existe el aliado con id {aliado_id}")
    return aliado


def editar_aliado(
    db: Session, aliado_id: int, datos: DatosEdicionAliado, rol: RolUsuario
) -> Aliado:
    validar_rol(rol, ROLES_GESTION)
    aliado = consultar_aliado(db, aliado_id, rol)

    cambios = {campo: valor for campo, valor in asdict(datos).items() if valor is not None}
    tipo_resultante = TipoAliado(cambios.get("tipo", aliado.tipo))
    sector_resultante = cambios.get("sector_economico", aliado.sector_economico)
    _validar_sector_economico(tipo_resultante, sector_resultante)

    for campo, valor in cambios.items():
        setattr(aliado, campo, valor)

    db.flush()
    return aliado


def listar_convenios_de_aliado(
    db: Session, aliado_id: int, rol: RolUsuario
) -> Sequence[Convenio]:
    """Convenios asociados al aliado, en cualquier estado."""
    consultar_aliado(db, aliado_id, rol)

    return db.scalars(
        select(Convenio).where(Convenio.aliado_id == aliado_id).order_by(Convenio.id)
    ).all()


def _tiene_convenios_vigentes(db: Session, aliado_id: int) -> bool:
    total = db.scalar(
        select(func.count())
        .select_from(Convenio)
        .where(
            Convenio.aliado_id == aliado_id,
            Convenio.estado.in_(ESTADOS_CONVENIO_BLOQUEAN_INACTIVACION),
        )
    )
    return bool(total)


def inactivar_aliado(db: Session, aliado_id: int, rol: RolUsuario) -> Aliado:
    validar_rol(rol, ROLES_GESTION)
    aliado = consultar_aliado(db, aliado_id, rol)

    if _tiene_convenios_vigentes(db, aliado_id):
        raise AliadoConConveniosVigentesError(
            "No se puede inactivar un aliado con convenios vigentes"
        )

    aliado.estado = EstadoAliado.INACTIVO
    db.flush()
    return aliado


def reactivar_aliado(db: Session, aliado_id: int, rol: RolUsuario) -> Aliado:
    validar_rol(rol, ROLES_GESTION)
    aliado = consultar_aliado(db, aliado_id, rol)

    aliado.estado = EstadoAliado.ACTIVO
    db.flush()
    return aliado


def resolver_aliado_para_convenio(
    db: Session, convenio: Convenio, datos_contraparte: DatosAliado
) -> Aliado | None:
    """Resuelve el aliado asociado a un convenio cuando este pasa a VIGENTE.

    `datos_contraparte` representa la información de la institución
    contraparte disponible en la solicitud (hoy no persistida, porque
    `solicitud_convenio` aún no existe como tabla).
    """
    if convenio.estado != EstadoConvenio.VIGENTE:
        return None

    if convenio.aliado_id is not None:
        return db.get(Aliado, convenio.aliado_id)

    aliado = buscar_por_identificacion(db, datos_contraparte.identificacion)
    if aliado is None:
        _validar_sector_economico(datos_contraparte.tipo, datos_contraparte.sector_economico)
        aliado = Aliado(**asdict(datos_contraparte))
        db.add(aliado)
        db.flush()
    elif datos_contraparte.correo and datos_contraparte.correo != aliado.correo:
        aliado.correo = datos_contraparte.correo
        db.flush()

    convenio.aliado_id = aliado.id
    db.flush()
    return aliado
