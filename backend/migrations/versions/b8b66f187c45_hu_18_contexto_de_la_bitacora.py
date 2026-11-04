from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8b66f187c45"
down_revision: str | Sequence[str] | None = "b18a4d2c9e71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # RN-24: además del cambio de campo, cada registro puede describir la acción
    # de negocio que lo originó. Los registros anteriores quedan sin descripción.
    op.add_column("auditoria", sa.Column("contexto", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("auditoria", "contexto")
