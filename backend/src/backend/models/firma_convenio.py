from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import EstadoFirma, ModalidadFirma, ParteFirmante, RolFirmante

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.usuario import Usuario

_ROLES = ", ".join(f"'{v.value}'" for v in RolFirmante)
_PARTES = ", ".join(f"'{v.value}'" for v in ParteFirmante)
_MODALIDADES = ", ".join(f"'{v.value}'" for v in ModalidadFirma)
_ESTADOS = ", ".join(f"'{v.value}'" for v in EstadoFirma)


class FirmaConvenio(Base):
    __tablename__ = "firma_convenio"
    __table_args__ = (
        UniqueConstraint("convenio_id", "orden", name="uq_firma_convenio_orden"),
        CheckConstraint(f"rol_firmante IN ({_ROLES})", name="ck_firma_convenio_rol_firmante"),
        CheckConstraint(f"parte IN ({_PARTES})", name="ck_firma_convenio_parte"),
        CheckConstraint(f"modalidad IS NULL OR modalidad IN ({_MODALIDADES})", name="ck_firma_convenio_modalidad"),
        CheckConstraint(f"estado IN ({_ESTADOS})", name="ck_firma_convenio_estado"),
        CheckConstraint("orden BETWEEN 1 AND 7", name="ck_firma_convenio_orden_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    convenio_id: Mapped[int] = mapped_column(ForeignKey("convenio.id", ondelete="CASCADE"), nullable=False)
    orden: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rol_firmante: Mapped[str] = mapped_column(String(40), nullable=False)
    parte: Mapped[str] = mapped_column(String(20), nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True)
    nombre_firmante: Mapped[str | None] = mapped_column(String(160), nullable=True)
    cargo_firmante: Mapped[str | None] = mapped_column(String(120), nullable=True)
    modalidad: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(20),
        default=EstadoFirma.PENDIENTE.value,
        server_default=EstadoFirma.PENDIENTE.value,
        nullable=False,
    )
    fecha_firma: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    documento_id: Mapped[int | None] = mapped_column(ForeignKey("documento.id"), nullable=True)
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    convenio: Mapped[Convenio] = relationship(back_populates="firmas")
    usuario: Mapped[Usuario | None] = relationship()
