"""add unique constraint to convenios.codigo

Revision ID: c3d9f1a02b7e
Revises: a1b2c3d4e5f6
Create Date: 2026-09-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d9f1a02b7e"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_convenios_codigo", "convenios", ["codigo"])


def downgrade() -> None:
    op.drop_constraint("uq_convenios_codigo", "convenios", type_="unique")
