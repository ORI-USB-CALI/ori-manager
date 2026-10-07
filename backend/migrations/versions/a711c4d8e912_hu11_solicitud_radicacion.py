"""HU-11 solicitud inicial y documentos.

Revision ID: a711c4d8e912
Revises: f10409b2c3d4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a711c4d8e912"
down_revision: str | Sequence[str] | None = "f10409b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEMILLA_DESCRIPCION = "Semilla catálogo oficial HU-11"
SEMILLA_TIPOS_SQL = """
    INSERT INTO tipo_convenio
        (codigo, nombre, naturaleza, descripcion, activo)
    VALUES
        ('MARCO', 'Marco', 'MARCO', :descripcion, true),
        ('ESPECIFICO', 'Específico', 'ESPECIFICO', :descripcion, true),
        ('PRACTICA_INTERNACIONAL', 'Práctica internacional', NULL, :descripcion, true),
        ('INVESTIGACION', 'Investigación', NULL, :descripcion, true),
        ('PLAN_BENEFICIOS', 'Plan de beneficios', NULL, :descripcion, true),
        ('OTRO', 'Otro', NULL, :descripcion, true)
    ON CONFLICT (codigo) DO NOTHING
"""


def upgrade() -> None:
    op.alter_column(
        "tipo_convenio",
        "naturaleza",
        existing_type=sa.String(10),
        nullable=True,
    )
    op.execute(sa.text(SEMILLA_TIPOS_SQL).bindparams(descripcion=SEMILLA_DESCRIPCION))
    op.alter_column(
        "solicitud_convenio", "objeto", existing_type=sa.Text(), nullable=True
    )
    for nombre, tipo in (
        ("contacto_contraparte_nombre", sa.String(160)),
        ("contacto_contraparte_cargo", sa.String(120)),
        ("contacto_contraparte_telefono", sa.String(40)),
        ("contacto_contraparte_correo", sa.String(160)),
        ("pais_aliado_propuesto", sa.String(80)),
        ("ciudad_aliado_propuesto", sa.String(120)),
        ("telefono_aliado_propuesto", sa.String(40)),
        ("direccion_aliado_propuesto", sa.String(200)),
        ("supervisor_usb_nombre", sa.String(160)),
        ("supervisor_usb_cargo", sa.String(120)),
        ("supervisor_usb_telefono", sa.String(40)),
        ("supervisor_usb_correo", sa.String(160)),
        ("supervisor_contraparte_nombre", sa.String(160)),
        ("supervisor_contraparte_cargo", sa.String(120)),
        ("supervisor_contraparte_telefono", sa.String(40)),
        ("supervisor_contraparte_correo", sa.String(160)),
        ("solicitante_nombre", sa.String(160)),
        ("solicitante_correo", sa.String(160)),
        ("solicitante_documento", sa.String(40)),
        ("solicitante_cargo", sa.String(120)),
        ("solicitante_entidad", sa.String(160)),
        ("solicitante_unidad", sa.String(160)),
        ("solicitante_programa", sa.String(160)),
    ):
        op.add_column("solicitud_convenio", sa.Column(nombre, tipo, nullable=True))

    op.create_index(
        "ix_solicitud_convenio_solicitante_estado",
        "solicitud_convenio",
        ["solicitante_id", "estado"],
    )
    op.create_table(
        "documento_solicitud",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("tipo_documento", sa.String(40), nullable=False),
        sa.Column("nombre_original", sa.String(255), nullable=False),
        sa.Column("tipo_mime", sa.String(100), nullable=False),
        sa.Column("tamano_bytes", sa.Integer(), nullable=False),
        sa.Column("clave_objeto", sa.String(255), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("tamano_bytes > 0", name="ck_documento_solicitud_tamano"),
        sa.CheckConstraint(
            "tipo_documento IN ('CAMARA_COMERCIO', 'RUT', "
            "'CEDULA_REPRESENTANTE_LEGAL', 'OTRO_DOCUMENTO_REPRESENTACION', "
            "'OTRO_SOPORTE')",
            name="ck_documento_solicitud_tipo",
        ),
        sa.ForeignKeyConstraint(
            ["solicitud_id"], ["solicitud_convenio.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clave_objeto"),
    )
    op.create_index(
        "ix_documento_solicitud_solicitud_id",
        "documento_solicitud",
        ["solicitud_id"],
    )
    op.create_table(
        "solicitud_usuario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["solicitud_id"], ["solicitud_convenio.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("solicitud_id", "usuario_id", name="uq_solicitud_usuario"),
    )
    op.create_index(
        "ix_solicitud_usuario_solicitud_id", "solicitud_usuario", ["solicitud_id"]
    )
    op.create_index(
        "ix_solicitud_usuario_usuario_id", "solicitud_usuario", ["usuario_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_solicitud_usuario_usuario_id", table_name="solicitud_usuario")
    op.drop_index("ix_solicitud_usuario_solicitud_id", table_name="solicitud_usuario")
    op.drop_table("solicitud_usuario")
    op.drop_index(
        "ix_documento_solicitud_solicitud_id", table_name="documento_solicitud"
    )
    op.drop_table("documento_solicitud")
    op.drop_index(
        "ix_solicitud_convenio_solicitante_estado", table_name="solicitud_convenio"
    )
    for nombre in (
        "solicitante_programa",
        "solicitante_unidad",
        "solicitante_entidad",
        "solicitante_cargo",
        "solicitante_documento",
        "solicitante_correo",
        "solicitante_nombre",
        "supervisor_contraparte_correo",
        "supervisor_contraparte_telefono",
        "supervisor_contraparte_cargo",
        "supervisor_contraparte_nombre",
        "supervisor_usb_correo",
        "supervisor_usb_telefono",
        "supervisor_usb_cargo",
        "supervisor_usb_nombre",
        "direccion_aliado_propuesto",
        "telefono_aliado_propuesto",
        "ciudad_aliado_propuesto",
        "pais_aliado_propuesto",
        "contacto_contraparte_correo",
        "contacto_contraparte_telefono",
        "contacto_contraparte_cargo",
        "contacto_contraparte_nombre",
    ):
        op.drop_column("solicitud_convenio", nombre)
    op.execute("UPDATE solicitud_convenio SET objeto = '' WHERE objeto IS NULL")
    op.alter_column(
        "solicitud_convenio", "objeto", existing_type=sa.Text(), nullable=False
    )
    op.get_bind().execute(
        sa.text(
            "DELETE FROM tipo_convenio WHERE descripcion = :descripcion AND codigo IN "
            "('MARCO', 'ESPECIFICO', 'PRACTICA_INTERNACIONAL', "
            "'INVESTIGACION', 'PLAN_BENEFICIOS', 'OTRO')"
        ),
        {"descripcion": SEMILLA_DESCRIPCION},
    )
    nulos = (
        op.get_bind()
        .execute(
            sa.text("SELECT codigo FROM tipo_convenio WHERE naturaleza IS NULL LIMIT 1")
        )
        .scalar_one_or_none()
    )
    if nulos is not None:
        raise RuntimeError(
            "No se puede restaurar naturaleza NOT NULL: existe un tipo sin naturaleza"
        )
    op.alter_column(
        "tipo_convenio",
        "naturaleza",
        existing_type=sa.String(10),
        nullable=False,
    )
