"""HU-08 estado de verificación del correo.

Revision ID: b822d14c8a31
Revises: a711c4d8e912
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b822d14c8a31"
down_revision: str | Sequence[str] | None = "a711c4d8e912"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MARCAR_EXISTENTES_SQL = (
    "UPDATE usuario SET correo_verificado_en = now() WHERE correo_verificado_en IS NULL"
)


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column("correo_verificado_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text(MARCAR_EXISTENTES_SQL))


def downgrade() -> None:
    op.drop_column("usuario", "correo_verificado_en")
