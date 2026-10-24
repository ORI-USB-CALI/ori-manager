from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import AccionAuditoria, EjecucionAuditoria

if TYPE_CHECKING:
    from backend.models.usuario import Usuario

_ACCIONES = ", ".join(f"'{valor.value}'" for valor in AccionAuditoria)
_EJECUCIONES = ", ".join(f"'{valor.value}'" for valor in EjecucionAuditoria)


class Auditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = (
        CheckConstraint(f"accion IN ({_ACCIONES})", name="ck_auditoria_accion"),
        CheckConstraint(
            f"ejecucion IS NULL OR ejecucion IN ({_EJECUCIONES})",
            name="ck_auditoria_ejecucion",
        ),
        # HT-09: toda acción humana debe traer su usuario; solo un proceso
        # automático puede carecer de uno. Los registros previos a HT-09
        # ya tenían usuario_id, así que ninguno viola esta regla.
        # IS NOT DISTINCT FROM (no "="): en SQL, "ejecucion = 'AUTOMATICA'" da
        # NULL (no FALSE) cuando ejecucion es NULL, y Postgres acepta un CHECK
        # que evalúa a NULL. Con "=" esta fila quedaría sin cubrir: sin
        # usuario_id y sin declarar ejecución.
        CheckConstraint(
            "usuario_id IS NOT NULL OR ejecucion IS NOT DISTINCT FROM 'AUTOMATICA'",
            name="ck_auditoria_usuario_o_automatica",
        ),
        Index("ix_auditoria_entidad_registro", "entidad", "registro_id"),
        Index("ix_auditoria_entidad_fecha_hora", "entidad", "fecha_hora"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # HT-09: nulo únicamente en procesos automáticos sin usuario originador
    # (CA-03); ver el CHECK ck_auditoria_usuario_o_automatica.
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    # Copia del código de rol al momento de la acción: el rol del usuario puede
    # cambiar después y la bitácora debe mostrar con qué rol actuó. Es nullable
    # porque los registros previos a HU-18 se completan con el rol vigente, y
    # porque los procesos automáticos no tienen un rol humano que copiar.
    rol: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entidad: Mapped[str] = mapped_column(String(80), nullable=False)
    registro_id: Mapped[int] = mapped_column(Integer, nullable=False)
    accion: Mapped[str] = mapped_column(String(10), nullable=False)
    # campo, valor_anterior y valor_nuevo quedan nulos en acciones INSERT y DELETE,
    # donde el registro cambia completo y no hay un campo puntual que señalar.
    campo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    valor_anterior: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_nuevo: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Acción de negocio que originó el cambio ("Aprobó la revisión jurídica 1 de
    # la ronda 2"). Es nula en los cambios que no la declaran.
    contexto: Mapped[str | None] = mapped_column(Text, nullable=True)
    # HT-09, CA-01/CA-05: identifica estructuradamente la acción de negocio
    # (p. ej. "VERSION_GENERADA"), independiente del texto libre de `contexto`.
    evento: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Copia del código de etapa al momento de la acción, igual que `rol`.
    etapa: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Versión formal del convenio asociada a la acción, cuando aplique.
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # HT-09, CA-02/CA-03: si la acción la originó una persona o un proceso
    # automático. Nula en los registros previos a HT-09 (CA-07): no se puede
    # reconstruir esa información de forma confiable para el pasado.
    ejecucion: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # HT-09, CA-04: responsable de negocio de la operación, distinto del
    # usuario que la originó o la ejecutó. Nulo cuando no exista una
    # asignación verificable.
    responsable_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True
    )
    direccion_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    usuario: Mapped[Usuario | None] = relationship(foreign_keys=[usuario_id])
    responsable: Mapped[Usuario | None] = relationship(foreign_keys=[responsable_id])
