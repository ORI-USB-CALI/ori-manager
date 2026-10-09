"""HU-33 notificaciones de acciones pendientes.

Revision ID: a2b6f4d9c1e8
Revises: f3a1c8e4d2b7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2b6f4d9c1e8"
down_revision: str | Sequence[str] | None = "f3a1c8e4d2b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notificacion",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("entidad_tipo", sa.String(length=20), nullable=False),
        sa.Column("entidad_id", sa.Integer(), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column(
            "leida", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("leida_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resuelta", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("resuelta_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "tipo IN ('REVISION_JURIDICA_PENDIENTE', 'DEVOLUCION_REVISION', "
            "'SOLICITUD_DEVUELTA', 'REVISION_CONTRAPARTE_PENDIENTE')",
            name="ck_notificacion_tipo",
        ),
        sa.CheckConstraint(
            "entidad_tipo IN ('CONVENIO', 'SOLICITUD')",
            name="ck_notificacion_entidad_tipo",
        ),
    )
    op.create_index(
        "ix_notificacion_usuario_id", "notificacion", ["usuario_id"]
    )
    op.create_index(
        "ix_notificacion_creado_en", "notificacion", ["creado_en"]
    )
    # CA-09: a lo sumo una notificacion sin resolver por usuario+tipo+entidad.
    # Parcial (solo WHERE resuelta = false) para que una accion que se repite
    # mas adelante sobre la misma entidad (ej. una solicitud devuelta por
    # segunda vez) pueda volver a notificarse una vez la anterior ya se
    # resolvio.
    op.create_index(
        "uq_notificacion_pendiente_por_usuario",
        "notificacion",
        ["usuario_id", "tipo", "entidad_tipo", "entidad_id"],
        unique=True,
        postgresql_where=sa.text("resuelta = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_notificacion_pendiente_por_usuario", table_name="notificacion")
    op.drop_index("ix_notificacion_creado_en", table_name="notificacion")
    op.drop_index("ix_notificacion_usuario_id", table_name="notificacion")
    op.drop_table("notificacion")
