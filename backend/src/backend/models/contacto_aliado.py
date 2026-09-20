from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.aliado import Aliado


class ContactoAliado(Base):
    __tablename__ = "contacto_aliado"
    __table_args__ = (UniqueConstraint("aliado_id", "correo", name="uq_contacto_aliado_correo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aliado_id: Mapped[int] = mapped_column(ForeignKey("aliado.id", ondelete="CASCADE"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    cargo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    correo: Mapped[str | None] = mapped_column(String(160), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    es_principal: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    aliado: Mapped[Aliado] = relationship(back_populates="contactos")
