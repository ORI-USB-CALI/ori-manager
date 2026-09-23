"""HU-14 revision pendiente para el solicitante/gestor.

Revision ID: d4a8f6c1b2e5
Revises: b6f2a1e7c9d3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a8f6c1b2e5"
down_revision: str | Sequence[str] | None = "b6f2a1e7c9d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revision_pendiente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("historial_etapa_id", sa.Integer(), nullable=False),
        sa.Column("responsable_id", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default=sa.text("'PENDIENTE'"), nullable=False),
        sa.Column("resultado", sa.String(length=20), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resuelta_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE', 'RESUELTA')",
            name="ck_revision_pendiente_estado",
        ),
        sa.CheckConstraint(
            "resultado IS NULL OR resultado IN ('APROBADA', 'DEVUELTA')",
            name="ck_revision_pendiente_resultado",
        ),
        sa.ForeignKeyConstraint(["convenio_id"], ["convenio.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["historial_etapa_id"], ["historial_etapa.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responsable_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_revision_pendiente_convenio_id", "revision_pendiente", ["convenio_id"], unique=False
    )
    op.create_index(
        "ix_revision_pendiente_responsable_id", "revision_pendiente", ["responsable_id"], unique=False
    )
    op.create_index(
        "ix_revision_pendiente_responsable_estado",
        "revision_pendiente",
        ["responsable_id", "estado"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("revision_pendiente")
