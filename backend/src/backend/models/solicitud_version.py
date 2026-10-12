from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.documento import Documento
    from backend.models.solicitud_convenio import SolicitudConvenio
    from backend.models.usuario import Usuario

# RESTRICT sobre documento: un documento que pertenece a una versión radicada
# no puede borrarse físicamente; al retirarlo se marca como no vigente.
solicitud_version_documento = Table(
    "solicitud_version_documento",
    Base.metadata,
    Column(
        "solicitud_version_id",
        ForeignKey("solicitud_version.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "documento_id",
        ForeignKey("documento.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    ),
)


class SolicitudVersion(Base):
    __tablename__ = "solicitud_version"
    __table_args__ = (
        UniqueConstraint("solicitud_id", "numero", name="uq_solicitud_version_numero"),
        CheckConstraint("numero > 0", name="ck_solicitud_version_numero"),
        CheckConstraint(
            "(devuelta_en IS NULL AND devuelta_por_id IS NULL"
            " AND observaciones_devolucion IS NULL)"
            " OR (devuelta_en IS NOT NULL AND devuelta_por_id IS NOT NULL"
            " AND observaciones_devolucion IS NOT NULL)",
            name="ck_solicitud_version_devolucion_completa",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(
        ForeignKey("solicitud_convenio.id", ondelete="RESTRICT"), nullable=False
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    # Formulario completo tal como quedó al radicar; no cambia con correcciones posteriores.
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    radicada_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    radicada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # CA-05: si esta radicación fue devuelta, aquí queda la devolución. La versión
    # corregida es la siguiente (numero + 1).
    observaciones_devolucion: Mapped[str | None] = mapped_column(Text, nullable=True)
    devuelta_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    devuelta_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    solicitud: Mapped[SolicitudConvenio] = relationship(back_populates="versiones")
    radicada_por: Mapped[Usuario] = relationship(foreign_keys=[radicada_por_id])
    devuelta_por: Mapped[Usuario | None] = relationship(foreign_keys=[devuelta_por_id])
    documentos: Mapped[list[Documento]] = relationship(
        secondary=solicitud_version_documento, order_by="Documento.id"
    )
