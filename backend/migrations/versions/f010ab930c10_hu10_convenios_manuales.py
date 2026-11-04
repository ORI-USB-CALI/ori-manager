"""HU-10 convenios de creación directa ORI.

Revision ID: f010ab930c10
Revises: 2b123412a774
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f010ab930c10"
down_revision: str | Sequence[str] | None = "2b123412a774"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("convenio", sa.Column(
        "origen", sa.String(length=20), nullable=False,
        server_default="SOLICITUD",
    ))
    op.alter_column("convenio", "solicitud_id", existing_type=sa.Integer(), nullable=True)
    op.create_check_constraint(
        "ck_convenio_origen", "convenio",
        "origen IN ('SOLICITUD', 'MANUAL_ORI')",
    )
    op.create_check_constraint(
        "ck_convenio_origen_solicitud", "convenio",
        "(origen = 'SOLICITUD' AND solicitud_id IS NOT NULL) OR "
        "(origen = 'MANUAL_ORI' AND solicitud_id IS NULL)",
    )


def downgrade() -> None:
    manuales = op.get_bind().execute(sa.text(
        "SELECT COUNT(*) FROM convenio WHERE solicitud_id IS NULL"
    )).scalar_one()
    if manuales:
        raise RuntimeError("Hay convenios manuales; no se puede revertir sin perder información")
    op.drop_constraint("ck_convenio_origen_solicitud", "convenio", type_="check")
    op.drop_constraint("ck_convenio_origen", "convenio", type_="check")
    op.alter_column("convenio", "solicitud_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("convenio", "origen")
