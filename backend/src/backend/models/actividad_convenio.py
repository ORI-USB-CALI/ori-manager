from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import EstadoActividadConvenio, ParteEjecutoraActividad

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.usuario import Usuario

_PARTES = ", ".join(f"'{valor.value}'" for valor in ParteEjecutoraActividad)
_ESTADOS = ", ".join(f"'{valor.value}'" for valor in EstadoActividadConvenio)


class ActividadConvenio(Base):
    """HU-34/HU-36. Actividad ejecutada o planeada durante la vigencia de un
    convenio, tal como la define el MER aprobado.

    Solo lectura por ahora: esta tabla la consultan los reportes de HU-34 y
    HU-36. El registro de actividades (crearlas, editarlas, marcarlas como
    realizadas) es alcance de HU-35 y no se implementa aquí. Como hoy no
    existe ningún punto de entrada para crearlas, los convenios reportados
    aparecerán todos sin actividades hasta que HU-35 se implemente — eso es
    exactamente lo que CA-03 de HU-34 espera que el reporte maneje.
    """

    __tablename__ = "actividad_convenio"
    __table_args__ = (
        CheckConstraint(f"parte_ejecutora IN ({_PARTES})", name="ck_actividad_convenio_parte_ejecutora"),
        CheckConstraint(f"estado IN ({_ESTADOS})", name="ck_actividad_convenio_estado"),
        CheckConstraint(
            "numero_participantes IS NULL OR numero_participantes >= 0",
            name="ck_actividad_convenio_participantes_no_negativo",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    parte_ejecutora: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_planificada: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_ejecucion: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(
        String(20),
        default=EstadoActividadConvenio.PENDIENTE.value,
        server_default=EstadoActividadConvenio.PENDIENTE.value,
        nullable=False,
    )
    resultado: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_participantes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    responsable_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    convenio: Mapped[Convenio] = relationship(back_populates="actividades")
    responsable: Mapped[Usuario | None] = relationship(foreign_keys=[responsable_id])
