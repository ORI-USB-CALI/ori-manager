from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.roles import TipoUsuario
from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.rol import Rol
    from backend.models.token_credencial import TokenCredencial
    from backend.models.unidad_organizacional import UnidadOrganizacional

_TIPOS_USUARIO_SQL = ", ".join(f"'{tipo.value}'" for tipo in TipoUsuario)


class Usuario(Base):
    """Usuario interno o externo con acceso al sistema."""

    __tablename__ = "usuario"
    __table_args__ = (
        CheckConstraint(
            f"tipo_usuario IN ({_TIPOS_USUARIO_SQL})",
            name="ck_usuario_tipo_usuario",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    correo: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    hash_contrasena: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(160), nullable=False)
    documento_identidad: Mapped[str | None] = mapped_column(String(40), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cargo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rol_id: Mapped[int] = mapped_column(
        ForeignKey("rol.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tipo_usuario: Mapped[str] = mapped_column(String(7), nullable=False)
    unidad_organizacional_id: Mapped[int | None] = mapped_column(
        ForeignKey("unidad_organizacional.id"),
        nullable=True,
    )
    entidad_externa: Mapped[str | None] = mapped_column(String(160), nullable=True)
    activo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )
    ultimo_acceso: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    correo_verificado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    rol: Mapped["Rol"] = relationship(back_populates="usuarios")
    unidad_organizacional: Mapped["UnidadOrganizacional | None"] = relationship(
        back_populates="usuarios"
    )
    tokens_credencial: Mapped[list["TokenCredencial"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
    )

    def puede_iniciar_sesion(self) -> bool:
        return self.activo

    def desactivar(self) -> None:
        self.activo = False

    def es_interno(self) -> bool:
        return self.tipo_usuario == TipoUsuario.INTERNO
