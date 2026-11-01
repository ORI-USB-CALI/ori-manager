from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import CodigoGuia, EstadoGuia

if TYPE_CHECKING:
    from backend.models.usuario import Usuario

_GUIAS = ", ".join(f"'{valor.value}'" for valor in CodigoGuia)
_ESTADOS_FINALES = ", ".join(
    f"'{valor.value}'" for valor in (EstadoGuia.COMPLETADO, EstadoGuia.OMITIDO)
)


class EstadoGuiaUsuario(Base):
    """HU-38. Estado final de una guía para un usuario. Sin fila, la guía
    está PENDIENTE (RN-03); por eso no hay backfill de usuarios existentes."""

    __tablename__ = "estado_guia_usuario"
    __table_args__ = (
        UniqueConstraint("usuario_id", "guia", name="uq_estado_guia_usuario_usuario_guia"),
        CheckConstraint(f"guia IN ({_GUIAS})", name="ck_estado_guia_usuario_guia"),
        CheckConstraint(
            f"estado IN ({_ESTADOS_FINALES})", name="ck_estado_guia_usuario_estado"
        ),
        CheckConstraint("version >= 1", name="ck_estado_guia_usuario_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    guia: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id])
