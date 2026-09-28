from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import EstadoProcesoFirmasConvenio

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.firma_convenio import FirmaConvenio
    from backend.models.revision_convenio import RevisionConvenio
    from backend.models.usuario import Usuario
    from backend.models.version_convenio import VersionConvenio

_ESTADOS = ", ".join(f"'{valor.value}'" for valor in EstadoProcesoFirmasConvenio)


class ProcesoFirmasConvenio(Base):
    __tablename__ = "proceso_firmas_convenio"
    __table_args__ = (
        CheckConstraint(
            f"estado IN ({_ESTADOS})", name="ck_proceso_firmas_convenio_estado"
        ),
        Index(
            "uq_proceso_firmas_convenio_activo",
            "convenio_id",
            unique=True,
            postgresql_where=text("estado IN ('CONFIGURACION', 'EN_CURSO')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version_convenio_id: Mapped[int] = mapped_column(
        ForeignKey("version_convenio.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    revision_final_id: Mapped[int] = mapped_column(
        ForeignKey("revision_convenio.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    creado_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        default=EstadoProcesoFirmasConvenio.CONFIGURACION.value,
        server_default=EstadoProcesoFirmasConvenio.CONFIGURACION.value,
        nullable=False,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    iniciado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    convenio: Mapped[Convenio] = relationship(back_populates="procesos_firmas")
    version_convenio: Mapped[VersionConvenio] = relationship(
        back_populates="procesos_firmas"
    )
    revision_final: Mapped[RevisionConvenio] = relationship(
        back_populates="proceso_firmas"
    )
    creado_por: Mapped[Usuario] = relationship(foreign_keys=[creado_por_id])
    firmas: Mapped[list[FirmaConvenio]] = relationship(
        back_populates="proceso_firmas",
        cascade="all, delete-orphan",
        order_by="FirmaConvenio.orden",
    )
