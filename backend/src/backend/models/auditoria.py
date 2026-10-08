from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import AccionAuditoria

if TYPE_CHECKING:
    from backend.models.usuario import Usuario

_ACCIONES = ", ".join(f"'{valor.value}'" for valor in AccionAuditoria)


class Auditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = (
        CheckConstraint(f"accion IN ({_ACCIONES})", name="ck_auditoria_accion"),
        Index("ix_auditoria_entidad_registro", "entidad", "registro_id"),
        Index("ix_auditoria_entidad_fecha_hora", "entidad", "fecha_hora"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    # Copia del código de rol al momento de la acción: el rol del usuario puede
    # cambiar después y la bitácora debe mostrar con qué rol actuó. Es nullable
    # porque los registros previos a HU-18 se completan con el rol vigente.
    rol: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entidad: Mapped[str] = mapped_column(String(80), nullable=False)
    registro_id: Mapped[int] = mapped_column(Integer, nullable=False)
    accion: Mapped[str] = mapped_column(String(10), nullable=False)
    # campo, valor_anterior y valor_nuevo quedan nulos en acciones INSERT y DELETE,
    # donde el registro cambia completo y no hay un campo puntual que señalar.
    campo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    valor_anterior: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_nuevo: Mapped[str | None] = mapped_column(Text, nullable=True)
    direccion_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id])
