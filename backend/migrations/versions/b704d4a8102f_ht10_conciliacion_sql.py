"""HT-10: conciliación SQL versionada para ejecución desde Supabase Cron.

Revision ID: b704d4a8102f
Revises: 2fa11b85762d

Esta migración instala la función, pero NO habilita pg_cron ni programa jobs.
Permite pruebas y despliegue controlado antes de activar la ejecución nocturna.
"""

from alembic import op

revision = "b704d4a8102f"
down_revision = "2fa11b85762d"
branch_labels = None
depends_on = None


FUNCION = r"""
CREATE FUNCTION ori_internal.conciliar_estados_ht10(
    p_fecha_referencia date DEFAULT NULL,
    p_simular boolean DEFAULT true
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $ht10$
DECLARE
    v_hoy date := COALESCE(
        p_fecha_referencia,
        (clock_timestamp() AT TIME ZONE 'America/Bogota')::date
    );
    v_cambio text;
    v_cambios integer := 0;
    v_sin_fecha integer := 0;
    v_legado_inconsistente integer := 0;
    v_transiciones jsonb := '[]'::jsonb;
    r record;
BEGIN
    -- No permitir NULL para que una omisión nunca derive en escritura.
    IF p_simular IS NULL THEN
        RAISE EXCEPTION 'HT-10: p_simular debe ser true o false';
    END IF;

    -- Una fecha de prueba no puede provocar cambios reales en Staging/Producción.
    -- El CLI original conserva sus propias defensas para pruebas locales.
    IF p_fecha_referencia IS NOT NULL AND NOT p_simular THEN
        RAISE EXCEPTION 'HT-10: las ejecuciones reales deben utilizar la fecha actual de Bogotá';
    END IF;

    -- Bloquear en orden fijo evita omisiones silenciosas y reduce interbloqueos.
    -- La transacción que invoca la función incluye updates + ambas auditorías.
    FOR r IN
        SELECT c.id, c.estado, c.fecha_vencimiento
        FROM public.convenio AS c
        WHERE c.estado IN ('VIGENTE', 'POR_VENCER', 'VENCIDO')
        ORDER BY c.id
        FOR UPDATE OF c
    LOOP
        IF r.fecha_vencimiento IS NULL THEN
            v_sin_fecha := v_sin_fecha + 1;
            CONTINUE;
        END IF;

        IF r.estado = 'VENCIDO' AND r.fecha_vencimiento >= v_hoy THEN
            v_legado_inconsistente := v_legado_inconsistente + 1;
            CONTINUE;
        END IF;

        v_cambio := CASE
            WHEN r.fecha_vencimiento < v_hoy THEN 'FINALIZADO'
            WHEN r.fecha_vencimiento <= v_hoy + 120 THEN 'POR_VENCER'
            ELSE 'VIGENTE'
        END;

        IF v_cambio = r.estado THEN
            CONTINUE;
        END IF;

        v_cambios := v_cambios + 1;
        v_transiciones := v_transiciones || jsonb_build_array(
            jsonb_build_object(
                'convenio_id', r.id,
                'anterior', r.estado,
                'nuevo', v_cambio
            )
        );

        IF p_simular THEN
            CONTINUE;
        END IF;

        UPDATE public.convenio AS c
        SET estado = v_cambio,
            actualizado_en = clock_timestamp()
        WHERE c.id = r.id AND c.estado = r.estado;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'HT-10: actualización concurrente inesperada para convenio %', r.id;
        END IF;

        INSERT INTO public.transicion_estado_convenio (
            convenio_id, estado_anterior, estado_nuevo,
            fecha_referencia, fecha_vencimiento
        ) VALUES (
            r.id, r.estado, v_cambio, v_hoy, r.fecha_vencimiento
        );

        -- La auditoría SQL debe reproducir el contrato HT-09; los eventos de
        -- SQL no pasan por el hook after_flush() del ORM de SQLAlchemy.
        INSERT INTO public.auditoria (
            usuario_id, rol, entidad, registro_id, accion, campo,
            valor_anterior, valor_nuevo, contexto, evento, ejecucion
        ) VALUES (
            NULL, NULL, 'convenio', r.id, 'UPDATE', 'estado',
            r.estado, v_cambio,
            'Concilió automáticamente el estado contractual de los convenios',
            'CONCILIACION_ESTADO_AUTOMATICA', 'AUTOMATICA'
        );
    END LOOP;

    RETURN jsonb_build_object(
        'fecha_referencia', v_hoy,
        'simulado', p_simular,
        'cambios', v_cambios,
        'sin_fecha', v_sin_fecha,
        'legado_inconsistente', v_legado_inconsistente,
        'transiciones', v_transiciones
    );
END;
$ht10$
"""


def upgrade() -> None:
    # Esquema privado: no está expuesto por defecto mediante PostgREST.
    op.execute("CREATE SCHEMA IF NOT EXISTS ori_internal")
    op.execute("REVOKE ALL ON SCHEMA ori_internal FROM PUBLIC")
    op.execute(FUNCION)
    op.execute(
        "REVOKE ALL ON FUNCTION ori_internal.conciliar_estados_ht10(date, boolean) FROM PUBLIC"
    )


def downgrade() -> None:
    # No elimina el esquema: otro proceso podría haber añadido objetos propios.
    # El job debe desprogramarse ANTES de un downgrade operativo.
    op.execute("DROP FUNCTION IF EXISTS ori_internal.conciliar_estados_ht10(date, boolean)")
