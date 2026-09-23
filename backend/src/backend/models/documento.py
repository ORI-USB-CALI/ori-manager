from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.solicitud_convenio import SolicitudConvenio
    from backend.models.usuario import Usuario

_TIPOS_HU11 = (
    "CAMARA_COMERCIO",
    "RUT",
    "CEDULA_REPRESENTANTE_LEGAL",
    "OTRO_DOCUMENTO_REPRESENTACION",
    "OTRO_SOPORTE",
)
_TIPOS_MER = (
    "FORMATO_SOLICITUD",
    "CAMARA_COMERCIO",
    "RUT",
    "CEDULA_REPRESENTANTE",
    "BORRADOR",
    "AVAL_JURIDICO",
    "CONVENIO_FIRMADO",
    "OTROSI",
    "ACTA_TERMINACION",
    "SOPORTE",
)
_TIPOS_COMPATIBLES = tuple(dict.fromkeys((*_TIPOS_HU11, *_TIPOS_MER)))
_TIPOS_SQL = ", ".join(f"'{tipo}'" for tipo in _TIPOS_COMPATIBLES)


class Documento(Base):
    __tablename__ = "documento"
    __table_args__ = (
        CheckConstraint("tamano_bytes > 0", name="ck_documento_tamano"),
        CheckConstraint(
            f"tipo IN ({_TIPOS_SQL})",
            name="ck_documento_tipo",
        ),
        CheckConstraint(
            "solicitud_id IS NOT NULL OR convenio_id IS NOT NULL",
            name="ck_documento_solicitud_o_convenio",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solicitud_id: Mapped[int | None] = mapped_column(
        ForeignKey("solicitud_convenio.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    convenio_id: Mapped[int | None] = mapped_column(
        ForeignKey("convenio.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    ruta_almacenamiento: Mapped[str] = mapped_column(
        String(500), unique=True, nullable=False
    )
    tipo_mime: Mapped[str] = mapped_column(String(120), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    es_vigente: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    cargado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    solicitud: Mapped[SolicitudConvenio | None] = relationship(
        back_populates="documentos"
    )
    convenio: Mapped[Convenio | None] = relationship(back_populates="documentos")
    cargado_por: Mapped[Usuario | None] = relationship(foreign_keys=[cargado_por_id])
