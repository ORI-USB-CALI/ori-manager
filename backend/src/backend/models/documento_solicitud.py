from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.solicitud_convenio import SolicitudConvenio


class DocumentoSolicitud(Base):
    __tablename__ = "documento_solicitud"
    __table_args__ = (
        CheckConstraint("tamano_bytes > 0", name="ck_documento_solicitud_tamano"),
        CheckConstraint(
            "tipo_documento IN ('CAMARA_COMERCIO', 'RUT', "
            "'CEDULA_REPRESENTANTE_LEGAL', 'OTRO_DOCUMENTO_REPRESENTACION', "
            "'OTRO_SOPORTE')",
            name="ck_documento_solicitud_tipo",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(
        ForeignKey("solicitud_convenio.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo_documento: Mapped[str] = mapped_column(String(40), nullable=False)
    nombre_original: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_mime: Mapped[str] = mapped_column(String(100), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    clave_objeto: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    solicitud: Mapped[SolicitudConvenio] = relationship(back_populates="documentos")
