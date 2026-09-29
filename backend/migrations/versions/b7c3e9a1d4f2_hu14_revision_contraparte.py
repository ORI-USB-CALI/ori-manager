"""HU-14 revisión de contraparte.

Revision ID: b7c3e9a1d4f2
Revises: 9d4e7a1c2b63
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c3e9a1d4f2"
down_revision: str | Sequence[str] | None = "9d4e7a1c2b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "revision_convenio",
        sa.Column("creada_por_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_revision_convenio_creada_por_id",
        "revision_convenio",
        "usuario",
        ["creada_por_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_revision_convenio_creada_por_id",
        "revision_convenio",
        ["creada_por_id"],
    )
    op.create_index(
        "uq_revision_convenio_contraparte_pendiente",
        "revision_convenio",
        ["convenio_id"],
        unique=True,
        postgresql_where=sa.text(
            "tipo = 'CONTRAPARTE' AND estado = 'PENDIENTE'"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_revision_convenio_contraparte_pendiente",
        table_name="revision_convenio",
    )
    op.drop_index(
        "ix_revision_convenio_creada_por_id",
        table_name="revision_convenio",
    )
    op.drop_constraint(
        "fk_revision_convenio_creada_por_id",
        "revision_convenio",
        type_="foreignkey",
    )
    op.drop_column("revision_convenio", "creada_por_id")
