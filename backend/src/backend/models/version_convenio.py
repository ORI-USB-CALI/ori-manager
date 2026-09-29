from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import ContextoVersionConvenio

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.etapa import Etapa
    from backend.models.plantilla_convenio import PlantillaConvenio
    from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
    from backend.models.revision_convenio import RevisionConvenio
    from backend.models.usuario import Usuario

_CONTEXTOS = ", ".join(f"'{valor.value}'" for valor in ContextoVersionConvenio)


class VersionConvenio(Base):
    __tablename__ = "version_convenio"
    __table_args__ = (
        UniqueConstraint("convenio_id", "numero", name="uq_version_convenio_numero"),
        CheckConstraint("numero > 0", name="ck_version_convenio_numero_positivo"),
        CheckConstraint(
            f"contexto IN ({_CONTEXTOS})", name="ck_version_convenio_contexto"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    contenido: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    autor_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    etapa_id: Mapped[int] = mapped_column(
        ForeignKey("etapa.id", ondelete="RESTRICT"), nullable=False
    )
    contexto: Mapped[str] = mapped_column(String(30), nullable=False)
    plantilla_id: Mapped[int | None] = mapped_column(
        ForeignKey("plantilla_convenio.id", ondelete="RESTRICT"), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    convenio: Mapped[Convenio] = relationship(back_populates="versiones")
    autor: Mapped[Usuario] = relationship(foreign_keys=[autor_id])
    etapa: Mapped[Etapa] = relationship()
    plantilla: Mapped[PlantillaConvenio | None] = relationship(
        back_populates="versiones"
    )
    revisiones_recibidas: Mapped[list[RevisionConvenio]] = relationship(
        back_populates="version_convenio",
        foreign_keys="RevisionConvenio.version_convenio_id",
    )
    revisiones_resultado: Mapped[list[RevisionConvenio]] = relationship(
        back_populates="version_resultado",
        foreign_keys="RevisionConvenio.version_resultado_id",
    )
    procesos_firmas: Mapped[list[ProcesoFirmasConvenio]] = relationship(
        back_populates="version_convenio"
    )
