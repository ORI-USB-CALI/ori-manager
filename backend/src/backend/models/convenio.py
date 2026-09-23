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
from backend.models.enums import AlcanceConvenio, EstadoConvenio

if TYPE_CHECKING:
    from backend.models.aliado import Aliado
    from backend.models.documento import Documento
    from backend.models.etapa import Etapa
    from backend.models.historial_etapa import HistorialEtapa
    from backend.models.observacion_revision import ObservacionRevision
    from backend.models.solicitud_convenio import SolicitudConvenio
    from backend.models.tipo_convenio import TipoConvenio
    from backend.models.unidad_organizacional import UnidadOrganizacional
    from backend.models.usuario import Usuario

_ESTADOS = ", ".join(f"'{valor.value}'" for valor in EstadoConvenio)
_ALCANCES = ", ".join(f"'{valor.value}'" for valor in AlcanceConvenio)


class Convenio(Base):
    __tablename__ = "convenio"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_ESTADOS})", name="ck_convenio_estado"),
        CheckConstraint(f"alcance IS NULL OR alcance IN ({_ALCANCES})", name="ck_convenio_alcance"),
        CheckConstraint("porcentaje_avance IS NULL OR porcentaje_avance BETWEEN 0 AND 100", name="ck_convenio_porcentaje_avance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitud_convenio.id"), unique=True, nullable=False)
    aliado_id: Mapped[int | None] = mapped_column(ForeignKey("aliado.id"), nullable=True)
    tipo_convenio_id: Mapped[int | None] = mapped_column(ForeignKey("tipo_convenio.id"), nullable=True)
    etapa_actual_id: Mapped[int | None] = mapped_column(ForeignKey("etapa.id"), nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default=EstadoConvenio.EN_TRAMITE.value, server_default=EstadoConvenio.EN_TRAMITE.value, nullable=False)
    objeto: Mapped[str | None] = mapped_column(Text, nullable=True)
    alcance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unidad_organizacional_id: Mapped[int | None] = mapped_column(ForeignKey("unidad_organizacional.id"), nullable=True)
    implicacion_financiera: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_firma: Mapped[date | None] = mapped_column(Date, nullable=True)
    duracion_meses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    porcentaje_avance: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    convenio_origen_id: Mapped[int | None] = mapped_column(ForeignKey("convenio.id"), nullable=True)
    numero_renovacion: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    creado_por_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    solicitud: Mapped[SolicitudConvenio] = relationship(back_populates="convenio")
    aliado: Mapped[Aliado | None] = relationship(back_populates="convenios")
    tipo_convenio: Mapped[TipoConvenio | None] = relationship()
    etapa_actual: Mapped[Etapa | None] = relationship()
    unidad_organizacional: Mapped[UnidadOrganizacional | None] = relationship()
    creado_por: Mapped[Usuario] = relationship(foreign_keys=[creado_por_id])
    convenio_origen: Mapped[Convenio | None] = relationship(remote_side=[id])
    documentos: Mapped[list[Documento]] = relationship(
        back_populates="convenio", foreign_keys="Documento.convenio_id"
    )
    historial_etapas: Mapped[list[HistorialEtapa]] = relationship(
        back_populates="convenio"
    )
    observaciones_revision: Mapped[list[ObservacionRevision]] = relationship(
        back_populates="convenio"
    )
