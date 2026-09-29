"""HU-17 area responsable por etapa

Revision ID: 68abde7e23b2
Revises: c6f9b2e4d8a1
Create Date: 2026-09-26 17:32:26.517622

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '68abde7e23b2'
down_revision: str | Sequence[str] | None = 'c6f9b2e4d8a1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AREAS_RESPONSABLES = {
    "SOLICITUD": "Solicitante",
    "ELABORACION": "Gestor ORI",
    "REVISION_AVAL_JURIDICO": "Oficina Jurídica",
    "REVISION_CONTRAPARTE": "Contraparte",
    "REVISION_FINAL": "ORI",
    "APROBACION_FIRMAS": "ORI",
    "FIRMA_ARCHIVO_SEGUIMIENTO": "ORI",
}

etapa = sa.table(
    "etapa",
    sa.column("codigo", sa.String()),
    sa.column("area_responsable", sa.String()),
)


def upgrade() -> None:
    """Upgrade schema."""
    for codigo, area in AREAS_RESPONSABLES.items():
        op.execute(
            etapa.update()
            .where(etapa.c.codigo == codigo)
            .values(area_responsable=area)
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        etapa.update()
        .where(etapa.c.codigo.in_(list(AREAS_RESPONSABLES)))
        .values(area_responsable=None)
    )
