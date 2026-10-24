from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bca1bf4a042d'
down_revision: str | Sequence[str] | None = 'e77280c6486a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Los convenios existentes no reciben borrador: trabajan sobre el contenido de
    # su versión actual hasta el primer guardado de avance.
    op.create_table(
        "borrador_convenio",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("convenio_id", sa.Integer(), nullable=False),
        sa.Column("contenido", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("actualizado_por_id", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("revision > 0", name="ck_borrador_convenio_revision_positiva"),
        sa.ForeignKeyConstraint(
            ["actualizado_por_id"], ["usuario.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["convenio_id"], ["convenio.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("convenio_id", name="uq_borrador_convenio_convenio"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("borrador_convenio")
