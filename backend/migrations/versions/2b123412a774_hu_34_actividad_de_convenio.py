"""HU-34/HU-35 actividad de convenio (entidad canónica compartida)

Revision ID: 2b123412a774
Revises: b337c7245190
Create Date: 2026-10-12 15:03:52.335842

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2b123412a774'
down_revision: str | Sequence[str] | None = 'b337c7245190'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'actividad_convenio',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('convenio_id', sa.Integer(), nullable=False),
        sa.Column('titulo', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('tipo', sa.String(length=80), nullable=True),
        sa.Column('parte_ejecutora', sa.String(length=20), nullable=True),
        sa.Column('fecha_planificada', sa.Date(), nullable=True),
        sa.Column('fecha_ejecucion', sa.Date(), nullable=True),
        sa.Column('estado', sa.String(length=20), server_default='PENDIENTE', nullable=False),
        sa.Column('resultado', sa.Text(), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('numero_participantes', sa.SmallInteger(), nullable=True),
        sa.Column('responsable_nombre', sa.String(length=200), nullable=True),
        sa.Column('responsable_id', sa.Integer(), nullable=True),
        sa.Column('registrado_por_id', sa.Integer(), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("estado IN ('PENDIENTE', 'EN_CURSO', 'REALIZADA', 'CANCELADA')", name='ck_actividad_convenio_estado'),
        sa.CheckConstraint("parte_ejecutora IS NULL OR parte_ejecutora IN ('USB', 'CONTRAPARTE', 'AMBAS')", name='ck_actividad_convenio_parte_ejecutora'),
        sa.CheckConstraint('numero_participantes IS NULL OR numero_participantes >= 0', name='ck_actividad_convenio_participantes_no_negativo'),
        sa.CheckConstraint("estado != 'REALIZADA' OR fecha_ejecucion IS NOT NULL", name='ck_actividad_convenio_realizada_requiere_fecha_ejecucion'),
        sa.ForeignKeyConstraint(['convenio_id'], ['convenio.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['responsable_id'], ['usuario.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['registrado_por_id'], ['usuario.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_actividad_convenio_convenio_id'), 'actividad_convenio', ['convenio_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_actividad_convenio_convenio_id'), table_name='actividad_convenio')
    op.drop_table('actividad_convenio')
