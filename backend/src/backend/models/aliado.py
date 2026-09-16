from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.db.base import Base
from backend.models.enums import EstadoAliado, TipoAliado

if TYPE_CHECKING:
    from backend.models.contacto_aliado import ContactoAliado


class Aliado(Base):
    __tablename__ = "aliado"

    id: Mapped[int] = mapped_column(primary_key=True)
    identificacion: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[TipoAliado] = mapped_column(
        SAEnum(TipoAliado, name="tipo_aliado"), nullable=False
    )
    sector_economico: Mapped[str | None] = mapped_column(String(120))
    pais_id: Mapped[int | None] = mapped_column(ForeignKey("pais.id"))
    ciudad: Mapped[str | None] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(String(200))
    telefono: Mapped[str | None] = mapped_column(String(40))
    correo: Mapped[str | None] = mapped_column(String(160))
    sitio_web: Mapped[str | None] = mapped_column(String(200))
    estado: Mapped[EstadoAliado] = mapped_column(
        SAEnum(EstadoAliado, name="estado_aliado"),
        nullable=False,
        default=EstadoAliado.ACTIVO,
    )
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    contactos: Mapped[list["ContactoAliado"]] = relationship(back_populates="aliado")
