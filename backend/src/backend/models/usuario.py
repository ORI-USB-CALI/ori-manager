from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.base import Base
from backend.models.rol import Rol


class Usuario(Base):
    """Usuario interno del sistema (HU-03)."""

    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    correo: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    hash_contrasena: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(160), nullable=False)
    documento_identidad: Mapped[str | None] = mapped_column(String(40))
    telefono: Mapped[str | None] = mapped_column(String(40))
    cargo: Mapped[str | None] = mapped_column(String(120))
    rol_id: Mapped[int] = mapped_column(
        ForeignKey("rol.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    tipo_usuario: Mapped[str] = mapped_column(String(20), default="INTERNO", nullable=False)
    entidad_externa: Mapped[str | None] = mapped_column(String(160))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    rol: Mapped[Rol] = relationship("Rol", back_populates="usuarios", lazy="joined")

    def puede_iniciar_sesion(self) -> bool:
        """RN-06: un usuario inactivo no puede autenticarse."""
        return self.activo

    def desactivar(self) -> None:
        """RN-05: la desactivacion es logica, no elimina el registro."""
        self.activo = False