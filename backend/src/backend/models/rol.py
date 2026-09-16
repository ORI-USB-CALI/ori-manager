from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.base import Base


class Rol(Base):
    """Rol de acceso autenticado. Catalogo administrable (RN-04)."""

    __tablename__ = "rol"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255))
    es_interno: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    usuarios: Mapped[list["Usuario"]] = relationship("Usuario", back_populates="rol")  # noqa: F821

    def permite_administrar_usuarios(self) -> bool:
        """RN-01: solo el Administrador ORI administra usuarios."""
        return self.codigo == "ADMINISTRADOR_ORI"