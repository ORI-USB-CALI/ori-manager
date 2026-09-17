"""change convenios.estado default to EN_TRAMITE

Un convenio nunca debe nacer en estado VIGENTE (ver MER, paquete 5:
Convenio y trazabilidad, CA-04). El valor por defecto anterior era
VIGENTE; se alinea al ciclo de vida real del convenio.

Revision ID: e5f1b3c4d9a2
Revises: d4e0a2b3c8f1
Create Date: 2026-09-17 00:20:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f1b3c4d9a2"
down_revision: str | Sequence[str] | None = "d4e0a2b3c8f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("convenios", "estado", server_default="EN_TRAMITE")


def downgrade() -> None:
    op.alter_column("convenios", "estado", server_default="VIGENTE")
