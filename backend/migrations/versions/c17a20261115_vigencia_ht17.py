"""HT-17: distinguir vigencias nuevas sin reescribir datos historicos."""

import sqlalchemy as sa
from alembic import op

revision = "c17a20261115"
down_revision = "0b2fb1bed5b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "convenio",
        sa.Column(
            "vigencia_ht17", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade():
    op.drop_column("convenio", "vigencia_ht17")
