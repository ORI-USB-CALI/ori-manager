from sqlalchemy import CHAR, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Pais(Base):
    __tablename__ = "pais"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_iso: Mapped[str] = mapped_column(CHAR(2), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
