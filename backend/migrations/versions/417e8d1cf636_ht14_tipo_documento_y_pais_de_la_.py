"""HT-14 tipo de documento, dígito de verificación y país por catálogo.

Revision ID: 417e8d1cf636
Revises: 2fa11b85762d
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "417e8d1cf636"
down_revision: str | Sequence[str] | None = "2fa11b85762d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIPOS_IDENTIFICACION = (
    "'NIT', 'CEDULA_CIUDADANIA', 'CEDULA_EXTRANJERIA', 'PASAPORTE', "
    "'IDENTIFICACION_FISCAL_EXTRANJERA', 'OTRO'"
)
# HT-14: el DV del NIT se guarda aparte de la base y solo existe para NIT.
_RESTRICCIONES_DV = {
    "digito_verificacion_aliado_propuesto": "ck_solicitud_digito_verificacion_aliado_propuesto",
    "solicitante_digito_verificacion": "ck_solicitud_solicitante_digito_verificacion",
    "digito_verificacion": "ck_aliado_digito_verificacion",
}


def upgrade() -> None:
    # Sin backfill: las solicitudes existentes conservan su país en texto y se
    # validan cuando se vuelvan a editar o radicar (HT-14 RN-10).
    op.add_column(
        "solicitud_convenio",
        sa.Column("solicitante_tipo_documento", sa.String(length=33), nullable=True),
    )
    op.create_check_constraint(
        "ck_solicitud_solicitante_tipo_documento",
        "solicitud_convenio",
        f"solicitante_tipo_documento IN ({_TIPOS_IDENTIFICACION})",
    )
    for tabla, columna, tipo in (
        ("solicitud_convenio", "digito_verificacion_aliado_propuesto",
         "tipo_identificacion_aliado_propuesto"),
        ("solicitud_convenio", "solicitante_digito_verificacion",
         "solicitante_tipo_documento"),
        ("aliado", "digito_verificacion", "tipo_identificacion"),
    ):
        op.add_column(tabla, sa.Column(columna, sa.String(length=1), nullable=True))
        op.create_check_constraint(
            _RESTRICCIONES_DV[columna],
            tabla,
            f"{columna} IS NULL OR ({tipo} = 'NIT' AND {columna} ~ '^[0-9]$')",
        )
    op.add_column(
        "solicitud_convenio",
        sa.Column("pais_aliado_propuesto_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_solicitud_convenio_pais_aliado_propuesto_id_pais",
        "solicitud_convenio",
        "pais",
        ["pais_aliado_propuesto_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_solicitud_convenio_pais_aliado_propuesto_id_pais",
        "solicitud_convenio",
        type_="foreignkey",
    )
    op.drop_column("solicitud_convenio", "pais_aliado_propuesto_id")
    for tabla, columna in (
        ("aliado", "digito_verificacion"),
        ("solicitud_convenio", "solicitante_digito_verificacion"),
        ("solicitud_convenio", "digito_verificacion_aliado_propuesto"),
    ):
        op.drop_constraint(_RESTRICCIONES_DV[columna], tabla, type_="check")
        op.drop_column(tabla, columna)
    op.drop_constraint(
        "ck_solicitud_solicitante_tipo_documento", "solicitud_convenio", type_="check"
    )
    op.drop_column("solicitud_convenio", "solicitante_tipo_documento")
