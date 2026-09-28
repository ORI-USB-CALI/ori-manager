"""HU-14 revisión externa de contraparte.

Revision ID: c5a8e2f1d7b4
Revises: b7c3e9a1d4f2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5a8e2f1d7b4"
down_revision: str | Sequence[str] | None = "b7c3e9a1d4f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "observacion_revision",
        "registrada_por_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_table(
        "invitacion_revision_contraparte",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("revision_convenio_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("correo_destino", sa.String(length=320), nullable=False),
        sa.Column("correo_cc", sa.String(length=320), nullable=True),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enviado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("utilizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["revision_convenio_id"],
            ["revision_convenio.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_invitacion_revision_contraparte_revision_convenio_id",
        "invitacion_revision_contraparte",
        ["revision_convenio_id"],
    )
    op.create_index(
        "uq_invitacion_contraparte_token_hash",
        "invitacion_revision_contraparte",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "uq_invitacion_contraparte_activa",
        "invitacion_revision_contraparte",
        ["revision_convenio_id"],
        unique=True,
        postgresql_where=sa.text(
            "utilizado_en IS NULL AND revocado_en IS NULL"
        ),
    )
    op.create_table(
        "respuesta_revision_contraparte",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("revision_convenio_id", sa.Integer(), nullable=False),
        sa.Column("nombre_firmante", sa.String(length=160), nullable=False),
        sa.Column("cargo_firmante", sa.String(length=160), nullable=False),
        sa.Column("correo_actor", sa.String(length=320), nullable=False),
        sa.Column("firma_png", sa.LargeBinary(), nullable=True),
        sa.Column("firma_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["revision_convenio_id"],
            ["revision_convenio.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_convenio_id"),
    )


def downgrade() -> None:
    op.drop_table("respuesta_revision_contraparte")
    op.drop_index(
        "uq_invitacion_contraparte_activa",
        table_name="invitacion_revision_contraparte",
    )
    op.drop_index(
        "uq_invitacion_contraparte_token_hash",
        table_name="invitacion_revision_contraparte",
    )
    op.drop_index(
        "ix_invitacion_revision_contraparte_revision_convenio_id",
        table_name="invitacion_revision_contraparte",
    )
    op.drop_table("invitacion_revision_contraparte")
    op.alter_column(
        "observacion_revision",
        "registrada_por_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
