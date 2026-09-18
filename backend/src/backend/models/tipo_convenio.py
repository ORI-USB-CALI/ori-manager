from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.models.enums import NaturalezaConvenio

_NATURALEZAS = ", ".join(f"'{valor.value}'" for valor in NaturalezaConvenio)


class TipoConvenio(Base):
    __tablename__ = "tipo_convenio"
    __table_args__ = (CheckConstraint(f"naturaleza IN ({_NATURALEZAS})", name="ck_tipo_convenio_naturaleza"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    naturaleza: Mapped[str] = mapped_column(String(10), nullable=False)
    duracion_meses_defecto: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
