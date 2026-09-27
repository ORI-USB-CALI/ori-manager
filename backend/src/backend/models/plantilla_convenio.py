from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.usuario import Usuario
    from backend.models.version_convenio import VersionConvenio


class PlantillaConvenio(Base):
    __tablename__ = "plantilla_convenio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    contenido_base: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    activa: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False, index=True
    )
    creado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
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

    creado_por: Mapped[Usuario | None] = relationship(foreign_keys=[creado_por_id])
    convenios: Mapped[list[Convenio]] = relationship(back_populates="plantilla_origen")
    versiones: Mapped[list[VersionConvenio]] = relationship(back_populates="plantilla")
