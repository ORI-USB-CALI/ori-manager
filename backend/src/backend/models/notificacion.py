from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import EntidadNotificacion, TipoNotificacion

if TYPE_CHECKING:
    from backend.models.usuario import Usuario

_TIPOS = ", ".join(f"'{valor.value}'" for valor in TipoNotificacion)
_ENTIDADES = ", ".join(f"'{valor.value}'" for valor in EntidadNotificacion)


class Notificacion(Base):
    """HU-33. Una fila por destinatario real (fan-out al crearse), no una
    notificación compartida entre varios usuarios: así "leída" (CA-08) es
    una columna propia de cada fila y no requiere una tabla de lectura
    aparte. Ver services/notificaciones.py para el porqué del índice único
    parcial de abajo.
    """

    __tablename__ = "notificacion"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_TIPOS})", name="ck_notificacion_tipo"),
        CheckConstraint(
            f"entidad_tipo IN ({_ENTIDADES})", name="ck_notificacion_entidad_tipo"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    entidad_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    entidad_id: Mapped[int] = mapped_column(Integer, nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    leida: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    leida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resuelta: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id])
