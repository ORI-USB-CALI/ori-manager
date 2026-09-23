from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.etapa import Etapa
    from backend.models.usuario import Usuario


class HistorialEtapa(Base):
    __tablename__ = "historial_etapa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    etapa_origen_id: Mapped[int | None] = mapped_column(
        ForeignKey("etapa.id", ondelete="RESTRICT"), nullable=True
    )
    etapa_destino_id: Mapped[int] = mapped_column(
        ForeignKey("etapa.id", ondelete="RESTRICT"), nullable=False
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    responsable_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_cambio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    convenio: Mapped[Convenio] = relationship(back_populates="historial_etapas")
    etapa_origen: Mapped[Etapa | None] = relationship(
        foreign_keys=[etapa_origen_id]
    )
    etapa_destino: Mapped[Etapa] = relationship(foreign_keys=[etapa_destino_id])
    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id])
    responsable: Mapped[Usuario | None] = relationship(
        foreign_keys=[responsable_id]
    )
