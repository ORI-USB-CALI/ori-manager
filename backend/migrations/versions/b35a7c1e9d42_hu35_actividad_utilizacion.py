"""HU-35 registro de actividades de utilización del convenio.

Revision ID: b35a7c1e9d42
Revises: f3a1c8e4d2b7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b35a7c1e9d42"
down_revision: str | Sequence[str] | None = "f3a1c8e4d2b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "actividad_utilizacion",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("actividad", sa.String(length=200), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("responsable", sa.String(length=200), nullable=False),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("registrado_por_id", sa.Integer(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["convenio_id"], ["convenio.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["registrado_por_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_actividad_utilizacion_convenio_id"),
        "actividad_utilizacion",
        ["convenio_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_actividad_utilizacion_convenio_id"),
        table_name="actividad_utilizacion",
    )
    op.drop_table("actividad_utilizacion")
