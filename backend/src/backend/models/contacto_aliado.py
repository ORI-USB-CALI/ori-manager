from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.db.base import Base
from backend.models.aliado import Aliado


class ContactoAliado(Base):
    __tablename__ = "contacto_aliado"

    id: Mapped[int] = mapped_column(primary_key=True)
    aliado_id: Mapped[int] = mapped_column(ForeignKey("aliado.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    cargo: Mapped[str | None] = mapped_column(String(120))
    correo: Mapped[str | None] = mapped_column(String(160))
    telefono: Mapped[str | None] = mapped_column(String(40))
    extension: Mapped[str | None] = mapped_column(String(20))
    es_principal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    aliado: Mapped[Aliado] = relationship(back_populates="contactos")
