from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.firma_convenio import FirmaConvenio
    from backend.models.usuario import Usuario


class InvitacionFirmaConvenio(Base):
    __tablename__ = "invitacion_firma_convenio"
    __table_args__ = (
        Index("uq_invitacion_firma_token_hash", "token_hash", unique=True),
        Index(
            "uq_invitacion_firma_activa",
            "firma_convenio_id",
            unique=True,
            postgresql_where=text("utilizado_en IS NULL AND revocado_en IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    firma_convenio_id: Mapped[int] = mapped_column(
        ForeignKey("firma_convenio.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enviado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    utilizado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revocado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    generada_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    firma_convenio: Mapped[FirmaConvenio] = relationship(
        back_populates="invitaciones"
    )
    generada_por: Mapped[Usuario] = relationship(foreign_keys=[generada_por_id])
