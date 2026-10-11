"""Bitácora de conciliación automática, sin atribución a un usuario humano."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class TransicionEstadoConvenio(Base):
    __tablename__ = "transicion_estado_convenio"
    __table_args__ = (
        CheckConstraint("actor = 'SISTEMA'", name="ck_transicion_convenio_actor"),
        CheckConstraint(
            "estado_anterior <> estado_nuevo",
            name="ck_transicion_convenio_cambio",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="RESTRICT"), index=True
    )
    actor: Mapped[str] = mapped_column(
        String(20), default="SISTEMA", server_default="SISTEMA"
    )
    estado_anterior: Mapped[str] = mapped_column(String(20))
    estado_nuevo: Mapped[str] = mapped_column(String(20))
    fecha_referencia: Mapped[date] = mapped_column(Date)
    fecha_vencimiento: Mapped[date] = mapped_column(Date)
    ejecutado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
