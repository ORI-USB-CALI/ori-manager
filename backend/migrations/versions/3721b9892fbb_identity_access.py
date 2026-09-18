"""identity access

Revision ID: 3721b9892fbb
Revises: 56626120dc9a
Create Date: 2026-09-18 01:09:17.978393

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3721b9892fbb"
down_revision: str | Sequence[str] | None = "56626120dc9a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rol",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=40), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column(
            "es_interno",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "activo",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_table(
        "unidad_organizacional",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=40), nullable=False),
        sa.Column("nombre", sa.String(length=160), nullable=False),
        sa.Column("tipo", sa.String(length=21), nullable=False),
        sa.Column("unidad_padre_id", sa.Integer(), nullable=True),
        sa.Column(
            "activa",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('FACULTAD', 'PROGRAMA', 'UNIDAD_ADMINISTRATIVA')",
            name="ck_unidad_organizacional_tipo",
        ),
        sa.ForeignKeyConstraint(
            ["unidad_padre_id"],
            ["unidad_organizacional.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_table(
        "usuario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("correo", sa.String(length=160), nullable=False),
        sa.Column("hash_contrasena", sa.String(length=255), nullable=False),
        sa.Column("nombre_completo", sa.String(length=160), nullable=False),
        sa.Column("documento_identidad", sa.String(length=40), nullable=True),
        sa.Column("telefono", sa.String(length=40), nullable=True),
        sa.Column("cargo", sa.String(length=120), nullable=True),
        sa.Column("rol_id", sa.Integer(), nullable=False),
        sa.Column("tipo_usuario", sa.String(length=7), nullable=False),
        sa.Column("unidad_organizacional_id", sa.Integer(), nullable=True),
        sa.Column("entidad_externa", sa.String(length=160), nullable=True),
        sa.Column(
            "activo",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("ultimo_acceso", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo_usuario IN ('INTERNO', 'EXTERNO')",
            name="ck_usuario_tipo_usuario",
        ),
        sa.ForeignKeyConstraint(["rol_id"], ["rol.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["unidad_organizacional_id"],
            ["unidad_organizacional.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correo"),
    )

    rol = sa.table(
        "rol",
        sa.column("codigo", sa.String(length=40)),
        sa.column("nombre", sa.String(length=80)),
        sa.column("descripcion", sa.Text()),
        sa.column("es_interno", sa.Boolean()),
        sa.column("activo", sa.Boolean()),
    )
    op.bulk_insert(
        rol,
        [
            {
                "codigo": "ADMINISTRADOR_ORI",
                "nombre": "Administrador ORI",
                "descripcion": None,
                "es_interno": True,
                "activo": True,
            },
            {
                "codigo": "GESTOR_ORI",
                "nombre": "Gestor ORI",
                "descripcion": None,
                "es_interno": True,
                "activo": True,
            },
            {
                "codigo": "REVISOR_ORI",
                "nombre": "Revisor ORI",
                "descripcion": None,
                "es_interno": True,
                "activo": True,
            },
            {
                "codigo": "SOLICITANTE_INTERNO",
                "nombre": "Solicitante interno",
                "descripcion": None,
                "es_interno": True,
                "activo": True,
            },
            {
                "codigo": "SOLICITANTE_EXTERNO",
                "nombre": "Solicitante externo",
                "descripcion": None,
                "es_interno": False,
                "activo": True,
            },
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("usuario")
    op.drop_table("unidad_organizacional")
    op.drop_table("rol")
