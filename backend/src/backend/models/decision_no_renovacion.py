from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.usuario import Usuario


class DecisionNoRenovacion(Base):
    __tablename__ = "decision_no_renovacion"
    __table_args__ = (
        UniqueConstraint(
            "convenio_id",
            "fecha_vencimiento_origen",
            name="uq_decision_no_renovacion_convenio_periodo",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="RESTRICT"), nullable=False
    )
    fecha_vencimiento_origen: Mapped[date] = mapped_column(Date, nullable=False)
    decidida_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    decidida_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    convenio: Mapped[Convenio] = relationship(
        back_populates="decisiones_no_renovacion"
    )
    decidida_por: Mapped[Usuario] = relationship(foreign_keys=[decidida_por_id])
