"""ht-06 contador de codigo institucional

Revision ID: 2fa11b85762d
Revises: 9d53cf1dcef3
Create Date: 2026-10-25 17:56:58.766620

Crea el consecutivo anual del código institucional del convenio. No asigna
códigos a los convenios existentes: eso lo hace el procedimiento de
regularización de CA-08, que es una operación autorizada y auditada aparte.

Las filas de cada año se crean solas al entregar el primer consecutivo de ese
año, así que la migración no siembra ninguna y no depende de la fecha en que
se ejecute.

El autogenerate de Alembic propone además borrar el índice parcial
`uq_notificacion_pendiente_por_usuario` de HU-33, que no sabe reconstruir
desde los modelos. Se omite a propósito: no pertenece a HT-06 y ese índice
es el que impide notificaciones pendientes duplicadas.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2fa11b85762d'
down_revision: str | Sequence[str] | None = '9d53cf1dcef3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'contador_codigo_convenio',
        sa.Column('anio', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column(
            'ultimo_consecutivo',
            sa.Integer(),
            server_default=sa.text('0'),
            nullable=False,
        ),
        sa.CheckConstraint(
            'ultimo_consecutivo >= 0',
            name='ck_contador_codigo_convenio_consecutivo',
        ),
        sa.PrimaryKeyConstraint('anio'),
    )


def downgrade() -> None:
    """Revertir solo elimina el contador; los códigos ya asignados se conservan.

    `convenio.codigo` existe desde `e20406a1b2c3` y no lo toca esta migración,
    así que bajar de revisión no borra identificadores institucionales ya
    entregados. Volver a subir reanuda cada año desde cero, de modo que una
    reversión en un entorno con códigos vivos exige revisar el contador antes
    de formalizar de nuevo.
    """
    op.drop_table('contador_codigo_convenio')
