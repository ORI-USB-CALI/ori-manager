"""HU-08 tokens de verificación de correo.

Revision ID: c91e4a7d2b60
Revises: b822d14c8a31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c91e4a7d2b60"
down_revision: str | Sequence[str] | None = "b822d14c8a31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "token_credencial",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("utilizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_token_credencial_token_hash",
        "token_credencial",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_token_credencial_usuario_id",
        "token_credencial",
        ["usuario_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_token_credencial_usuario_id", table_name="token_credencial")
    op.drop_index("ix_token_credencial_token_hash", table_name="token_credencial")
    op.drop_table("token_credencial")
