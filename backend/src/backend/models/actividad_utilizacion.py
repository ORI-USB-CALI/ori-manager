from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.usuario import Usuario


class ActividadUtilizacion(Base):
    """Actividad ya ocurrida que evidencia el uso de un convenio (HU-35)."""

    __tablename__ = "actividad_utilizacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    actividad: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    responsable: Mapped[str] = mapped_column(String(200), nullable=False)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    registrado_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    convenio: Mapped[Convenio] = relationship(
        back_populates="actividades_utilizacion"
    )
    registrado_por: Mapped[Usuario] = relationship(
        foreign_keys=[registrado_por_id]
    )
