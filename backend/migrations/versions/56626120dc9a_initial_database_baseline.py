"""initial database baseline

Revision ID: 56626120dc9a
Revises: 
Create Date: 2026-09-10 16:35:14.559785

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '56626120dc9a'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
