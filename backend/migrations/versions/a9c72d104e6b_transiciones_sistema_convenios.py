"""Bitácora de transiciones automáticas de convenios.

Revision ID: a9c72d104e6b
Revises: f3a1c8e4d2b7
"""

import sqlalchemy as sa
from alembic import op

revision = "a9c72d104e6b"
down_revision = "f3a1c8e4d2b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transicion_estado_convenio",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(20), server_default="SISTEMA", nullable=False),
        sa.Column("estado_anterior", sa.String(20), nullable=False),
        sa.Column("estado_nuevo", sa.String(20), nullable=False),
        sa.Column("fecha_referencia", sa.Date(), nullable=False),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=False),
        sa.Column(
            "ejecutado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["convenio_id"], ["convenio.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("actor = 'SISTEMA'", name="ck_transicion_convenio_actor"),
        sa.CheckConstraint(
            "estado_anterior <> estado_nuevo", name="ck_transicion_convenio_cambio"
        ),
    )
    op.create_index(
        "ix_transicion_estado_convenio_convenio_id",
        "transicion_estado_convenio",
        ["convenio_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transicion_estado_convenio_convenio_id",
        table_name="transicion_estado_convenio",
    )
    op.drop_table("transicion_estado_convenio")
