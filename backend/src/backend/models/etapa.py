from sqlalchemy import Boolean, Integer, SmallInteger, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Etapa(Base):
    __tablename__ = "etapa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    orden: Mapped[int] = mapped_column(SmallInteger, unique=True, nullable=False)
    codigo: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_responsable: Mapped[str | None] = mapped_column(String(120), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
