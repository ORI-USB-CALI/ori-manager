import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class EstadoAliado(str, enum.Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"


class EstadoConvenio(str, enum.Enum):
    VIGENTE = "VIGENTE"
    EN_TRAMITE = "EN_TRAMITE"
    FINALIZADO = "FINALIZADO"
    VENCIDO = "VENCIDO"
    CANCELADO = "CANCELADO"


class Aliado(Base):
    __tablename__ = "aliados"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    nit_o_identificacion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tipo_aliado: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[EstadoAliado] = mapped_column(
        Enum(EstadoAliado, name="estado_aliado_enum", native_enum=False),
        nullable=False,
        default=EstadoAliado.ACTIVO,
    )
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


    convenios: Mapped[list["Convenio"]] = relationship(
        "Convenio", back_populates="aliado", cascade="all, delete-orphan"
    )


class Convenio(Base):
    __tablename__ = "convenios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    aliado_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("aliados.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codigo: Mapped[str] = mapped_column(String(100), nullable=False)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_convenio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[EstadoConvenio] = mapped_column(
        Enum(EstadoConvenio, name="estado_convenio_enum", native_enum=False),
        nullable=False,
        default=EstadoConvenio.VIGENTE,
    )
    fecha_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


    aliado: Mapped["Aliado"] = relationship("Aliado", back_populates="convenios")
