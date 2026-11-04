"""HU-27 indices para filtros de fecha

Revision ID: b337c7245190
Revises: a2b6f4d9c1e8
Create Date: 2026-10-12 06:36:18.010553

"""
from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b337c7245190'
down_revision: str | Sequence[str] | None = 'a2b6f4d9c1e8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_convenio_fecha_firma', 'convenio', ['fecha_firma'], unique=False)
    op.create_index('ix_convenio_vigencia', 'convenio', ['fecha_inicio', 'fecha_vencimiento'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_convenio_vigencia', table_name='convenio')
    op.drop_index('ix_convenio_fecha_firma', table_name='convenio')
