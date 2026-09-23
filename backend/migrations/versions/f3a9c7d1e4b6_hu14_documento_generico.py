"""Generalizar documento_solicitud a documento (alineado al MER).

Revision ID: f3a9c7d1e4b6
Revises: d4a8f6c1b2e5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a9c7d1e4b6"
down_revision: str | Sequence[str] | None = "d4a8f6c1b2e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIPOS = (
    "CAMARA_COMERCIO",
    "RUT",
    "CEDULA_REPRESENTANTE_LEGAL",
    "OTRO_DOCUMENTO_REPRESENTACION",
    "OTRO_SOPORTE",
    "BORRADOR",
    "AVAL_JURIDICO",
    "CONVENIO_FIRMADO",
    "OTROSI",
    "ACTA_TERMINACION",
)


def upgrade() -> None:
    op.rename_table("documento_solicitud", "documento")
    op.alter_column("documento", "tipo_documento", new_column_name="tipo")
    op.alter_column("documento", "nombre_original", new_column_name="nombre_archivo")
    op.alter_column("documento", "clave_objeto", new_column_name="ruta_almacenamiento")
    op.alter_column("documento", "solicitud_id", nullable=True)

    op.add_column("documento", sa.Column("convenio_id", sa.Integer(), nullable=True))
    op.add_column("documento", sa.Column("version", sa.SmallInteger(), nullable=True))
    op.add_column(
        "documento",
        sa.Column("es_vigente", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column("documento", sa.Column("cargado_por_id", sa.Integer(), nullable=True))

    op.create_foreign_key(
        "fk_documento_convenio_id", "documento", "convenio", ["convenio_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_documento_cargado_por_id", "documento", "usuario", ["cargado_por_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_documento_convenio_id", "documento", ["convenio_id"])

    op.execute("ALTER TABLE documento RENAME CONSTRAINT ck_documento_solicitud_tamano TO ck_documento_tamano")
    op.drop_constraint("ck_documento_solicitud_tipo", "documento", type_="check")
    op.create_check_constraint(
        "ck_documento_tipo",
        "documento",
        "tipo IN (" + ", ".join(f"'{valor}'" for valor in _TIPOS) + ")",
    )
    op.create_check_constraint(
        "ck_documento_solicitud_o_convenio",
        "documento",
        "solicitud_id IS NOT NULL OR convenio_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documento_solicitud_o_convenio", "documento", type_="check")
    op.drop_constraint("ck_documento_tipo", "documento", type_="check")
    op.create_check_constraint(
        "ck_documento_solicitud_tipo",
        "documento",
        "tipo IN ('CAMARA_COMERCIO', 'RUT', 'CEDULA_REPRESENTANTE_LEGAL', "
        "'OTRO_DOCUMENTO_REPRESENTACION', 'OTRO_SOPORTE')",
    )
    op.execute("ALTER TABLE documento RENAME CONSTRAINT ck_documento_tamano TO ck_documento_solicitud_tamano")

    op.drop_index("ix_documento_convenio_id", table_name="documento")
    op.drop_constraint("fk_documento_cargado_por_id", "documento", type_="foreignkey")
    op.drop_constraint("fk_documento_convenio_id", "documento", type_="foreignkey")

    op.drop_column("documento", "cargado_por_id")
    op.drop_column("documento", "es_vigente")
    op.drop_column("documento", "version")
    op.drop_column("documento", "convenio_id")

    op.alter_column("documento", "solicitud_id", nullable=False)
    op.alter_column("documento", "ruta_almacenamiento", new_column_name="clave_objeto")
    op.alter_column("documento", "nombre_archivo", new_column_name="nombre_original")
    op.alter_column("documento", "tipo", new_column_name="tipo_documento")
    op.rename_table("documento", "documento_solicitud")
