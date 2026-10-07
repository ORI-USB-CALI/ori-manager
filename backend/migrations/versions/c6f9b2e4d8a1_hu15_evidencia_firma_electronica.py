"""HU-15 evidencia de firma electrónica.

Revision ID: c6f9b2e4d8a1
Revises: a4e8c1d7f2b9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6f9b2e4d8a1"
down_revision: str | Sequence[str] | None = "a4e8c1d7f2b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "firma_convenio", sa.Column("firma_png", sa.LargeBinary(), nullable=True)
    )
    op.add_column(
        "firma_convenio",
        sa.Column("firma_sha256", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_firma_convenio_evidencia_electronica_completa",
        "firma_convenio",
        "(firma_png IS NULL AND firma_sha256 IS NULL) OR "
        "(firma_png IS NOT NULL AND firma_sha256 IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_firma_convenio_evidencia_electronica_completa",
        "firma_convenio",
        type_="check",
    )
    op.drop_column("firma_convenio", "firma_sha256")
    op.drop_column("firma_convenio", "firma_png")
