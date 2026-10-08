from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import (
    EstadoRevisionConvenio,
    ResultadoRevisionConvenio,
    TipoRevisionConvenio,
)

if TYPE_CHECKING:
    from backend.models.convenio import Convenio
    from backend.models.documento import Documento
    from backend.models.historial_etapa import HistorialEtapa
    from backend.models.invitacion_revision_contraparte import (
        InvitacionRevisionContraparte,
    )
    from backend.models.observacion_revision import ObservacionRevision
    from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
    from backend.models.respuesta_revision_contraparte import (
        RespuestaRevisionContraparte,
    )
    from backend.models.usuario import Usuario
    from backend.models.version_convenio import VersionConvenio

_TIPOS = ", ".join(f"'{valor.value}'" for valor in TipoRevisionConvenio)
_ESTADOS = ", ".join(f"'{valor.value}'" for valor in EstadoRevisionConvenio)
_RESULTADOS = ", ".join(f"'{valor.value}'" for valor in ResultadoRevisionConvenio)


class RevisionConvenio(Base):
    __tablename__ = "revision_convenio"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_TIPOS})", name="ck_revision_convenio_tipo"),
        CheckConstraint(
            f"estado IN ({_ESTADOS})", name="ck_revision_convenio_estado"
        ),
        CheckConstraint(
            f"resultado IS NULL OR resultado IN ({_RESULTADOS})",
            name="ck_revision_convenio_resultado",
        ),
        CheckConstraint(
            "instancia_juridica IS NULL OR instancia_juridica IN (1, 2)",
            name="ck_revision_convenio_instancia_juridica",
        ),
        CheckConstraint(
            "numero_ronda IS NULL OR numero_ronda > 0",
            name="ck_revision_convenio_numero_ronda_positivo",
        ),
        CheckConstraint(
            "(instancia_juridica IS NULL) = (numero_ronda IS NULL)",
            name="ck_revision_convenio_coordenadas_juridicas",
        ),
        UniqueConstraint(
            "convenio_id",
            "tipo",
            "numero_ronda",
            "instancia_juridica",
            name="uq_revision_convenio_ronda_instancia",
        ),
        Index(
            "uq_revision_convenio_juridica_pendiente",
            "convenio_id",
            unique=True,
            postgresql_where=text("tipo = 'JURIDICA' AND estado = 'PENDIENTE'"),
        ),
        Index(
            "uq_revision_convenio_contraparte_pendiente",
            "convenio_id",
            unique=True,
            postgresql_where=text("tipo = 'CONTRAPARTE' AND estado = 'PENDIENTE'"),
        ),
        Index(
            "uq_revision_convenio_final_pendiente",
            "convenio_id",
            unique=True,
            postgresql_where=text("tipo = 'FINAL' AND estado = 'PENDIENTE'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenio.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    historial_etapa_id: Mapped[int | None] = mapped_column(
        ForeignKey("historial_etapa.id", ondelete="RESTRICT"), nullable=True
    )
    documento_id: Mapped[int | None] = mapped_column(
        ForeignKey("documento.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    version_convenio_id: Mapped[int | None] = mapped_column(
        ForeignKey("version_convenio.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    version_resultado_id: Mapped[int | None] = mapped_column(
        ForeignKey("version_convenio.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    instancia_juridica: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    numero_ronda: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsable_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    creada_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        default=EstadoRevisionConvenio.PENDIENTE.value,
        server_default=EstadoRevisionConvenio.PENDIENTE.value,
        nullable=False,
    )
    resultado: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resuelta_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    # Estado exacto de los datos del convenio presentados en esta ronda. Se escribe
    # una sola vez, al crear la revisión, y no vuelve a modificarse: si hay
    # correcciones, la siguiente ronda es otra RevisionConvenio con otro snapshot.
    # Nullable a nivel de columna por compatibilidad con revisiones de otro origen.
    snapshot_datos: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resuelta_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    convenio: Mapped[Convenio] = relationship(back_populates="revisiones")
    historial_etapa: Mapped[HistorialEtapa | None] = relationship()
    documento: Mapped[Documento | None] = relationship(back_populates="revisiones")
    version_convenio: Mapped[VersionConvenio | None] = relationship(
        back_populates="revisiones_recibidas", foreign_keys=[version_convenio_id]
    )
    version_resultado: Mapped[VersionConvenio | None] = relationship(
        back_populates="revisiones_resultado", foreign_keys=[version_resultado_id]
    )
    responsable: Mapped[Usuario | None] = relationship(
        foreign_keys=[responsable_id]
    )
    creada_por: Mapped[Usuario | None] = relationship(foreign_keys=[creada_por_id])
    resuelta_por: Mapped[Usuario | None] = relationship(
        foreign_keys=[resuelta_por_id]
    )
    observaciones: Mapped[list[ObservacionRevision]] = relationship(
        back_populates="revision_convenio", order_by="ObservacionRevision.id"
    )
    invitaciones_contraparte: Mapped[list[InvitacionRevisionContraparte]] = relationship(
        back_populates="revision_convenio",
        cascade="all, delete-orphan",
    )
    respuesta_contraparte: Mapped[RespuestaRevisionContraparte | None] = relationship(
        back_populates="revision_convenio",
        cascade="all, delete-orphan",
        uselist=False,
    )
    proceso_firmas: Mapped[ProcesoFirmasConvenio | None] = relationship(
        back_populates="revision_final", uselist=False
    )
