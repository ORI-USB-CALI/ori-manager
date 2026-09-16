"""Add rol to users

Revision ID: b7e1c4a9d2f3
Revises: 2557d68c8bd6
Create Date: 2026-09-16 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7e1c4a9d2f3'
down_revision: str | Sequence[str] | None = '2557d68c8bd6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Usuarios existentes quedan con el rol de mínimo privilegio.
    op.add_column(
        'users',
        sa.Column('rol', sa.String(length=30), server_default='usuario_ori', nullable=False),
    )
    op.create_check_constraint(
        'ck_users_rol', 'users', "rol IN ('administrador', 'usuario_ori')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_users_rol', 'users', type_='check')
    op.drop_column('users', 'rol')
