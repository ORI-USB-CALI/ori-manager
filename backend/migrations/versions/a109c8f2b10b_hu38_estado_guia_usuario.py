"""HU-38 estado de guías por usuario.

Revision ID: a109c8f2b10b
Revises: 2fa11b85762d
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a109c8f2b10b"
down_revision: str | Sequence[str] | None = "2fa11b85762d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Sin backfill: la ausencia de registro equivale a PENDIENTE (HU-38 RN-03).
    op.create_table(
        "estado_guia_usuario",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("guia", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "usuario_id", "guia", name="uq_estado_guia_usuario_usuario_guia"
        ),
        sa.CheckConstraint(
            "guia IN ('ONBOARDING_INICIAL', 'GUIA_RADICACION')",
            name="ck_estado_guia_usuario_guia",
        ),
        sa.CheckConstraint(
            "estado IN ('COMPLETADO', 'OMITIDO')",
            name="ck_estado_guia_usuario_estado",
        ),
        sa.CheckConstraint("version >= 1", name="ck_estado_guia_usuario_version"),
    )
    op.create_index(
        "ix_estado_guia_usuario_usuario_id", "estado_guia_usuario", ["usuario_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_estado_guia_usuario_usuario_id", table_name="estado_guia_usuario")
    op.drop_table("estado_guia_usuario")
