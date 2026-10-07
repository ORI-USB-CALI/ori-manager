"""Crear foundation compartida de revisiones de convenio.

Revision ID: a6c4e2f8b1d9
Revises: e41c9a7b2d53
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6c4e2f8b1d9"
down_revision: str | Sequence[str] | None = "e41c9a7b2d53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revision_convenio",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("historial_etapa_id", sa.Integer(), nullable=True),
        sa.Column("documento_id", sa.Integer(), nullable=True),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column(
            "estado",
            sa.String(20),
            server_default="PENDIENTE",
            nullable=False,
        ),
        sa.Column("resultado", sa.String(20), nullable=True),
        sa.Column("resuelta_por_id", sa.Integer(), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resuelta_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('JURIDICA', 'CONTRAPARTE', 'FINAL')",
            name="ck_revision_convenio_tipo",
        ),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE', 'RESUELTA')",
            name="ck_revision_convenio_estado",
        ),
        sa.CheckConstraint(
            "resultado IS NULL OR resultado IN ('APROBADA', 'DEVUELTA')",
            name="ck_revision_convenio_resultado",
        ),
        sa.ForeignKeyConstraint(
            ["convenio_id"], ["convenio.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["historial_etapa_id"],
            ["historial_etapa.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["documento_id"], ["documento.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["responsable_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resuelta_por_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_revision_convenio_convenio_id",
        "revision_convenio",
        ["convenio_id"],
    )
    op.create_index(
        "ix_revision_convenio_documento_id",
        "revision_convenio",
        ["documento_id"],
    )

    op.add_column(
        "observacion_revision",
        sa.Column("revision_convenio_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_observacion_revision_revision_convenio_id",
        "observacion_revision",
        "revision_convenio",
        ["revision_convenio_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_observacion_revision_revision_convenio_id",
        "observacion_revision",
        ["revision_convenio_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_observacion_revision_revision_convenio_id",
        table_name="observacion_revision",
    )
    op.drop_constraint(
        "fk_observacion_revision_revision_convenio_id",
        "observacion_revision",
        type_="foreignkey",
    )
    op.drop_column("observacion_revision", "revision_convenio_id")

    op.drop_index(
        "ix_revision_convenio_documento_id", table_name="revision_convenio"
    )
    op.drop_index(
        "ix_revision_convenio_convenio_id", table_name="revision_convenio"
    )
    op.drop_table("revision_convenio")
