from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.core.roles import CodigoRol
from backend.models.auditoria import Auditoria
from backend.models.enums import AccionAuditoria

Orden = Literal["asc", "desc"]


@dataclass(frozen=True)
class FiltrosBitacora:
    entidad: str | None = None
    registro_id: int | None = None
    usuario_id: int | None = None
    rol: CodigoRol | None = None
    accion: AccionAuditoria | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
    orden: Orden = "asc"
    limite: int = 50
    desplazamiento: int = 0


def listar_auditoria(
    db: Session, filtros: FiltrosBitacora
) -> tuple[Sequence[Auditoria], int]:
    condiciones = []
    if filtros.entidad is not None:
        condiciones.append(Auditoria.entidad == filtros.entidad)
    if filtros.registro_id is not None:
        condiciones.append(Auditoria.registro_id == filtros.registro_id)
    if filtros.usuario_id is not None:
        condiciones.append(Auditoria.usuario_id == filtros.usuario_id)
    if filtros.rol is not None:
        condiciones.append(Auditoria.rol == filtros.rol.value)
    if filtros.accion is not None:
        condiciones.append(Auditoria.accion == filtros.accion.value)
    if filtros.desde is not None:
        condiciones.append(Auditoria.fecha_hora >= filtros.desde)
    if filtros.hasta is not None:
        condiciones.append(Auditoria.fecha_hora <= filtros.hasta)

    total = db.scalar(
        select(func.count()).select_from(Auditoria).where(*condiciones)
    ) or 0
    # El id desempata registros de una misma transacción, que comparten
    # fecha_hora porque now() se fija al inicio de la transacción.
    criterio = (
        (Auditoria.fecha_hora.desc(), Auditoria.id.desc())
        if filtros.orden == "desc"
        else (Auditoria.fecha_hora.asc(), Auditoria.id.asc())
    )
    items = db.scalars(
        select(Auditoria)
        .options(joinedload(Auditoria.usuario), joinedload(Auditoria.responsable))
        .where(*condiciones)
        .order_by(*criterio)
        .limit(filtros.limite)
        .offset(filtros.desplazamiento)
    ).all()
    return items, total
