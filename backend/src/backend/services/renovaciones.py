"""Reglas, consultas y decisiones del seguimiento de renovación."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from secrets import token_hex
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.decision_no_renovacion import DecisionNoRenovacion
from backend.models.enums import (
    AccionAuditoria,
    EstadoConvenio,
    EstadoSeguimientoRenovacion,
    EstadoSolicitud,
)
from backend.models.etapa import Etapa
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.schemas.convenio import ConvenioCrear
from backend.services.convenios import (
    ConvenioDuplicado,
    ConvenioNoEditable,
    ConvenioNoEncontrado,
    ServicioConvenios,
)

ZONA_HORARIA_DOMINIO = ZoneInfo("America/Bogota")
DIAS_VENTANA_RENOVACION = 120
ESTADOS_ELEGIBLES_RENOVACION = frozenset(
    (EstadoConvenio.VIGENTE.value, EstadoConvenio.POR_VENCER.value)
)
ESTADOS_ORIGEN_RENOVACION = frozenset(
    (
        EstadoConvenio.VIGENTE.value,
        EstadoConvenio.POR_VENCER.value,
        EstadoConvenio.VENCIDO.value,
        EstadoConvenio.FINALIZADO.value,
    )
)

# Solo antecedentes reutilizables; excluye decisiones, observaciones, fechas de
# aprobación/radicación, adjuntos e historial del proceso anterior.
CAMPOS_SOLICITUD_RENOVACION = (
    "tipo_solicitante", "solicitante_id", "unidad_organizacional_id",
    "nombre_aliado_propuesto", "tipo_identificacion_aliado_propuesto",
    "identificacion_aliado_propuesto", "tipo_aliado_propuesto",
    "correo_aliado_propuesto", "pais_aliado_propuesto", "ciudad_aliado_propuesto",
    "telefono_aliado_propuesto", "direccion_aliado_propuesto",
    "sector_economico_aliado_propuesto", "justificacion", "actividades_por_parte",
    "metas_esperadas", "vigencia_estimada", "requisitos_renovacion",
    "contacto_contraparte_nombre", "contacto_contraparte_cargo",
    "contacto_contraparte_telefono", "contacto_contraparte_correo",
    "supervisor_usb_nombre", "supervisor_usb_cargo", "supervisor_usb_telefono",
    "supervisor_usb_correo", "supervisor_contraparte_nombre",
    "supervisor_contraparte_cargo", "supervisor_contraparte_telefono",
    "supervisor_contraparte_correo", "solicitante_nombre", "solicitante_correo",
    "solicitante_documento", "solicitante_cargo", "solicitante_entidad",
    "solicitante_unidad", "solicitante_programa",
)


@dataclass(frozen=True, slots=True)
class SeguimientoRenovacion:
    convenio_id: int
    codigo: str | None
    objeto: str | None
    aliado: str | None
    fecha_inicio: date | None
    fecha_vencimiento: date | None
    estado_convenio: EstadoConvenio
    estado_seguimiento: EstadoSeguimientoRenovacion
    tipo_convenio: str | None
    convenio_renovacion_id: int | None
    codigo_renovacion: str | None
    numero_renovacion: int | None
    etapa_renovacion: str | None


def fecha_actual_dominio() -> date:
    return datetime.now(ZONA_HORARIA_DOMINIO).date()


def es_elegible_para_renovacion(
    convenio: Convenio, fecha_referencia: date | None = None
) -> bool:
    referencia = fecha_referencia or fecha_actual_dominio()
    vencimiento = convenio.fecha_vencimiento
    if convenio.estado not in ESTADOS_ELEGIBLES_RENOVACION or vencimiento is None:
        return False
    return referencia <= vencimiento <= referencia + timedelta(
        days=DIAS_VENTANA_RENOVACION
    )


def _resolver_estado_seguimiento(
    *,
    elegible: bool,
    tiene_renovacion_activa: bool,
    tiene_decision_no_renovacion: bool,
) -> EstadoSeguimientoRenovacion | None:
    if tiene_renovacion_activa:
        return EstadoSeguimientoRenovacion.RENOVACION_INICIADA
    if tiene_decision_no_renovacion:
        return EstadoSeguimientoRenovacion.NO_SE_RENOVARA
    if elegible:
        return EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION
    return None


def existe_renovacion_activa(db: Session, convenio_id: int) -> bool:
    consulta = (
        select(Convenio.id)
        .where(
            Convenio.convenio_origen_id == convenio_id,
            Convenio.estado == EstadoConvenio.EN_TRAMITE.value,
        )
        .limit(1)
    )
    with db.no_autoflush:
        return db.scalar(consulta) is not None


def puede_iniciar_renovacion(db: Session, convenio: Convenio) -> bool:
    if (
        convenio.estado not in ESTADOS_ORIGEN_RENOVACION
        or convenio.fecha_vencimiento is None
    ):
        return False
    return not existe_renovacion_activa(db, convenio.id)


def existe_decision_no_renovacion_vigente(
    db: Session, convenio: Convenio
) -> bool:
    if convenio.fecha_vencimiento is None:
        return False
    consulta = (
        select(DecisionNoRenovacion.id)
        .where(
            DecisionNoRenovacion.convenio_id == convenio.id,
            DecisionNoRenovacion.fecha_vencimiento_origen
            == convenio.fecha_vencimiento,
        )
        .limit(1)
    )
    with db.no_autoflush:
        return db.scalar(consulta) is not None


def calcular_estado_seguimiento(
    db: Session,
    convenio: Convenio,
    fecha_referencia: date | None = None,
) -> EstadoSeguimientoRenovacion | None:
    return _resolver_estado_seguimiento(
        elegible=es_elegible_para_renovacion(convenio, fecha_referencia),
        tiene_renovacion_activa=existe_renovacion_activa(db, convenio.id),
        tiene_decision_no_renovacion=existe_decision_no_renovacion_vigente(
            db, convenio
        ),
    )


def listar_seguimiento_renovaciones(
    db: Session,
    estado: EstadoSeguimientoRenovacion | None = None,
    fecha_referencia: date | None = None,
) -> list[SeguimientoRenovacion]:
    referencia = fecha_referencia or fecha_actual_dominio()
    limite = referencia + timedelta(days=DIAS_VENTANA_RENOVACION)
    renovacion = aliased(Convenio, name="renovacion_activa")

    condicion_elegible = and_(
        Convenio.estado.in_(ESTADOS_ELEGIBLES_RENOVACION),
        Convenio.fecha_vencimiento.is_not(None),
        Convenio.fecha_vencimiento >= referencia,
        Convenio.fecha_vencimiento <= limite,
    )
    consulta = (
        select(
            Convenio,
            Aliado.nombre.label("aliado"),
            TipoConvenio.nombre.label("tipo_convenio"),
            renovacion.id.label("convenio_renovacion_id"),
            renovacion.codigo.label("codigo_renovacion"),
            renovacion.numero_renovacion.label("numero_renovacion"),
            Etapa.nombre.label("etapa_renovacion"),
            DecisionNoRenovacion.id.label("decision_no_renovacion_id"),
        )
        .outerjoin(Aliado, Aliado.id == Convenio.aliado_id)
        .outerjoin(TipoConvenio, TipoConvenio.id == Convenio.tipo_convenio_id)
        .outerjoin(
            renovacion,
            and_(
                renovacion.convenio_origen_id == Convenio.id,
                renovacion.estado == EstadoConvenio.EN_TRAMITE.value,
            ),
        )
        .outerjoin(Etapa, Etapa.id == renovacion.etapa_actual_id)
        .outerjoin(
            DecisionNoRenovacion,
            and_(
                DecisionNoRenovacion.convenio_id == Convenio.id,
                DecisionNoRenovacion.fecha_vencimiento_origen
                == Convenio.fecha_vencimiento,
            ),
        )
        .where(
            or_(
                renovacion.id.is_not(None),
                DecisionNoRenovacion.id.is_not(None),
                condicion_elegible,
            )
        )
        .order_by(Convenio.fecha_vencimiento.asc().nulls_last(), Convenio.id)
    )

    with db.no_autoflush:
        filas = db.execute(consulta).all()

    resultado: list[SeguimientoRenovacion] = []
    for fila in filas:
        convenio = fila.Convenio
        estado_calculado = _resolver_estado_seguimiento(
            elegible=es_elegible_para_renovacion(convenio, referencia),
            tiene_renovacion_activa=fila.convenio_renovacion_id is not None,
            tiene_decision_no_renovacion=(
                fila.decision_no_renovacion_id is not None
            ),
        )
        if estado_calculado is None or (estado is not None and estado != estado_calculado):
            continue
        resultado.append(
            SeguimientoRenovacion(
                convenio_id=convenio.id,
                codigo=convenio.codigo,
                objeto=convenio.objeto,
                aliado=fila.aliado,
                fecha_inicio=convenio.fecha_inicio,
                fecha_vencimiento=convenio.fecha_vencimiento,
                estado_convenio=EstadoConvenio(convenio.estado),
                estado_seguimiento=estado_calculado,
                tipo_convenio=fila.tipo_convenio,
                convenio_renovacion_id=fila.convenio_renovacion_id,
                codigo_renovacion=fila.codigo_renovacion,
                numero_renovacion=fila.numero_renovacion,
                etapa_renovacion=fila.etapa_renovacion,
            )
        )
    return resultado


class ServicioRenovaciones:
    def __init__(self, db: Session):
        self.db = db

    def _bloquear_origen(self, convenio_id: int) -> Convenio:
        origen = self.db.scalar(
            select(Convenio)
            .where(Convenio.id == convenio_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if origen is None:
            raise ConvenioNoEncontrado("Convenio origen no encontrado")
        return origen

    def iniciar_renovacion(self, convenio_id: int, usuario: Usuario) -> Convenio:
        try:
            origen = self._bloquear_origen(convenio_id)
            if not puede_iniciar_renovacion(self.db, origen):
                raise ConvenioNoEditable(
                    "El convenio no puede originar una renovación o ya tiene un intento activo"
                )
            servicio = ServicioConvenios(self.db)
            version = servicio._version_actual(origen)
            if version is None:
                raise ConvenioNoEditable("El convenio origen no tiene una versión vigente")
            anterior = origen.solicitud
            solicitud = SolicitudConvenio(
                **{campo: getattr(anterior, campo) for campo in CAMPOS_SOLICITUD_RENOVACION},
                consecutivo=f"TEMP-{token_hex(12)}",
                estado=EstadoSolicitud.APROBADA.value,
                aliado_id=origen.aliado_id,
                tipo_convenio_id=origen.tipo_convenio_id,
                objeto=origen.objeto,
                implicacion_financiera=origen.implicacion_financiera,
                decidida_por_id=usuario.id,
                fecha_decision=datetime.now(UTC),
            )
            self.db.add(solicitud)
            self.db.flush()
            solicitud.consecutivo = f"SOL-{solicitud.id:08d}"
            datos = ConvenioCrear(
                solicitud_id=solicitud.id,
                tipo_convenio_id=origen.tipo_convenio_id,
                objeto=origen.objeto or anterior.objeto or "",
                alcance=origen.alcance,
                unidad_organizacional_id=origen.unidad_organizacional_id,
                implicacion_financiera=origen.implicacion_financiera,
                duracion_meses=origen.duracion_meses,
                convenio_origen_id=origen.id,
                numero_renovacion=(origen.numero_renovacion or 0) + 1,
            )
            hijo = servicio._crear_en_transaccion(
                datos, usuario, solicitud, version_base=version
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConvenioDuplicado("Ya existe una renovación activa para este convenio") from exc
        except Exception:
            self.db.rollback()
            raise
        return hijo

    def registrar_no_renovacion(
        self, convenio_id: int, usuario: Usuario
    ) -> DecisionNoRenovacion:
        try:
            origen = self._bloquear_origen(convenio_id)
            if calcular_estado_seguimiento(self.db, origen) != (
                EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION
            ):
                raise ConvenioNoEditable("El convenio no está pendiente de decisión de renovación")
            decision = DecisionNoRenovacion(
                convenio_id=origen.id,
                fecha_vencimiento_origen=origen.fecha_vencimiento,
                decidida_por_id=usuario.id,
            )
            self.db.add(decision)
            self.db.flush()
            self.db.add(
                Auditoria(
                    usuario_id=usuario.id,
                    entidad="decision_no_renovacion",
                    registro_id=decision.id,
                    accion=AccionAuditoria.INSERT.value,
                )
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConvenioDuplicado("Ya existe una decisión para este convenio y periodo") from exc
        except Exception:
            self.db.rollback()
            raise
        return decision
