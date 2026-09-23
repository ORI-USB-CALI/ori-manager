from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import EstadoObservacion, OrigenObservacion

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.historial_etapa import HistorialEtapa
    from backend.models.usuario import Usuario

_ORIGENES = ", ".join(f"'{valor.value}'" for valor in OrigenObservacion)
_ESTADOS = ", ".join(f"'{valor.value}'" for valor in EstadoObservacion)


class ObservacionRevision(Base):
    __tablename__ = "observacion_revision"
    __table_args__ = (
        CheckConstraint(f"origen IN ({_ORIGENES})", name="ck_observacion_revision_origen"),
        CheckConstraint(f"estado IN ({_ESTADOS})", name="ck_observacion_revision_estado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="CASCADE"), nullable=False, index=True
    )
    historial_etapa_id: Mapped[int] = mapped_column(
        ForeignKey("historial_etapa.id", ondelete="CASCADE"), nullable=False
    )
    origen: Mapped[str] = mapped_column(String(20), nullable=False)
    registrada_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    responsable_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    respuesta: Mapped[str | None] = mapped_column(Text, nullable=True)
    atendida_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    fecha_atencion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(20),
        default=EstadoObservacion.PENDIENTE.value,
        server_default=EstadoObservacion.PENDIENTE.value,
        nullable=False,
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    convenio: Mapped[Convenio] = relationship(back_populates="observaciones_revision")
    historial_etapa: Mapped[HistorialEtapa] = relationship(back_populates="observaciones")
    registrada_por: Mapped[Usuario] = relationship(foreign_keys=[registrada_por_id])
    responsable: Mapped[Usuario | None] = relationship(foreign_keys=[responsable_id])
    atendida_por: Mapped[Usuario | None] = relationship(foreign_keys=[atendida_por_id])
