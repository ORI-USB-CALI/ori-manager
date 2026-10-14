"""HT-02 relacionar devolucion con la version radicada

Revision ID: c02b7e4f1a95
Revises: 21fb929bf614
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c02b7e4f1a95"
down_revision: str | Sequence[str] | None = "21fb929bf614"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "solicitud_version",
        sa.Column("observaciones_devolucion", sa.Text(), nullable=True),
    )
    op.add_column(
        "solicitud_version", sa.Column("devuelta_por_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "solicitud_version",
        sa.Column("devuelta_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_solicitud_version_devuelta_por",
        "solicitud_version",
        "usuario",
        ["devuelta_por_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    # Coherencia: una devolución siempre tiene texto, responsable y fecha.
    op.create_check_constraint(
        "ck_solicitud_version_devolucion_completa",
        "solicitud_version",
        "(devuelta_en IS NULL AND devuelta_por_id IS NULL"
        " AND observaciones_devolucion IS NULL)"
        " OR (devuelta_en IS NOT NULL AND devuelta_por_id IS NOT NULL"
        " AND observaciones_devolucion IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_solicitud_version_devolucion_completa", "solicitud_version", type_="check"
    )
    op.drop_constraint(
        "fk_solicitud_version_devuelta_por", "solicitud_version", type_="foreignkey"
    )
    op.drop_column("solicitud_version", "devuelta_en")
    op.drop_column("solicitud_version", "devuelta_por_id")
    op.drop_column("solicitud_version", "observaciones_devolucion")
