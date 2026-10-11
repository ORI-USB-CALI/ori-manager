from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.usuario import Usuario


class EvaluacionConvenio(Base):
    """Evaluación única e inmutable de un convenio finalizado.

    `creado_en` es la fecha y hora oficial de la evaluación (CA-06): se genera
    automáticamente al registrarla y no se modifica. Por eso no se almacena un
    `fecha_evaluacion` aparte, que representaría el mismo evento.
    """

    __tablename__ = "evaluacion_convenio"
    __table_args__ = (
        UniqueConstraint("convenio_id", name="uq_evaluacion_convenio_convenio"),
        CheckConstraint(
            "calificacion BETWEEN 1 AND 10",
            name="ck_evaluacion_convenio_calificacion",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="RESTRICT"), nullable=False
    )
    evaluado_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    fue_funcional: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Nivel de cumplimiento de lo pactado (RN-08): 1 muy bajo, 10 total.
    calificacion: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    observaciones: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    convenio: Mapped[Convenio] = relationship(back_populates="evaluacion")
    evaluado_por: Mapped[Usuario] = relationship(foreign_keys=[evaluado_por_id])
