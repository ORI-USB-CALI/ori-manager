"""Persist counterparty identity and distinguish ally document types.

Revision ID: f10409b2c3d4
Revises: e20406a1b2c3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f10409b2c3d4"
down_revision: str | Sequence[str] | None = "e20406a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPOS_IDENTIFICACION = (
    "'NIT', 'CEDULA_CIUDADANIA', 'CEDULA_EXTRANJERIA', 'PASAPORTE', "
    "'IDENTIFICACION_FISCAL_EXTRANJERA', 'OTRO'"
)


def upgrade() -> None:
    op.add_column("aliado", sa.Column("tipo_identificacion", sa.String(33), nullable=True))
    op.execute("UPDATE aliado SET tipo_identificacion = 'OTRO'")
    op.alter_column("aliado", "tipo_identificacion", nullable=False)
    op.create_check_constraint(
        "ck_aliado_tipo_identificacion", "aliado",
        f"tipo_identificacion IN ({TIPOS_IDENTIFICACION})",
    )
    op.drop_constraint("aliado_identificacion_key", "aliado", type_="unique")
    op.create_unique_constraint(
        "uq_aliado_tipo_identificacion", "aliado",
        ["tipo_identificacion", "identificacion"],
    )
    op.add_column("solicitud_convenio", sa.Column("tipo_identificacion_aliado_propuesto", sa.String(33), nullable=True))
    op.add_column("solicitud_convenio", sa.Column("identificacion_aliado_propuesto", sa.String(40), nullable=True))
    op.add_column("solicitud_convenio", sa.Column("tipo_aliado_propuesto", sa.String(22), nullable=True))
    op.add_column("solicitud_convenio", sa.Column("correo_aliado_propuesto", sa.String(160), nullable=True))
    op.add_column("solicitud_convenio", sa.Column("sector_economico_aliado_propuesto", sa.String(120), nullable=True))
    op.create_check_constraint(
        "ck_solicitud_tipo_identificacion_aliado_propuesto", "solicitud_convenio",
        f"tipo_identificacion_aliado_propuesto IN ({TIPOS_IDENTIFICACION})",
    )
    op.create_check_constraint(
        "ck_solicitud_tipo_aliado_propuesto", "solicitud_convenio",
        "tipo_aliado_propuesto IN ('UNIVERSIDAD', 'COLEGIO', 'EMPRESA', 'ENTIDAD_GUBERNAMENTAL')",
    )


def downgrade() -> None:
    duplicate = op.get_bind().execute(sa.text(
        "SELECT identificacion FROM aliado GROUP BY identificacion HAVING count(*) > 1 LIMIT 1"
    )).scalar_one_or_none()
    if duplicate is not None:
        raise RuntimeError(
            "No se puede restaurar UNIQUE(identificacion): existen identificaciones "
            "repetidas entre tipos distintos"
        )
    op.drop_constraint("ck_solicitud_tipo_aliado_propuesto", "solicitud_convenio", type_="check")
    op.drop_constraint("ck_solicitud_tipo_identificacion_aliado_propuesto", "solicitud_convenio", type_="check")
    op.drop_column("solicitud_convenio", "sector_economico_aliado_propuesto")
    op.drop_column("solicitud_convenio", "correo_aliado_propuesto")
    op.drop_column("solicitud_convenio", "tipo_aliado_propuesto")
    op.drop_column("solicitud_convenio", "identificacion_aliado_propuesto")
    op.drop_column("solicitud_convenio", "tipo_identificacion_aliado_propuesto")
    op.drop_constraint("uq_aliado_tipo_identificacion", "aliado", type_="unique")
    op.create_unique_constraint("aliado_identificacion_key", "aliado", ["identificacion"])
    op.drop_constraint("ck_aliado_tipo_identificacion", "aliado", type_="check")
    op.drop_column("aliado", "tipo_identificacion")
