from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.convenio import ESTADO_CONVENIO_INICIAL, Convenio
from backend.models.enums import RolUsuario
from backend.schemas.convenio import ConvenioCreate
from backend.services.exceptions import (
    AliadoInvalidoError,
    ConvenioDuplicadoError,
    ConvenioNoEncontradoError,
    PermisoDenegadoError,
    SolicitudInvalidaError,
    UnidadOrganizacionalRequeridaError,
)

# Rol.permiteGestionarConvenios() del diagrama de clases: quien puede
# crear/editar convenios. Misma convencion que backend.services.aliado
# en feature/HU-04-aliados.
ROLES_GESTION = {RolUsuario.ADMINISTRADOR_ORI, RolUsuario.GESTOR_ORI}
ROLES_CONSULTA = ROLES_GESTION | {RolUsuario.REVISOR_ORI}


def _validar_rol(rol: RolUsuario, roles_permitidos: set[RolUsuario]) -> None:
    """CA-08: el rol debe estar habilitado para la operacion."""
    if rol not in roles_permitidos:
        raise PermisoDenegadoError(
            f"El rol '{rol.value}' no tiene permiso para esta operación"
        )


def _existe_fila(db: Session, tabla: str, id_valor: int) -> bool:
    """Verifica la existencia de una fila por id en una tabla que aun no
    tiene modelo de SQLAlchemy propio en esta rama (aliado y
    solicitud_convenio pertenecen a otras HU que todavia no se han
    fusionado). Se usa SQL crudo a proposito para no acoplarnos a esos
    modelos antes de tiempo.

    TODO(integracion): cuando feature/HU-04-aliados (Aliado) y la HU de
    solicitudes esten fusionadas a esta rama, reemplazar por
    `db.get(Modelo, id_valor) is not None`.
    """
    fila = db.execute(
        text(f"SELECT 1 FROM {tabla} WHERE id = :id_valor"),
        {"id_valor": id_valor},
    ).first()
    return fila is not None


def _validar_solicitud_existe(db: Session, solicitud_id: int) -> None:
    if not _existe_fila(db, "solicitud_convenio", solicitud_id):
        raise SolicitudInvalidaError(
            f"No existe una solicitud con id {solicitud_id}"
        )


def _validar_aliado_existe(db: Session, aliado_id: int | None) -> None:
    """CA-07: si se indica un aliado, debe existir. Si no se indica
    (None), es valido: CA-03 permite registrar el convenio sin aliado.
    """
    if aliado_id is None:
        return
    if not _existe_fila(db, "aliado", aliado_id):
        raise AliadoInvalidoError(
            f"El aliado seleccionado (id {aliado_id}) no existe"
        )


def _validar_solicitud_sin_convenio(db: Session, solicitud_id: int) -> None:
    """RN-07 / MER: una solicitud origina a lo sumo un convenio (1:1).

    Se valida antes del INSERT para dar un error claro (CA-05); la
    restriccion UNIQUE en la base de datos sigue siendo la garantia
    final ante condiciones de carrera (ver `crear_convenio`).
    """
    ya_existe = db.execute(
        text("SELECT 1 FROM convenio WHERE solicitud_id = :solicitud_id"),
        {"solicitud_id": solicitud_id},
    ).first()
    if ya_existe is not None:
        raise ConvenioDuplicadoError(
            f"La solicitud {solicitud_id} ya tiene un convenio registrado"
        )


def _validar_alcance_y_unidad(alcance: str | None, unidad_organizacional_id: int | None) -> None:
    """MER, reglas de aplicacion #2: unidad_organizacional_id es
    obligatorio cuando alcance = PROGRAMA.
    """
    if alcance == "PROGRAMA" and unidad_organizacional_id is None:
        raise UnidadOrganizacionalRequeridaError(
            "unidad_organizacional_id es obligatorio cuando el alcance es PROGRAMA"
        )


def crear_convenio(db: Session, datos: ConvenioCreate, rol: RolUsuario) -> Convenio:
    """CA-01/CA-02/CA-03/CA-04/CA-05/CA-07/CA-08: crea el registro base
    de un convenio, validando relaciones, identificadores y permisos.
    """
    _validar_rol(rol, ROLES_GESTION)

    _validar_solicitud_existe(db, datos.solicitud_id)
    _validar_aliado_existe(db, datos.aliado_id)
    _validar_solicitud_sin_convenio(db, datos.solicitud_id)
    _validar_alcance_y_unidad(datos.alcance, datos.unidad_organizacional_id)

    convenio = Convenio(
        solicitud_id=datos.solicitud_id,
        aliado_id=datos.aliado_id,
        creado_por_id=datos.creado_por_id,
        estado=ESTADO_CONVENIO_INICIAL,
        codigo=datos.codigo,
        tipo_convenio_id=datos.tipo_convenio_id,
        etapa_actual_id=datos.etapa_actual_id,
        objeto=datos.objeto,
        alcance=datos.alcance,
        unidad_organizacional_id=datos.unidad_organizacional_id,
        implicacion_financiera=datos.implicacion_financiera,
        fecha_inicio=datos.fecha_inicio,
        fecha_vencimiento=datos.fecha_vencimiento,
        fecha_firma=datos.fecha_firma,
        duracion_meses=datos.duracion_meses,
        porcentaje_avance=datos.porcentaje_avance,
        convenio_origen_id=datos.convenio_origen_id,
        numero_renovacion=datos.numero_renovacion,
    )
    db.add(convenio)

    try:
        db.commit()
    except IntegrityError as exc:
        # CA-05: red de seguridad ante condiciones de carrera (dos
        # solicitudes concurrentes para el mismo solicitud_id). El
        # chequeo previo cubre el caso normal; esto cubre el resto.
        db.rollback()
        raise ConvenioDuplicadoError(
            f"La solicitud {datos.solicitud_id} ya tiene un convenio registrado"
        ) from exc

    db.refresh(convenio)
    return convenio


def obtener_convenio(db: Session, convenio_id: int, rol: RolUsuario) -> Convenio:
    """CA-06/CA-08: consulta el registro base de un convenio por id."""
    _validar_rol(rol, ROLES_CONSULTA)

    convenio = db.get(Convenio, convenio_id)
    if convenio is None:
        raise ConvenioNoEncontradoError(f"No existe un convenio con id {convenio_id}")
    return convenio
