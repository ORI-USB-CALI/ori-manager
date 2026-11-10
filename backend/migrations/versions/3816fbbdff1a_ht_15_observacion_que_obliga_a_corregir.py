from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3816fbbdff1a'
down_revision: str | Sequence[str] | None = '0b2fb1bed5b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Las observaciones existentes quedan como obligatorias (RN-09 de HT-15): no
    # se puede saber si sus correcciones eran necesarias, así que no se reutiliza.
    op.add_column(
        "observacion_revision",
        sa.Column(
            "requiere_correccion",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("observacion_revision", "requiere_correccion")
