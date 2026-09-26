"""HU-07 decision de solicitud

Revision ID: 6c2cc29471c1
Revises: 3c946dc86ec5
Create Date: 2026-09-26 10:17:35.736162

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6c2cc29471c1'
down_revision: str | Sequence[str] | None = '3c946dc86ec5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "solicitud_convenio",
        sa.Column("decidida_por_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "solicitud_convenio",
        sa.Column("fecha_decision", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_solicitud_convenio_decidida_por",
        "solicitud_convenio",
        "usuario",
        ["decidida_por_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_solicitud_convenio_decidida_por", "solicitud_convenio", type_="foreignkey"
    )
    op.drop_column("solicitud_convenio", "fecha_decision")
    op.drop_column("solicitud_convenio", "decidida_por_id")
