from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import (
    EstadoRevisionConvenio,
    ResultadoRevisionConvenio,
    TipoRevisionConvenio,
)

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.documento import Documento
    from backend.models.historial_etapa import HistorialEtapa
    from backend.models.observacion_revision import ObservacionRevision
    from backend.models.usuario import Usuario

_TIPOS = ", ".join(f"'{valor.value}'" for valor in TipoRevisionConvenio)
_ESTADOS = ", ".join(f"'{valor.value}'" for valor in EstadoRevisionConvenio)
_RESULTADOS = ", ".join(f"'{valor.value}'" for valor in ResultadoRevisionConvenio)


class RevisionConvenio(Base):
    __tablename__ = "revision_convenio"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_TIPOS})", name="ck_revision_convenio_tipo"),
        CheckConstraint(
            f"estado IN ({_ESTADOS})", name="ck_revision_convenio_estado"
        ),
        CheckConstraint(
            f"resultado IS NULL OR resultado IN ({_RESULTADOS})",
            name="ck_revision_convenio_resultado",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    historial_etapa_id: Mapped[int | None] = mapped_column(
        ForeignKey("historial_etapa.id", ondelete="RESTRICT"), nullable=True
    )
    documento_id: Mapped[int | None] = mapped_column(
        ForeignKey("documento.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    responsable_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        default=EstadoRevisionConvenio.PENDIENTE.value,
        server_default=EstadoRevisionConvenio.PENDIENTE.value,
        nullable=False,
    )
    resultado: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resuelta_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    # Estado exacto de los datos del convenio presentados en esta ronda. Se escribe
    # una sola vez, al crear la revisión, y no vuelve a modificarse: si hay
    # correcciones, la siguiente ronda es otra RevisionConvenio con otro snapshot.
    # Nullable a nivel de columna por compatibilidad con revisiones de otro origen.
    snapshot_datos: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resuelta_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    convenio: Mapped[Convenio] = relationship(back_populates="revisiones")
    historial_etapa: Mapped[HistorialEtapa | None] = relationship()
    documento: Mapped[Documento | None] = relationship(back_populates="revisiones")
    responsable: Mapped[Usuario | None] = relationship(
        foreign_keys=[responsable_id]
    )
    resuelta_por: Mapped[Usuario | None] = relationship(
        foreign_keys=[resuelta_por_id]
    )
    observaciones: Mapped[list[ObservacionRevision]] = relationship(
        back_populates="revision_convenio"
    )
