"""Crear infraestructura base de trazabilidad y observaciones.

Revision ID: e41c9a7b2d53
Revises: d8f4b2a1c6e7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e41c9a7b2d53"
down_revision: str | Sequence[str] | None = "d8f4b2a1c6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historial_etapa",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("etapa_origen_id", sa.Integer(), nullable=True),
        sa.Column("etapa_destino_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column(
            "fecha_cambio",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["convenio_id"], ["convenio.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["etapa_origen_id"], ["etapa.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["etapa_destino_id"], ["etapa.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["responsable_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_historial_etapa_convenio_id", "historial_etapa", ["convenio_id"]
    )
    op.create_index(
        "ix_historial_etapa_fecha_cambio", "historial_etapa", ["fecha_cambio"]
    )

    op.create_table(
        "observacion_revision",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("historial_etapa_id", sa.Integer(), nullable=False),
        sa.Column("origen", sa.String(30), nullable=False),
        sa.Column("registrada_por_id", sa.Integer(), nullable=False),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("respuesta", sa.Text(), nullable=True),
        sa.Column("atendida_por_id", sa.Integer(), nullable=True),
        sa.Column("fecha_atencion", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "estado",
            sa.String(20),
            server_default="PENDIENTE",
            nullable=False,
        ),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "origen IN ('REVISOR_ORI', 'CONTRAPARTE', 'REVISION_FINAL_ORI')",
            name="ck_observacion_revision_origen",
        ),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE', 'ATENDIDA')",
            name="ck_observacion_revision_estado",
        ),
        sa.ForeignKeyConstraint(
            ["convenio_id"], ["convenio.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["historial_etapa_id"],
            ["historial_etapa.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["registrada_por_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["responsable_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["atendida_por_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_observacion_revision_convenio_id",
        "observacion_revision",
        ["convenio_id"],
    )
    op.create_index(
        "ix_observacion_revision_historial_etapa_id",
        "observacion_revision",
        ["historial_etapa_id"],
    )
    op.create_index(
        "ix_observacion_revision_estado", "observacion_revision", ["estado"]
    )


def downgrade() -> None:
    op.drop_table("observacion_revision")
    op.drop_table("historial_etapa")
