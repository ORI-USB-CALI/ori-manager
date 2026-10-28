from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.usuario import Usuario


class BorradorConvenio(Base):
    """Contenido de trabajo del convenio durante la Elaboración.

    Guardar avance sobrescribe este registro sin crear versiones: la versión
    formal se genera al enviar el convenio a revisión. Un convenio sin borrador
    trabaja sobre el contenido de su versión actual.
    """

    __tablename__ = "borrador_convenio"
    __table_args__ = (
        UniqueConstraint("convenio_id", name="uq_borrador_convenio_convenio"),
        CheckConstraint("revision > 0", name="ck_borrador_convenio_revision_positiva"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="RESTRICT"), nullable=False
    )
    contenido: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Sube con cada guardado que cambia el borrador. Es independiente de
    # convenio.version_actual y detecta guardados concurrentes (409).
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    actualizado_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    convenio: Mapped[Convenio] = relationship(back_populates="borrador")
    actualizado_por: Mapped[Usuario] = relationship(foreign_keys=[actualizado_por_id])
