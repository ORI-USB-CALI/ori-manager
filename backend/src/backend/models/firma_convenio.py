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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import (
    EstadoFirmaConvenio,
    ModalidadFirma,
    ParteFirmaConvenio,
    RolFirmanteConvenio,
)

if TYPE_CHECKING:
    from backend.models.documento import Documento
    from backend.models.invitacion_firma_convenio import InvitacionFirmaConvenio
    from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
    from backend.models.usuario import Usuario

_ROLES = ", ".join(f"'{valor.value}'" for valor in RolFirmanteConvenio)
_PARTES = ", ".join(f"'{valor.value}'" for valor in ParteFirmaConvenio)
_MODALIDADES = ", ".join(f"'{valor.value}'" for valor in ModalidadFirma)
_ESTADOS = ", ".join(f"'{valor.value}'" for valor in EstadoFirmaConvenio)


class FirmaConvenio(Base):
    __tablename__ = "firma_convenio"
    __table_args__ = (
        UniqueConstraint(
            "proceso_firmas_id", "orden", name="uq_firma_convenio_proceso_orden"
        ),
        UniqueConstraint(
            "proceso_firmas_id",
            "rol_firmante",
            name="uq_firma_convenio_proceso_rol",
        ),
        CheckConstraint("orden BETWEEN 1 AND 7", name="ck_firma_convenio_orden"),
        CheckConstraint(
            f"rol_firmante IN ({_ROLES})", name="ck_firma_convenio_rol"
        ),
        CheckConstraint(f"parte IN ({_PARTES})", name="ck_firma_convenio_parte"),
        CheckConstraint(
            f"modalidad IS NULL OR modalidad IN ({_MODALIDADES})",
            name="ck_firma_convenio_modalidad",
        ),
        CheckConstraint(f"estado IN ({_ESTADOS})", name="ck_firma_convenio_estado"),
        CheckConstraint(
            "modalidad <> 'ELECTRONICA' OR correo_firmante IS NOT NULL",
            name="ck_firma_convenio_electronica_correo",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proceso_firmas_id: Mapped[int] = mapped_column(
        ForeignKey("proceso_firmas_convenio.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    orden: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rol_firmante: Mapped[str] = mapped_column(String(40), nullable=False)
    parte: Mapped[str] = mapped_column(String(40), nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    nombre_firmante: Mapped[str | None] = mapped_column(String(160), nullable=True)
    cargo_firmante: Mapped[str | None] = mapped_column(String(160), nullable=True)
    correo_firmante: Mapped[str | None] = mapped_column(String(320), nullable=True)
    modalidad: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(20),
        default=EstadoFirmaConvenio.PENDIENTE.value,
        server_default=EstadoFirmaConvenio.PENDIENTE.value,
        nullable=False,
    )
    fecha_firma: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    documento_id: Mapped[int | None] = mapped_column(
        ForeignKey("documento.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    proceso_firmas: Mapped[ProcesoFirmasConvenio] = relationship(
        back_populates="firmas"
    )
    usuario: Mapped[Usuario | None] = relationship(foreign_keys=[usuario_id])
    documento: Mapped[Documento | None] = relationship(back_populates="firmas")
    invitaciones: Mapped[list[InvitacionFirmaConvenio]] = relationship(
        back_populates="firma_convenio", cascade="all, delete-orphan"
    )
