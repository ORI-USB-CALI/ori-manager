from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import (
    EstadoSolicitud,
    TipoAliado,
    TipoIdentificacion,
    TipoSolicitante,
)

if TYPE_CHECKING:
    from backend.models.aliado import Aliado
    from backend.models.convenio import Convenio
    from backend.models.documento import Documento
    from backend.models.tipo_convenio import TipoConvenio
    from backend.models.usuario import Usuario

_TIPOS = ", ".join(f"'{valor.value}'" for valor in TipoSolicitante)
_ESTADOS = ", ".join(f"'{valor.value}'" for valor in EstadoSolicitud)
_TIPOS_ALIADO = ", ".join(f"'{valor.value}'" for valor in TipoAliado)
_TIPOS_IDENTIFICACION = ", ".join(f"'{valor.value}'" for valor in TipoIdentificacion)


class SolicitudConvenio(Base):
    __tablename__ = "solicitud_convenio"
    __table_args__ = (
        CheckConstraint(
            f"tipo_solicitante IN ({_TIPOS})", name="ck_solicitud_tipo_solicitante"
        ),
        CheckConstraint(f"estado IN ({_ESTADOS})", name="ck_solicitud_estado"),
        CheckConstraint(
            f"tipo_identificacion_aliado_propuesto IN ({_TIPOS_IDENTIFICACION})",
            name="ck_solicitud_tipo_identificacion_aliado_propuesto",
        ),
        CheckConstraint(
            f"tipo_aliado_propuesto IN ({_TIPOS_ALIADO})",
            name="ck_solicitud_tipo_aliado_propuesto",
        ),
        Index("ix_solicitud_convenio_solicitante_estado", "solicitante_id", "estado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consecutivo: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    tipo_solicitante: Mapped[str] = mapped_column(String(7), nullable=False)
    solicitante_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    unidad_organizacional_id: Mapped[int | None] = mapped_column(
        ForeignKey("unidad_organizacional.id"), nullable=True
    )
    aliado_id: Mapped[int | None] = mapped_column(
        ForeignKey("aliado.id"), nullable=True
    )
    nombre_aliado_propuesto: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    tipo_identificacion_aliado_propuesto: Mapped[str | None] = mapped_column(
        String(33), nullable=True
    )
    identificacion_aliado_propuesto: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    tipo_aliado_propuesto: Mapped[str | None] = mapped_column(String(22), nullable=True)
    correo_aliado_propuesto: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    pais_aliado_propuesto: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ciudad_aliado_propuesto: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    telefono_aliado_propuesto: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    direccion_aliado_propuesto: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    sector_economico_aliado_propuesto: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    tipo_convenio_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipo_convenio.id"), nullable=True
    )
    objeto: Mapped[str | None] = mapped_column(Text, nullable=True)
    justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    actividades_por_parte: Mapped[str | None] = mapped_column(Text, nullable=True)
    metas_esperadas: Mapped[str | None] = mapped_column(Text, nullable=True)
    implicacion_financiera: Mapped[str | None] = mapped_column(Text, nullable=True)
    vigencia_estimada: Mapped[str | None] = mapped_column(String(120), nullable=True)
    requisitos_renovacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    contacto_contraparte_nombre: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    contacto_contraparte_cargo: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    contacto_contraparte_telefono: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    contacto_contraparte_correo: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    supervisor_usb_nombre: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    supervisor_usb_cargo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    supervisor_usb_telefono: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    supervisor_usb_correo: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    supervisor_contraparte_nombre: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    supervisor_contraparte_cargo: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    supervisor_contraparte_telefono: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    supervisor_contraparte_correo: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    solicitante_nombre: Mapped[str | None] = mapped_column(String(160), nullable=True)
    solicitante_correo: Mapped[str | None] = mapped_column(String(160), nullable=True)
    solicitante_documento: Mapped[str | None] = mapped_column(String(40), nullable=True)
    solicitante_cargo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    solicitante_entidad: Mapped[str | None] = mapped_column(String(160), nullable=True)
    solicitante_unidad: Mapped[str | None] = mapped_column(String(160), nullable=True)
    solicitante_programa: Mapped[str | None] = mapped_column(String(160), nullable=True)
    aprobada_por_director: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    fecha_aprobacion_director: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_radicacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fecha_recibido_ori: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        default=EstadoSolicitud.BORRADOR.value,
        server_default=EstadoSolicitud.BORRADOR.value,
        nullable=False,
    )
    motivo_rechazo: Mapped[str | None] = mapped_column(Text, nullable=True)
    decidida_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    fecha_decision: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    aliado: Mapped[Aliado | None] = relationship(back_populates="solicitudes")
    convenio: Mapped[Convenio | None] = relationship(
        back_populates="solicitud", uselist=False
    )
    tipo_convenio: Mapped[TipoConvenio | None] = relationship()
    solicitante: Mapped[Usuario] = relationship(foreign_keys=[solicitante_id])
    decidida_por: Mapped[Usuario | None] = relationship(foreign_keys=[decidida_por_id])
    documentos: Mapped[list[Documento]] = relationship(back_populates="solicitud")
