"""HU-18 bitacora de auditoria: rol, indice por entidad y fecha, inmutabilidad

Revision ID: b18a4d2c9e71
Revises: f3a1c8e4d2b7
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b18a4d2c9e71"
down_revision: str | Sequence[str] | None = "f3a1c8e4d2b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("auditoria", sa.Column("rol", sa.String(length=40), nullable=True))
    # Aproximación: los registros previos toman el rol vigente de su usuario.
    # Debe ejecutarse antes de crear el trigger que impide UPDATE.
    op.execute(
        """
        UPDATE auditoria AS a
        SET rol = r.codigo
        FROM usuario AS u
        JOIN rol AS r ON r.id = u.rol_id
        WHERE u.id = a.usuario_id
        """
    )
    op.create_index(
        "ix_auditoria_entidad_fecha_hora", "auditoria", ["entidad", "fecha_hora"]
    )
    # Los productores existentes no asignan rol: si llega nulo, la base toma el
    # rol vigente del usuario al insertar. Un rol explícito se respeta.
    op.execute(
        """
        CREATE FUNCTION auditoria_completar_rol() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.rol IS NULL THEN
                SELECT r.codigo INTO NEW.rol
                FROM usuario AS u
                JOIN rol AS r ON r.id = u.rol_id
                WHERE u.id = NEW.usuario_id;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_auditoria_completar_rol
        BEFORE INSERT ON auditoria
        FOR EACH ROW EXECUTE FUNCTION auditoria_completar_rol()
        """
    )
    # CA-03: un registro de bitácora nunca se sobrescribe. Se bloquea solo UPDATE,
    # porque la limpieza de los tests concurrentes (HU-14, HU-15) borra filas.
    # Una migración de datos futura que necesite UPDATE debe envolverlo en
    # ALTER TABLE auditoria DISABLE/ENABLE TRIGGER tr_auditoria_no_sobrescribible.
    op.execute(
        """
        CREATE FUNCTION auditoria_no_sobrescribible() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'La bitácora de auditoría no admite modificar registros';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_auditoria_no_sobrescribible
        BEFORE UPDATE ON auditoria
        FOR EACH ROW EXECUTE FUNCTION auditoria_no_sobrescribible()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER tr_auditoria_no_sobrescribible ON auditoria")
    op.execute("DROP FUNCTION auditoria_no_sobrescribible()")
    op.execute("DROP TRIGGER tr_auditoria_completar_rol ON auditoria")
    op.execute("DROP FUNCTION auditoria_completar_rol()")
    op.drop_index("ix_auditoria_entidad_fecha_hora", table_name="auditoria")
    op.drop_column("auditoria", "rol")
