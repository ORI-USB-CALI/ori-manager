from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.unidades_organizacionales import TipoUnidad
from backend.db.base import Base

_TIPOS_UNIDAD_SQL = ", ".join(f"'{tipo.value}'" for tipo in TipoUnidad)


class UnidadOrganizacional(Base):
    """Unidad de la estructura organizacional definida por el MER."""

    __tablename__ = "unidad_organizacional"
    __table_args__ = (
        CheckConstraint(
            f"tipo IN ({_TIPOS_UNIDAD_SQL})",
            name="ck_unidad_organizacional_tipo",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    tipo: Mapped[str] = mapped_column(String(21), nullable=False)
    unidad_padre_id: Mapped[int | None] = mapped_column(
        ForeignKey("unidad_organizacional.id"),
        nullable=True,
    )
    activa: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    unidad_padre: Mapped[UnidadOrganizacional | None] = relationship(
        back_populates="subunidades",
        remote_side="UnidadOrganizacional.id",
    )
    subunidades: Mapped[list[UnidadOrganizacional]] = relationship(
        back_populates="unidad_padre",
    )
