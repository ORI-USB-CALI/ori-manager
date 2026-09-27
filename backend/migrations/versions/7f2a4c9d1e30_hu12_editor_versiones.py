"""HU-12 plantilla, editor y versiones inmutables.

Revision ID: 7f2a4c9d1e30
Revises: 3c946dc86ec5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7f2a4c9d1e30"
down_revision: str | Sequence[str] | None = "3c946dc86ec5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PLANTILLA_BASE = {
    "type": "doc",
    "content": [
        {
            "type": "heading",
            "attrs": {"level": 1},
            "content": [{"type": "text", "text": "PROYECTO DE CONVENIO"}],
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Solicitud de origen: {{solicitud.consecutivo}}",
                }
            ],
        },
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Información de origen"}],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Solicitante: {{solicitud.solicitante}}"}
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Contraparte propuesta: {{solicitud.contraparte}}",
                }
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Contacto de contraparte: {{solicitud.contacto_contraparte}}",
                }
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Tipo de convenio: {{solicitud.tipo_convenio}}",
                }
            ],
        },
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Justificación"}],
        },
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "{{solicitud.justificacion}}"}],
        },
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Objeto propuesto"}],
        },
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "{{solicitud.objeto}}"}],
        },
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Actividades"}],
        },
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "{{solicitud.actividades}}"}],
        },
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Metas"}],
        },
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "{{solicitud.metas}}"}],
        },
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Implicación financiera"}],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "{{solicitud.implicacion_financiera}}"}
            ],
        },
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Vigencia y renovación"}],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Vigencia estimada: {{solicitud.vigencia}}"}
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Renovación: {{solicitud.renovacion}}"}
            ],
        },
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Supervisión propuesta"}],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Supervisor USB: {{solicitud.supervisor_usb}}"}
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Supervisor de contraparte: {{solicitud.supervisor_contraparte}}",
                }
            ],
        },
    ],
}


def upgrade() -> None:
    op.create_table(
        "plantilla_convenio",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=60), nullable=False),
        sa.Column("nombre", sa.String(length=160), nullable=False),
        sa.Column(
            "contenido_base", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("activa", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("creado_por_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["creado_por_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_index("ix_plantilla_convenio_activa", "plantilla_convenio", ["activa"])
    plantilla = sa.table(
        "plantilla_convenio",
        sa.column("codigo", sa.String()),
        sa.column("nombre", sa.String()),
        sa.column("contenido_base", postgresql.JSONB()),
        sa.column("activa", sa.Boolean()),
    )
    op.bulk_insert(
        plantilla,
        [
            {
                "codigo": "BASE_HU12",
                "nombre": "Plantilla base de proyecto de convenio",
                "contenido_base": PLANTILLA_BASE,
                "activa": True,
            }
        ],
    )

    op.add_column(
        "convenio", sa.Column("plantilla_origen_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "convenio",
        sa.Column("version_actual", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_foreign_key(
        "fk_convenio_plantilla_origen_id",
        "convenio",
        "plantilla_convenio",
        ["plantilla_origen_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_convenio_version_actual_no_negativa", "convenio", "version_actual >= 0"
    )

    op.create_table(
        "version_convenio",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("contenido", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "snapshot_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("autor_id", sa.Integer(), nullable=False),
        sa.Column("etapa_id", sa.Integer(), nullable=False),
        sa.Column("contexto", sa.String(length=30), nullable=False),
        sa.Column("plantilla_id", sa.Integer(), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("numero > 0", name="ck_version_convenio_numero_positivo"),
        sa.CheckConstraint(
            "contexto IN ('INICIALIZACION', 'GUARDADO', 'FINALIZACION', 'CORRECCION_REVISION')",
            name="ck_version_convenio_contexto",
        ),
        sa.ForeignKeyConstraint(["autor_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["convenio_id"], ["convenio.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["etapa_id"], ["etapa.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["plantilla_id"], ["plantilla_convenio.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("convenio_id", "numero", name="uq_version_convenio_numero"),
    )
    op.create_index(
        "ix_version_convenio_convenio_id", "version_convenio", ["convenio_id"]
    )
    op.create_index("ix_version_convenio_creado_en", "version_convenio", ["creado_en"])

    op.add_column(
        "revision_convenio",
        sa.Column("version_convenio_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_revision_convenio_version_convenio_id",
        "revision_convenio",
        "version_convenio",
        ["version_convenio_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_revision_convenio_version_convenio_id",
        "revision_convenio",
        ["version_convenio_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_revision_convenio_version_convenio_id", table_name="revision_convenio"
    )
    op.drop_constraint(
        "fk_revision_convenio_version_convenio_id",
        "revision_convenio",
        type_="foreignkey",
    )
    op.drop_column("revision_convenio", "version_convenio_id")
    op.drop_index("ix_version_convenio_creado_en", table_name="version_convenio")
    op.drop_index("ix_version_convenio_convenio_id", table_name="version_convenio")
    op.drop_table("version_convenio")
    op.drop_constraint(
        "ck_convenio_version_actual_no_negativa", "convenio", type_="check"
    )
    op.drop_constraint(
        "fk_convenio_plantilla_origen_id", "convenio", type_="foreignkey"
    )
    op.drop_column("convenio", "version_actual")
    op.drop_column("convenio", "plantilla_origen_id")
    op.drop_index("ix_plantilla_convenio_activa", table_name="plantilla_convenio")
    op.drop_table("plantilla_convenio")
