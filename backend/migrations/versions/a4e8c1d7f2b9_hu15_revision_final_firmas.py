"""HU-15 revisión final y ciclos de firmas.

Revision ID: a4e8c1d7f2b9
Revises: d9e1f3a5b7c2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4e8c1d7f2b9"
down_revision: str | Sequence[str] | None = "d9e1f3a5b7c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_revision_convenio_final_pendiente",
        "revision_convenio",
        ["convenio_id"],
        unique=True,
        postgresql_where=sa.text("tipo = 'FINAL' AND estado = 'PENDIENTE'"),
    )
    op.create_table(
        "proceso_firmas_convenio",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("version_convenio_id", sa.Integer(), nullable=False),
        sa.Column("revision_final_id", sa.Integer(), nullable=False),
        sa.Column("creado_por_id", sa.Integer(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            server_default="CONFIGURACION",
            nullable=False,
        ),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("iniciado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('CONFIGURACION', 'EN_CURSO', 'COMPLETADO', 'CANCELADO')",
            name="ck_proceso_firmas_convenio_estado",
        ),
        sa.ForeignKeyConstraint(
            ["convenio_id"], ["convenio.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["version_convenio_id"],
            ["version_convenio.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revision_final_id"],
            ["revision_convenio.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_final_id"),
    )
    op.create_index(
        "ix_proceso_firmas_convenio_convenio_id",
        "proceso_firmas_convenio",
        ["convenio_id"],
    )
    op.create_index(
        "ix_proceso_firmas_convenio_version_convenio_id",
        "proceso_firmas_convenio",
        ["version_convenio_id"],
    )
    op.create_index(
        "uq_proceso_firmas_convenio_activo",
        "proceso_firmas_convenio",
        ["convenio_id"],
        unique=True,
        postgresql_where=sa.text("estado IN ('CONFIGURACION', 'EN_CURSO')"),
    )
    op.create_table(
        "firma_convenio",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("proceso_firmas_id", sa.Integer(), nullable=False),
        sa.Column("orden", sa.SmallInteger(), nullable=False),
        sa.Column("rol_firmante", sa.String(length=40), nullable=False),
        sa.Column("parte", sa.String(length=40), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("nombre_firmante", sa.String(length=160), nullable=True),
        sa.Column("cargo_firmante", sa.String(length=160), nullable=True),
        sa.Column("correo_firmante", sa.String(length=320), nullable=True),
        sa.Column("modalidad", sa.String(length=20), nullable=True),
        sa.Column(
            "estado", sa.String(length=20), server_default="PENDIENTE", nullable=False
        ),
        sa.Column("fecha_firma", sa.DateTime(timezone=True), nullable=True),
        sa.Column("documento_id", sa.Integer(), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("orden BETWEEN 1 AND 7", name="ck_firma_convenio_orden"),
        sa.CheckConstraint(
            "rol_firmante IN ('ADMINISTRADOR_ORI', 'REVISOR_ORI', "
            "'VICERRECTORIA_FINANCIERA', 'VICERRECTORIA_ACADEMICA', "
            "'SECRETARIA', 'RECTOR', 'PARTE_SOLICITANTE')",
            name="ck_firma_convenio_rol",
        ),
        sa.CheckConstraint(
            "parte IN ('UNIVERSIDAD', 'UNIDAD_SOLICITANTE', "
            "'REPRESENTANTE_LEGAL_ENTIDAD')",
            name="ck_firma_convenio_parte",
        ),
        sa.CheckConstraint(
            "modalidad IS NULL OR modalidad IN ('ELECTRONICA', 'FISICA')",
            name="ck_firma_convenio_modalidad",
        ),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE', 'FIRMADA')",
            name="ck_firma_convenio_estado",
        ),
        sa.CheckConstraint(
            "modalidad <> 'ELECTRONICA' OR correo_firmante IS NOT NULL",
            name="ck_firma_convenio_electronica_correo",
        ),
        sa.ForeignKeyConstraint(
            ["proceso_firmas_id"],
            ["proceso_firmas_convenio.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["documento_id"], ["documento.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proceso_firmas_id", "orden", name="uq_firma_convenio_proceso_orden"
        ),
        sa.UniqueConstraint(
            "proceso_firmas_id",
            "rol_firmante",
            name="uq_firma_convenio_proceso_rol",
        ),
    )
    op.create_index(
        "ix_firma_convenio_proceso_firmas_id",
        "firma_convenio",
        ["proceso_firmas_id"],
    )
    op.create_index(
        "ix_firma_convenio_documento_id", "firma_convenio", ["documento_id"]
    )
    op.create_table(
        "invitacion_firma_convenio",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("firma_convenio_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enviado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("utilizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generada_por_id", sa.Integer(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["firma_convenio_id"], ["firma_convenio.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["generada_por_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_invitacion_firma_convenio_firma_convenio_id",
        "invitacion_firma_convenio",
        ["firma_convenio_id"],
    )
    op.create_index(
        "ix_invitacion_firma_convenio_generada_por_id",
        "invitacion_firma_convenio",
        ["generada_por_id"],
    )
    op.create_index(
        "uq_invitacion_firma_token_hash",
        "invitacion_firma_convenio",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "uq_invitacion_firma_activa",
        "invitacion_firma_convenio",
        ["firma_convenio_id"],
        unique=True,
        postgresql_where=sa.text("utilizado_en IS NULL AND revocado_en IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_invitacion_firma_activa", table_name="invitacion_firma_convenio"
    )
    op.drop_index(
        "uq_invitacion_firma_token_hash", table_name="invitacion_firma_convenio"
    )
    op.drop_index(
        "ix_invitacion_firma_convenio_generada_por_id",
        table_name="invitacion_firma_convenio",
    )
    op.drop_index(
        "ix_invitacion_firma_convenio_firma_convenio_id",
        table_name="invitacion_firma_convenio",
    )
    op.drop_table("invitacion_firma_convenio")
    op.drop_index("ix_firma_convenio_documento_id", table_name="firma_convenio")
    op.drop_index("ix_firma_convenio_proceso_firmas_id", table_name="firma_convenio")
    op.drop_table("firma_convenio")
    op.drop_index(
        "uq_proceso_firmas_convenio_activo",
        table_name="proceso_firmas_convenio",
    )
    op.drop_index(
        "ix_proceso_firmas_convenio_version_convenio_id",
        table_name="proceso_firmas_convenio",
    )
    op.drop_index(
        "ix_proceso_firmas_convenio_convenio_id",
        table_name="proceso_firmas_convenio",
    )
    op.drop_table("proceso_firmas_convenio")
    op.drop_index(
        "uq_revision_convenio_final_pendiente", table_name="revision_convenio"
    )
