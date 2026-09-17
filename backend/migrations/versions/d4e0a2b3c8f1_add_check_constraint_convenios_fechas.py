"""add check constraint for convenios fecha_inicio <= fecha_fin

Revision ID: d4e0a2b3c8f1
Revises: c3d9f1a02b7e
Create Date: 2026-09-17 00:10:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e0a2b3c8f1"
down_revision: str | Sequence[str] | None = "c3d9f1a02b7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_convenios_fecha_inicio_fecha_fin",
        "convenios",
        "fecha_inicio IS NULL OR fecha_fin IS NULL OR fecha_inicio <= fecha_fin",
    )


def downgrade() -> None:
    op.drop_constraint("ck_convenios_fecha_inicio_fecha_fin", "convenios", type_="check")
