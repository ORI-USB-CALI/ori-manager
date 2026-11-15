"""HU-09: directorio público de convenios vigentes. No exige sesión (CA-01, CA-07)."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.db.session import get_db
from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.services.convenios import filtro_convenio_formalizado
from backend.services.vigencia import fecha_actual_dominio

router = APIRouter(prefix="/public/directorio-convenios", tags=["Directorio público"])
DatabaseSession = Annotated[Session, Depends(get_db)]


class ConvenioPublico(BaseModel):
    """Lista blanca de lo que se puede publicar (CA-03, CA-06). Agregar un campo
    aquí lo hace público: nada interno, jurídico ni personal."""

    codigo: str
    aliado: str
    tipo_convenio: str | None
    objeto: str | None
    fecha_inicio: date
    fecha_vencimiento: date
    estado: Literal["VIGENTE"] = "VIGENTE"


class DirectorioPublico(BaseModel):
    items: list[ConvenioPublico]
    total: int


def filtro_vigente_publico(hoy: date):
    """Formalizado, en estado vigente y con hoy dentro del periodo, ambos extremos
    inclusivos (HT-10). La fecha se revisa aunque el estado diga VIGENTE, para
    no publicar un convenio vencido que la conciliación aún no ha marcado (CA-04)."""
    return (
        filtro_convenio_formalizado(),
        Convenio.estado == EstadoConvenio.VIGENTE.value,
        Convenio.fecha_vencimiento >= hoy,
        Convenio.fecha_inicio <= hoy,
        # NULL queda excluido por SQL. No asignar códigos ni inferir el aliado
        # desde nombres propuestos de solicitudes al consultar públicamente.
        func.trim(Convenio.codigo) != "",
        Convenio.aliado.has(func.trim(Aliado.nombre) != ""),
    )


@router.get("", response_model=DirectorioPublico)
def listar(
    db: DatabaseSession,
    limite: Annotated[int, Query(ge=1, le=50)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
) -> DirectorioPublico:
    condiciones = filtro_vigente_publico(fecha_actual_dominio())
    total = (
        db.scalar(select(func.count()).select_from(Convenio).where(*condiciones)) or 0
    )
    convenios = db.scalars(
        select(Convenio)
        .where(*condiciones)
        .options(joinedload(Convenio.aliado), joinedload(Convenio.tipo_convenio))
        .order_by(Convenio.fecha_vencimiento, Convenio.id)
        .limit(limite)
        .offset(desplazamiento)
    ).all()
    return DirectorioPublico(
        total=total,
        items=[
            ConvenioPublico(
                codigo=c.codigo,
                aliado=c.aliado.nombre,
                tipo_convenio=c.tipo_convenio.nombre if c.tipo_convenio else None,
                objeto=c.objeto,
                fecha_inicio=c.fecha_inicio,
                fecha_vencimiento=c.fecha_vencimiento,
            )
            for c in convenios
        ],
    )
