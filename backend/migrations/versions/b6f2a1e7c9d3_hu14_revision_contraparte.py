"""HU-14 historial de etapa y observaciones de revision de contraparte.

Revision ID: b6f2a1e7c9d3
Revises: a711c4d8e912
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6f2a1e7c9d3"
down_revision: str | Sequence[str] | None = "a711c4d8e912"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historial_etapa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("etapa_origen_id", sa.Integer(), nullable=True),
        sa.Column("etapa_destino_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column("numero_ciclo", sa.SmallInteger(), nullable=False),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("fecha_cambio", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["convenio_id"], ["convenio.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["etapa_origen_id"], ["etapa.id"]),
        sa.ForeignKeyConstraint(["etapa_destino_id"], ["etapa.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["responsable_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_historial_etapa_convenio_id", "historial_etapa", ["convenio_id"], unique=False
    )

    op.create_table(
        "observacion_revision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("historial_etapa_id", sa.Integer(), nullable=False),
        sa.Column("origen", sa.String(length=20), nullable=False),
        sa.Column("registrada_por_id", sa.Integer(), nullable=False),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("respuesta", sa.Text(), nullable=True),
        sa.Column("atendida_por_id", sa.Integer(), nullable=True),
        sa.Column("fecha_atencion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default=sa.text("'PENDIENTE'"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "origen IN ('REVISOR_ORI', 'CONTRAPARTE', 'REVISION_FINAL_ORI')",
            name="ck_observacion_revision_origen",
        ),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE', 'ATENDIDA')",
            name="ck_observacion_revision_estado",
        ),
        sa.ForeignKeyConstraint(["convenio_id"], ["convenio.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["historial_etapa_id"], ["historial_etapa.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["registrada_por_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["responsable_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["atendida_por_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_observacion_revision_convenio_id", "observacion_revision", ["convenio_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("observacion_revision")
    op.drop_table("historial_etapa")
