from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.revision_convenio import RevisionConvenio
    from backend.models.usuario import Usuario


class InvitacionRevisionContraparte(Base):
    __tablename__ = "invitacion_revision_contraparte"
    __table_args__ = (
        Index(
            "uq_invitacion_contraparte_token_hash",
            "token_hash",
            unique=True,
        ),
        Index(
            "uq_invitacion_contraparte_activa",
            "revision_convenio_id",
            unique=True,
            postgresql_where=text(
                "utilizado_en IS NULL AND revocado_en IS NULL"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    revision_convenio_id: Mapped[int] = mapped_column(
        ForeignKey("revision_convenio.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generada_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    correo_destino: Mapped[str] = mapped_column(String(320), nullable=False)
    correo_cc: Mapped[str | None] = mapped_column(String(320), nullable=True)
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
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    revision_convenio: Mapped[RevisionConvenio] = relationship(
        back_populates="invitaciones_contraparte"
    )
    generada_por: Mapped[Usuario] = relationship()
