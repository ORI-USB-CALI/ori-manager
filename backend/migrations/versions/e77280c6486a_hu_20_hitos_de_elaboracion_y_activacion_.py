from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e77280c6486a'
down_revision: str | Sequence[str] | None = 'f3a1c8e4d2b7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "convenio",
        sa.Column("elaboracion_iniciada_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "convenio",
        sa.Column("activado_en", sa.DateTime(timezone=True), nullable=True),
    )
    # Los convenios existentes toman sus hitos del historial de etapas: el ingreso
    # inicial a Elaboración y la primera llegada a seguimiento, que solo ocurre al
    # formalizar las firmas.
    op.execute(
        sa.text(
            """
            UPDATE convenio
            SET elaboracion_iniciada_en = COALESCE(
                (
                    SELECT min(h.fecha_cambio)
                    FROM historial_etapa h
                    JOIN etapa e ON e.id = h.etapa_destino_id
                    WHERE h.convenio_id = convenio.id
                      AND h.etapa_origen_id IS NULL
                      AND e.codigo = 'ELABORACION'
                ),
                convenio.creado_en
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE convenio
            SET activado_en = (
                SELECT min(h.fecha_cambio)
                FROM historial_etapa h
                JOIN etapa e ON e.id = h.etapa_destino_id
                WHERE h.convenio_id = convenio.id
                  AND e.codigo = 'FIRMA_ARCHIVO_SEGUIMIENTO'
            )
            WHERE convenio.estado <> 'EN_TRAMITE'
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("convenio", "activado_en")
    op.drop_column("convenio", "elaboracion_iniciada_en")
