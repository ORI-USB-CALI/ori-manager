"""HU-31 decisión de no renovación e intento activo único.

Revision ID: f3a1c8e4d2b7
Revises: 68abde7e23b2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a1c8e4d2b7"
down_revision: str | Sequence[str] | None = "68abde7e23b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_no_renovacion",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("fecha_vencimiento_origen", sa.Date(), nullable=False),
        sa.Column("decidida_por_id", sa.Integer(), nullable=False),
        sa.Column(
            "decidida_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["convenio_id"], ["convenio.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["decidida_por_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "convenio_id",
            "fecha_vencimiento_origen",
            name="uq_decision_no_renovacion_convenio_periodo",
        ),
    )
    op.create_index(
        "uq_convenio_origen_renovacion_activa",
        "convenio",
        ["convenio_origen_id"],
        unique=True,
        postgresql_where=sa.text(
            "convenio_origen_id IS NOT NULL AND estado = 'EN_TRAMITE'"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_convenio_origen_renovacion_activa", table_name="convenio")
    op.drop_table("decision_no_renovacion")
