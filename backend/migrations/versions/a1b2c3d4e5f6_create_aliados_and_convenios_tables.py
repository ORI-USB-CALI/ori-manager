"""create aliados and convenios tables

Revision ID: a1b2c3d4e5f6
Revises: 56626120dc9a
Create Date: 2026-09-13 23:15:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "56626120dc9a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aliados",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("nit_o_identificacion", sa.String(length=100), nullable=True),
        sa.Column("tipo_aliado", sa.String(length=100), nullable=True),
        sa.Column("estado", sa.String(length=50), nullable=False, server_default="ACTIVO"),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "convenios",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("aliado_id", sa.UUID(as_uuid=True), sa.ForeignKey("aliados.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo", sa.String(length=100), nullable=False),
        sa.Column("titulo", sa.String(length=255), nullable=False),
        sa.Column("tipo_convenio", sa.String(length=100), nullable=True),
        sa.Column("estado", sa.String(length=50), nullable=False, server_default="VIGENTE"),
        sa.Column("fecha_inicio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fecha_fin", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_convenios_aliado_id", "convenios", ["aliado_id"])


def downgrade() -> None:
    op.drop_index("ix_convenios_aliado_id", table_name="convenios")
    op.drop_table("convenios")
    op.drop_table("aliados")
