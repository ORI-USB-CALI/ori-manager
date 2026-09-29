from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.revision_convenio import RevisionConvenio


class RespuestaRevisionContraparte(Base):
    __tablename__ = "respuesta_revision_contraparte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    revision_convenio_id: Mapped[int] = mapped_column(
        ForeignKey("revision_convenio.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    nombre_firmante: Mapped[str] = mapped_column(String(160), nullable=False)
    cargo_firmante: Mapped[str] = mapped_column(String(160), nullable=False)
    correo_actor: Mapped[str] = mapped_column(String(320), nullable=False)
    firma_png: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    firma_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    revision_convenio: Mapped[RevisionConvenio] = relationship(
        back_populates="respuesta_contraparte"
    )
