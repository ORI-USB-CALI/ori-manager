from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import EstadoRevisionPendiente, ResultadoRevisionPendiente

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.historial_etapa import HistorialEtapa
    from backend.models.usuario import Usuario

_ESTADOS = ", ".join(f"'{valor.value}'" for valor in EstadoRevisionPendiente)
_RESULTADOS = ", ".join(f"'{valor.value}'" for valor in ResultadoRevisionPendiente)


class RevisionPendiente(Base):
    __tablename__ = "revision_pendiente"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_ESTADOS})", name="ck_revision_pendiente_estado"),
        CheckConstraint(f"resultado IS NULL OR resultado IN ({_RESULTADOS})", name="ck_revision_pendiente_resultado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="CASCADE"), nullable=False, index=True
    )
    historial_etapa_id: Mapped[int] = mapped_column(
        ForeignKey("historial_etapa.id", ondelete="CASCADE"), nullable=False
    )
    responsable_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        default=EstadoRevisionPendiente.PENDIENTE.value,
        server_default=EstadoRevisionPendiente.PENDIENTE.value,
        nullable=False,
    )
    resultado: Mapped[str | None] = mapped_column(String(20), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    convenio: Mapped[Convenio] = relationship(back_populates="revisiones_pendientes")
    historial_etapa: Mapped[HistorialEtapa] = relationship()
    responsable: Mapped[Usuario] = relationship(foreign_keys=[responsable_id])
