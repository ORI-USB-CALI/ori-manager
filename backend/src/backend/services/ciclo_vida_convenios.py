"""Conciliación explícita y transaccional; las consultas HTTP no la invocan."""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.models.transicion_estado_convenio import TransicionEstadoConvenio
from backend.services.renovaciones import DIAS_VENTANA_RENOVACION, fecha_actual_dominio

logger = logging.getLogger(__name__)
ESTADOS_CONCILIABLES = (
    EstadoConvenio.VIGENTE.value,
    EstadoConvenio.POR_VENCER.value,
    EstadoConvenio.VENCIDO.value,
)


@dataclass(frozen=True)
class CambioEstado:
    convenio_id: int
    anterior: str
    nuevo: str


@dataclass(frozen=True)
class ResultadoConciliacion:
    fecha_referencia: date
    cambios: tuple[CambioEstado, ...]
    sin_fecha: tuple[int, ...]
    legado_inconsistente: tuple[int, ...]
    simulado: bool


def conciliar_estados(
    db: Session, fecha_referencia: date | None = None, *, simular: bool = False
) -> ResultadoConciliacion:
    """Posee la transacción: confirmar todo, o revertir todo ante cualquier error.

    Bloquea y recarga filas para serializar conciliaciones y cambios humanos.
    VENCIDO se migra únicamente con fecha pasada; no se elimina del contrato.
    No depende de decisiones negativas ni del estado de una renovación hija.
    """
    referencia = fecha_referencia or fecha_actual_dominio()
    limite = referencia + timedelta(days=DIAS_VENTANA_RENOVACION)
    cambios: list[CambioEstado] = []
    sin_fecha: list[int] = []
    legado_inconsistente: list[int] = []
    try:
        convenios = db.scalars(
            select(Convenio)
            .where(Convenio.estado.in_(ESTADOS_CONCILIABLES))
            .order_by(Convenio.id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()
        for convenio in convenios:
            vencimiento = convenio.fecha_vencimiento
            if vencimiento is None:
                sin_fecha.append(convenio.id)
                continue
            if (
                convenio.estado == EstadoConvenio.VENCIDO.value
                and vencimiento >= referencia
            ):
                legado_inconsistente.append(convenio.id)
                continue
            if vencimiento < referencia:
                nuevo = EstadoConvenio.FINALIZADO.value
            elif vencimiento <= limite:
                nuevo = EstadoConvenio.POR_VENCER.value
            else:
                nuevo = EstadoConvenio.VIGENTE.value
            if convenio.estado == nuevo:
                continue
            cambios.append(CambioEstado(convenio.id, convenio.estado, nuevo))
            if not simular:
                db.add(
                    TransicionEstadoConvenio(
                        convenio_id=convenio.id,
                        estado_anterior=convenio.estado,
                        estado_nuevo=nuevo,
                        fecha_referencia=referencia,
                        fecha_vencimiento=vencimiento,
                    )
                )
                convenio.estado = nuevo
        if simular:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise

    # Solo anunciar transiciones después de confirmar la transacción.
    for cambio in cambios:
        logger.info(
            "transicion actor=SISTEMA convenio_id=%s anterior=%s nuevo=%s referencia=%s simulado=%s",
            cambio.convenio_id,
            cambio.anterior,
            cambio.nuevo,
            referencia,
            simular,
        )
    for convenio_id in sin_fecha:
        logger.warning(
            "anomalia=SIN_FECHA_VENCIMIENTO convenio_id=%s referencia=%s",
            convenio_id,
            referencia,
        )
    for convenio_id in legado_inconsistente:
        logger.warning(
            "anomalia=VENCIDO_SIN_FECHA_PASADA convenio_id=%s referencia=%s",
            convenio_id,
            referencia,
        )
    return ResultadoConciliacion(
        referencia,
        tuple(cambios),
        tuple(sin_fecha),
        tuple(legado_inconsistente),
        simular,
    )
