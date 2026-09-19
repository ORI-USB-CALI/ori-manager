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
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import TipoAliado, TipoIdentificacion

if TYPE_CHECKING:
    from backend.models.contacto_aliado import ContactoAliado
    from backend.models.convenio import Convenio
    from backend.models.pais import Pais
    from backend.models.solicitud_convenio import SolicitudConvenio

_TIPOS = ", ".join(f"'{tipo.value}'" for tipo in TipoAliado)
_TIPOS_IDENTIFICACION = ", ".join(f"'{tipo.value}'" for tipo in TipoIdentificacion)


class Aliado(Base):
    __tablename__ = "aliado"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_TIPOS})", name="ck_aliado_tipo"),
        CheckConstraint(f"tipo_identificacion IN ({_TIPOS_IDENTIFICACION})", name="ck_aliado_tipo_identificacion"),
        UniqueConstraint("tipo_identificacion", "identificacion", name="uq_aliado_tipo_identificacion"),
        CheckConstraint(
            "tipo != 'EMPRESA' OR (sector_economico IS NOT NULL AND "
            "btrim(sector_economico) != '')",
            name="ck_aliado_empresa_sector_economico",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(22), nullable=False)
    sector_economico: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tipo_identificacion: Mapped[str] = mapped_column(String(33), nullable=False)
    identificacion: Mapped[str] = mapped_column(String(40), nullable=False)
    pais_id: Mapped[int | None] = mapped_column(ForeignKey("pais.id"), nullable=True)
    ciudad: Mapped[str | None] = mapped_column(String(120), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    correo: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sitio_web: Mapped[str | None] = mapped_column(String(200), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    pais: Mapped[Pais | None] = relationship()
    contactos: Mapped[list[ContactoAliado]] = relationship(back_populates="aliado")
    convenios: Mapped[list[Convenio]] = relationship(back_populates="aliado")
    solicitudes: Mapped[list[SolicitudConvenio]] = relationship(back_populates="aliado")
