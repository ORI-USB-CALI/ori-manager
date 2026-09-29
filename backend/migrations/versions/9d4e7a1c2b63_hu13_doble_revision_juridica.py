"""HU-13 doble revisión jurídica.

Revision ID: 9d4e7a1c2b63
Revises: 7f2a4c9d1e30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d4e7a1c2b63"
down_revision: str | Sequence[str] | None = "7f2a4c9d1e30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "revision_convenio",
        sa.Column("instancia_juridica", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "revision_convenio",
        sa.Column("numero_ronda", sa.Integer(), nullable=True),
    )
    op.add_column(
        "revision_convenio",
        sa.Column("version_resultado_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_revision_convenio_version_resultado_id",
        "revision_convenio",
        "version_convenio",
        ["version_resultado_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_revision_convenio_instancia_juridica",
        "revision_convenio",
        "instancia_juridica IS NULL OR instancia_juridica IN (1, 2)",
    )
    op.create_check_constraint(
        "ck_revision_convenio_numero_ronda_positivo",
        "revision_convenio",
        "numero_ronda IS NULL OR numero_ronda > 0",
    )
    op.create_check_constraint(
        "ck_revision_convenio_coordenadas_juridicas",
        "revision_convenio",
        "(instancia_juridica IS NULL) = (numero_ronda IS NULL)",
    )
    op.create_unique_constraint(
        "uq_revision_convenio_ronda_instancia",
        "revision_convenio",
        ["convenio_id", "tipo", "numero_ronda", "instancia_juridica"],
    )
    op.create_index(
        "ix_revision_convenio_version_resultado_id",
        "revision_convenio",
        ["version_resultado_id"],
    )
    op.create_index(
        "uq_revision_convenio_juridica_pendiente",
        "revision_convenio",
        ["convenio_id"],
        unique=True,
        postgresql_where=sa.text("tipo = 'JURIDICA' AND estado = 'PENDIENTE'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_revision_convenio_juridica_pendiente",
        table_name="revision_convenio",
    )
    op.drop_index(
        "ix_revision_convenio_version_resultado_id",
        table_name="revision_convenio",
    )
    op.drop_constraint(
        "uq_revision_convenio_ronda_instancia",
        "revision_convenio",
        type_="unique",
    )
    op.drop_constraint(
        "ck_revision_convenio_coordenadas_juridicas",
        "revision_convenio",
        type_="check",
    )
    op.drop_constraint(
        "ck_revision_convenio_numero_ronda_positivo",
        "revision_convenio",
        type_="check",
    )
    op.drop_constraint(
        "ck_revision_convenio_instancia_juridica",
        "revision_convenio",
        type_="check",
    )
    op.drop_constraint(
        "fk_revision_convenio_version_resultado_id",
        "revision_convenio",
        type_="foreignkey",
    )
    op.drop_column("revision_convenio", "version_resultado_id")
    op.drop_column("revision_convenio", "numero_ronda")
    op.drop_column("revision_convenio", "instancia_juridica")
