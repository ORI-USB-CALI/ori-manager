"""HU-14 hardening de revisión externa de contraparte.

Revision ID: d9e1f3a5b7c2
Revises: c5a8e2f1d7b4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9e1f3a5b7c2"
down_revision: str | Sequence[str] | None = "c5a8e2f1d7b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_observacion_revision_actor_registrado",
        "observacion_revision",
        "origen = 'CONTRAPARTE' OR registrada_por_id IS NOT NULL",
    )
    op.add_column(
        "invitacion_revision_contraparte",
        sa.Column("generada_por_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_invitacion_contraparte_generada_por",
        "invitacion_revision_contraparte",
        "usuario",
        ["generada_por_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        sa.text(
            """
            UPDATE invitacion_revision_contraparte AS invitacion
            SET generada_por_id = revision.creada_por_id
            FROM revision_convenio AS revision
            WHERE revision.id = invitacion.revision_convenio_id
              AND invitacion.generada_por_id IS NULL
            """
        )
    )
    faltantes = op.get_bind().execute(
        sa.text(
            "SELECT count(*) FROM invitacion_revision_contraparte "
            "WHERE generada_por_id IS NULL"
        )
    ).scalar_one()
    if faltantes:
        raise RuntimeError(
            "No es posible identificar al usuario ORI que generó invitaciones "
            "históricas de contraparte"
        )
    op.alter_column(
        "invitacion_revision_contraparte",
        "generada_por_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_index(
        "ix_invitacion_revision_contraparte_generada_por_id",
        "invitacion_revision_contraparte",
        ["generada_por_id"],
    )


def downgrade() -> None:
    observaciones_externas = op.get_bind().execute(
        sa.text(
            """
            SELECT count(*)
            FROM observacion_revision
            WHERE origen = 'CONTRAPARTE' AND registrada_por_id IS NULL
            """
        )
    ).scalar_one()
    if observaciones_externas:
        raise RuntimeError(
            "Downgrade HU-14 rechazado: existen observaciones externas sin usuario "
            "interno y la revisión anterior no puede representarlas al continuar "
            "el downgrade sin perder o falsificar datos"
        )
    op.drop_index(
        "ix_invitacion_revision_contraparte_generada_por_id",
        table_name="invitacion_revision_contraparte",
    )
    op.drop_constraint(
        "fk_invitacion_contraparte_generada_por",
        "invitacion_revision_contraparte",
        type_="foreignkey",
    )
    op.drop_column("invitacion_revision_contraparte", "generada_por_id")
    op.drop_constraint(
        "ck_observacion_revision_actor_registrado",
        "observacion_revision",
        type_="check",
    )
