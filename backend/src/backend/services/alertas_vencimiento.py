from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio

ZONA_HORARIA_DOMINIO = ZoneInfo("America/Bogota")
DIAS_MAXIMOS_ALERTA = 120


class RangoVencimiento(StrEnum):
    DIAS_0_30 = "0_30"
    DIAS_31_60 = "31_60"
    DIAS_61_90 = "61_90"
    DIAS_91_120 = "91_120"


@dataclass(frozen=True, slots=True)
class ProximoVencimiento:
    convenio_id: int
    codigo: str | None
    objeto: str | None
    fecha_vencimiento: date
    dias_restantes: int
    rango_vencimiento: RangoVencimiento


def _fecha_actual_dominio() -> date:
    return datetime.now(ZONA_HORARIA_DOMINIO).date()


def _clasificar(dias_restantes: int) -> RangoVencimiento:
    if dias_restantes <= 30:
        return RangoVencimiento.DIAS_0_30
    if dias_restantes <= 60:
        return RangoVencimiento.DIAS_31_60
    if dias_restantes <= 90:
        return RangoVencimiento.DIAS_61_90
    return RangoVencimiento.DIAS_91_120


class ServicioAlertasVencimiento:
    def __init__(self, db: Session):
        self.db = db

    def listar_proximos_vencimientos(
        self, fecha_referencia: date | None = None
    ) -> list[ProximoVencimiento]:
        referencia = fecha_referencia or _fecha_actual_dominio()
        fecha_limite = referencia + timedelta(days=DIAS_MAXIMOS_ALERTA)

        consulta = (
            select(
                Convenio.id,
                Convenio.codigo,
                Convenio.objeto,
                Convenio.fecha_vencimiento,
            )
            .where(
                Convenio.estado.in_(
                    (
                        EstadoConvenio.VIGENTE.value,
                        EstadoConvenio.POR_VENCER.value,
                    )
                ),
                Convenio.fecha_vencimiento.is_not(None),
                Convenio.fecha_vencimiento >= referencia,
                Convenio.fecha_vencimiento <= fecha_limite,
            )
            .order_by(Convenio.fecha_vencimiento, Convenio.id)
        )

        # La consulta no debe propagar escrituras pendientes de otros flujos.
        with self.db.no_autoflush:
            filas = self.db.execute(consulta).all()

        return [
            ProximoVencimiento(
                convenio_id=fila.id,
                codigo=fila.codigo,
                objeto=fila.objeto,
                fecha_vencimiento=fila.fecha_vencimiento,
                dias_restantes=(fila.fecha_vencimiento - referencia).days,
                rango_vencimiento=_clasificar(
                    (fila.fecha_vencimiento - referencia).days
                ),
            )
            for fila in filas
        ]
