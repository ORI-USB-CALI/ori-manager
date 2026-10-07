"""Generalizar documento_solicitud al modelo documento del MER.

Revision ID: d8f4b2a1c6e7
Revises: c91e4a7d2b60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f4b2a1c6e7"
down_revision: str | Sequence[str] | None = "c91e4a7d2b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIPOS_HU11 = (
    "CAMARA_COMERCIO",
    "RUT",
    "CEDULA_REPRESENTANTE_LEGAL",
    "OTRO_DOCUMENTO_REPRESENTACION",
    "OTRO_SOPORTE",
)
_TIPOS_MER = (
    "FORMATO_SOLICITUD",
    "CAMARA_COMERCIO",
    "RUT",
    "CEDULA_REPRESENTANTE",
    "BORRADOR",
    "AVAL_JURIDICO",
    "CONVENIO_FIRMADO",
    "OTROSI",
    "ACTA_TERMINACION",
    "SOPORTE",
)
_TIPOS_COMPATIBLES = tuple(dict.fromkeys((*_TIPOS_HU11, *_TIPOS_MER)))


def _lista_sql(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


def upgrade() -> None:
    op.rename_table("documento_solicitud", "documento")
    op.execute(
        "ALTER SEQUENCE documento_solicitud_id_seq RENAME TO documento_id_seq"
    )
    op.alter_column("documento", "tipo_documento", new_column_name="tipo")
    op.alter_column("documento", "nombre_original", new_column_name="nombre_archivo")
    op.alter_column("documento", "clave_objeto", new_column_name="ruta_almacenamiento")

    op.alter_column(
        "documento",
        "ruta_almacenamiento",
        existing_type=sa.String(255),
        type_=sa.String(500),
        existing_nullable=False,
    )
    op.alter_column(
        "documento",
        "tipo_mime",
        existing_type=sa.String(100),
        type_=sa.String(120),
        existing_nullable=False,
    )
    op.alter_column(
        "documento",
        "tamano_bytes",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )
    op.alter_column(
        "documento",
        "solicitud_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    op.add_column("documento", sa.Column("convenio_id", sa.Integer(), nullable=True))
    op.add_column("documento", sa.Column("version", sa.SmallInteger(), nullable=True))
    op.add_column(
        "documento",
        sa.Column(
            "es_vigente",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.add_column("documento", sa.Column("cargado_por_id", sa.Integer(), nullable=True))

    op.create_foreign_key(
        "fk_documento_convenio_id",
        "documento",
        "convenio",
        ["convenio_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_documento_cargado_por_id",
        "documento",
        "usuario",
        ["cargado_por_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_documento_convenio_id", "documento", ["convenio_id"])

    op.execute(
        "ALTER INDEX ix_documento_solicitud_solicitud_id "
        "RENAME TO ix_documento_solicitud_id"
    )
    op.execute(
        "ALTER TABLE documento RENAME CONSTRAINT "
        "ck_documento_solicitud_tamano TO ck_documento_tamano"
    )
    op.drop_constraint("ck_documento_solicitud_tipo", "documento", type_="check")
    op.create_check_constraint(
        "ck_documento_tipo",
        "documento",
        f"tipo IN ({_lista_sql(_TIPOS_COMPATIBLES)})",
    )
    op.create_check_constraint(
        "ck_documento_solicitud_o_convenio",
        "documento",
        "solicitud_id IS NOT NULL OR convenio_id IS NOT NULL",
    )


def downgrade() -> None:
    conexion = op.get_bind()
    documento_incompatible = conexion.execute(
        sa.text(
            "SELECT id FROM documento "
            "WHERE solicitud_id IS NULL "
            "OR convenio_id IS NOT NULL "
            "OR tipo NOT IN "
            f"({_lista_sql(_TIPOS_HU11)}) LIMIT 1"
        )
    ).scalar_one_or_none()
    if documento_incompatible is not None:
        raise RuntimeError(
            "No se puede restaurar documento_solicitud: existe un documento "
            "sin solicitud o con un tipo no soportado por HU-11"
        )
    valor_fuera_de_rango = conexion.execute(
        sa.text(
            "SELECT id FROM documento "
            "WHERE char_length(ruta_almacenamiento) > 255 "
            "OR char_length(tipo_mime) > 100 "
            "OR tamano_bytes > 2147483647 LIMIT 1"
        )
    ).scalar_one_or_none()
    if valor_fuera_de_rango is not None:
        raise RuntimeError(
            "No se puede restaurar documento_solicitud: existe un valor que "
            "excede los límites del esquema HU-11"
        )

    op.drop_constraint("ck_documento_solicitud_o_convenio", "documento", type_="check")
    op.drop_constraint("ck_documento_tipo", "documento", type_="check")
    op.create_check_constraint(
        "ck_documento_solicitud_tipo",
        "documento",
        f"tipo IN ({_lista_sql(_TIPOS_HU11)})",
    )
    op.execute(
        "ALTER TABLE documento RENAME CONSTRAINT "
        "ck_documento_tamano TO ck_documento_solicitud_tamano"
    )
    op.execute(
        "ALTER INDEX ix_documento_solicitud_id "
        "RENAME TO ix_documento_solicitud_solicitud_id"
    )

    op.drop_index("ix_documento_convenio_id", table_name="documento")
    op.drop_constraint("fk_documento_cargado_por_id", "documento", type_="foreignkey")
    op.drop_constraint("fk_documento_convenio_id", "documento", type_="foreignkey")
    op.drop_column("documento", "cargado_por_id")
    op.drop_column("documento", "es_vigente")
    op.drop_column("documento", "version")
    op.drop_column("documento", "convenio_id")

    op.alter_column(
        "documento",
        "solicitud_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "documento",
        "tamano_bytes",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "documento",
        "tipo_mime",
        existing_type=sa.String(120),
        type_=sa.String(100),
        existing_nullable=False,
    )
    op.alter_column(
        "documento",
        "ruta_almacenamiento",
        existing_type=sa.String(500),
        type_=sa.String(255),
        existing_nullable=False,
    )
    op.alter_column("documento", "ruta_almacenamiento", new_column_name="clave_objeto")
    op.alter_column("documento", "nombre_archivo", new_column_name="nombre_original")
    op.alter_column("documento", "tipo", new_column_name="tipo_documento")
    op.rename_table("documento", "documento_solicitud")
    op.execute(
        "ALTER SEQUENCE documento_id_seq RENAME TO documento_solicitud_id_seq"
    )
