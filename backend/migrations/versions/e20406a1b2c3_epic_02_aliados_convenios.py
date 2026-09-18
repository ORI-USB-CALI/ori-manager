"""epic 02 aliados y convenios

Revision ID: e20406a1b2c3
Revises: 3721b9892fbb
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e20406a1b2c3"
down_revision: str | Sequence[str] | None = "3721b9892fbb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pais",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo_iso", sa.CHAR(length=2), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo_iso"),
        sa.UniqueConstraint("nombre"),
    )
    op.create_table(
        "aliado",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("tipo", sa.String(length=22), nullable=False),
        sa.Column("sector_economico", sa.String(length=120), nullable=True),
        sa.Column("identificacion", sa.String(length=40), nullable=False),
        sa.Column("pais_id", sa.Integer(), nullable=True),
        sa.Column("ciudad", sa.String(length=120), nullable=True),
        sa.Column("direccion", sa.String(length=200), nullable=True),
        sa.Column("telefono", sa.String(length=40), nullable=True),
        sa.Column("correo", sa.String(length=160), nullable=True),
        sa.Column("sitio_web", sa.String(length=200), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('UNIVERSIDAD', 'COLEGIO', 'EMPRESA', 'ENTIDAD_GUBERNAMENTAL')",
            name="ck_aliado_tipo",
        ),
        sa.CheckConstraint(
            "tipo != 'EMPRESA' OR (sector_economico IS NOT NULL AND btrim(sector_economico) != '')",
            name="ck_aliado_empresa_sector_economico",
        ),
        sa.ForeignKeyConstraint(["pais_id"], ["pais.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identificacion"),
    )
    op.create_table(
        "contacto_aliado",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aliado_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=160), nullable=False),
        sa.Column("cargo", sa.String(length=120), nullable=True),
        sa.Column("correo", sa.String(length=160), nullable=True),
        sa.Column("telefono", sa.String(length=40), nullable=True),
        sa.Column("extension", sa.String(length=20), nullable=True),
        sa.Column("es_principal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["aliado_id"], ["aliado.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("aliado_id", "correo", name="uq_contacto_aliado_correo"),
    )
    op.create_table(
        "tipo_convenio",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=40), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("naturaleza", sa.String(length=10), nullable=False),
        sa.Column("duracion_meses_defecto", sa.SmallInteger(), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("naturaleza IN ('MARCO', 'ESPECIFICO')", name="ck_tipo_convenio_naturaleza"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_table(
        "etapa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orden", sa.SmallInteger(), nullable=False),
        sa.Column("codigo", sa.String(length=60), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("area_responsable", sa.String(length=120), nullable=True),
        sa.Column("activa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
        sa.UniqueConstraint("nombre"),
        sa.UniqueConstraint("orden"),
    )
    etapa = sa.table(
        "etapa",
        sa.column("orden", sa.SmallInteger()),
        sa.column("codigo", sa.String()),
        sa.column("nombre", sa.String()),
        sa.column("descripcion", sa.Text()),
        sa.column("area_responsable", sa.String()),
        sa.column("activa", sa.Boolean()),
    )
    op.bulk_insert(
        etapa,
        [
            {"orden": 1, "codigo": "SOLICITUD", "nombre": "Solicitud", "descripcion": None, "area_responsable": None, "activa": True},
            {"orden": 2, "codigo": "ELABORACION", "nombre": "Elaboración", "descripcion": None, "area_responsable": None, "activa": True},
            {"orden": 3, "codigo": "REVISION_AVAL_JURIDICO", "nombre": "Revisión y aval jurídico", "descripcion": None, "area_responsable": None, "activa": True},
            {"orden": 4, "codigo": "REVISION_CONTRAPARTE", "nombre": "Revisión de contraparte", "descripcion": None, "area_responsable": None, "activa": True},
            {"orden": 5, "codigo": "REVISION_FINAL", "nombre": "Revisión final", "descripcion": None, "area_responsable": None, "activa": True},
            {"orden": 6, "codigo": "APROBACION_FIRMAS", "nombre": "Aprobación y proceso de firmas", "descripcion": None, "area_responsable": None, "activa": True},
            {"orden": 7, "codigo": "FIRMA_ARCHIVO_SEGUIMIENTO", "nombre": "Firma y archivo/seguimiento", "descripcion": None, "area_responsable": None, "activa": True},
        ],
    )
    op.create_table(
        "solicitud_convenio",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("consecutivo", sa.String(length=40), nullable=False),
        sa.Column("tipo_solicitante", sa.String(length=7), nullable=False),
        sa.Column("solicitante_id", sa.Integer(), nullable=False),
        sa.Column("unidad_organizacional_id", sa.Integer(), nullable=True),
        sa.Column("aliado_id", sa.Integer(), nullable=True),
        sa.Column("nombre_aliado_propuesto", sa.String(length=200), nullable=True),
        sa.Column("tipo_convenio_id", sa.Integer(), nullable=True),
        sa.Column("objeto", sa.Text(), nullable=False),
        sa.Column("justificacion", sa.Text(), nullable=True),
        sa.Column("actividades_por_parte", sa.Text(), nullable=True),
        sa.Column("metas_esperadas", sa.Text(), nullable=True),
        sa.Column("implicacion_financiera", sa.Text(), nullable=True),
        sa.Column("vigencia_estimada", sa.String(length=120), nullable=True),
        sa.Column("requisitos_renovacion", sa.Text(), nullable=True),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("aprobada_por_director", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("fecha_aprobacion_director", sa.Date(), nullable=True),
        sa.Column("fecha_radicacion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fecha_recibido_ori", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default=sa.text("'BORRADOR'"), nullable=False),
        sa.Column("motivo_rechazo", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("tipo_solicitante IN ('INTERNO', 'EXTERNO')", name="ck_solicitud_tipo_solicitante"),
        sa.CheckConstraint("estado IN ('BORRADOR', 'RADICADA', 'EN_ESTUDIO', 'DEVUELTA', 'APROBADA', 'RECHAZADA')", name="ck_solicitud_estado"),
        sa.ForeignKeyConstraint(["aliado_id"], ["aliado.id"]),
        sa.ForeignKeyConstraint(["solicitante_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tipo_convenio_id"], ["tipo_convenio.id"]),
        sa.ForeignKeyConstraint(["unidad_organizacional_id"], ["unidad_organizacional.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("consecutivo"),
    )
    op.create_table(
        "convenio",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=40), nullable=True),
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("aliado_id", sa.Integer(), nullable=True),
        sa.Column("tipo_convenio_id", sa.Integer(), nullable=True),
        sa.Column("etapa_actual_id", sa.Integer(), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default=sa.text("'EN_TRAMITE'"), nullable=False),
        sa.Column("objeto", sa.Text(), nullable=True),
        sa.Column("alcance", sa.String(length=20), nullable=True),
        sa.Column("unidad_organizacional_id", sa.Integer(), nullable=True),
        sa.Column("implicacion_financiera", sa.Text(), nullable=True),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=True),
        sa.Column("fecha_firma", sa.Date(), nullable=True),
        sa.Column("duracion_meses", sa.Integer(), nullable=True),
        sa.Column("porcentaje_avance", sa.SmallInteger(), nullable=True),
        sa.Column("convenio_origen_id", sa.Integer(), nullable=True),
        sa.Column("numero_renovacion", sa.SmallInteger(), nullable=True),
        sa.Column("creado_por_id", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("estado IN ('EN_TRAMITE', 'VIGENTE', 'POR_VENCER', 'VENCIDO', 'RENOVADO', 'FINALIZADO', 'CANCELADO')", name="ck_convenio_estado"),
        sa.CheckConstraint("alcance IS NULL OR alcance IN ('PROGRAMA', 'INSTITUCIONAL')", name="ck_convenio_alcance"),
        sa.CheckConstraint("porcentaje_avance IS NULL OR porcentaje_avance BETWEEN 0 AND 100", name="ck_convenio_porcentaje_avance"),
        sa.ForeignKeyConstraint(["aliado_id"], ["aliado.id"]),
        sa.ForeignKeyConstraint(["convenio_origen_id"], ["convenio.id"]),
        sa.ForeignKeyConstraint(["creado_por_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["etapa_actual_id"], ["etapa.id"]),
        sa.ForeignKeyConstraint(["solicitud_id"], ["solicitud_convenio.id"]),
        sa.ForeignKeyConstraint(["tipo_convenio_id"], ["tipo_convenio.id"]),
        sa.ForeignKeyConstraint(["unidad_organizacional_id"], ["unidad_organizacional.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
        sa.UniqueConstraint("solicitud_id"),
    )


def downgrade() -> None:
    op.drop_table("convenio")
    op.drop_table("solicitud_convenio")
    op.drop_table("etapa")
    op.drop_table("tipo_convenio")
    op.drop_table("contacto_aliado")
    op.drop_table("aliado")
    op.drop_table("pais")
