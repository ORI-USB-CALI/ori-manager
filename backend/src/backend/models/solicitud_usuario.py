from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class SolicitudUsuario(Base):
    """Asociación explícita que también concede acceso de lectura al solicitante."""

    __tablename__ = "solicitud_usuario"
    __table_args__ = (
        UniqueConstraint("solicitud_id", "usuario_id", name="uq_solicitud_usuario"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(
        ForeignKey("solicitud_convenio.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
