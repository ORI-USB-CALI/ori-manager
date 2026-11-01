# HT-10 — Conciliación contractual mediante Supabase Cron

## Alcance

- El backend ya almacena `fecha_vencimiento`, calculada o proporcionada según el flujo vigente.
- A partir de ese campo, la función versionada `ori_internal.conciliar_estados_ht10`
  persiste los estados `VIGENTE`, `POR_VENCER` y `FINALIZADO` (también regulariza `VENCIDO` pasado).
- No modifica `EN_TRAMITE`, `RENOVADO`, `CANCELADO` ni `FINALIZADO` existente.
- El vencimiento es inclusivo: un convenio que vence hoy no finaliza hasta mañana.
- Registra `transicion_estado_convenio` y `auditoria` de HT-09 en la misma transacción.
- `--simular` del CLI Python continúa disponible como instrumento independiente de diagnóstico.

## Ciclo de despliegue (primero Staging)

1. Crear rama desde `develop`, añadir migración y tests, ejecutar Ruff y pytest local.
2. Revisar PR y CI (el CI ejecuta `alembic upgrade head`; **no instala pg_cron**).
3. Hacer merge a `develop`; comprobar job Staging DB Migrations e identificar la revisión Alembic.
4. En Supabase **Staging solamente**, habilitar la extensión `pg_cron` desde Dashboard > Database > Extensions.
5. Verificar función, simulación y auditorías previstas antes de programar. No ejecutar
   `false` si falta validar el volumen de cambios y disponer de respaldo reciente.
6. Tras autorización y QA, programar el job usando una sesión de privilegios controlados.

La programación no está incluida en la migración para impedir que `alembic upgrade`
cree jobs automáticamente en CI o producción.

### Consultas de solo lectura en Staging

```sql
SELECT extname, extversion FROM pg_extension WHERE extname='pg_cron';

SELECT ori_internal.conciliar_estados_ht10(NULL, true);

SELECT convenio_id, estado_anterior, estado_nuevo, fecha_referencia
FROM public.transicion_estado_convenio ORDER BY id DESC LIMIT 20;
```

### Activación diaria (NO EJECUTAR sin autorización y QA)

La zona `cron.timezone` del proyecto se ha verificado como GMT, equivalente a UTC.
La ejecución a las 05:00 UTC coincide con las 00:00 de Bogotá (UTC-5).
La función usa `clock_timestamp() AT TIME ZONE 'America/Bogota'` independientemente
 de la zona horaria de la conexión.

```sql
SELECT cron.schedule(
  'ori-ht10-conciliacion-diaria',
  '0 5 * * *',
  $$SELECT ori_internal.conciliar_estados_ht10(NULL, false)$$
);
```

### Inspección de ejecuciones

```sql
SELECT jobid, jobname, schedule, active FROM cron.job
WHERE jobname = 'ori-ht10-conciliacion-diaria';

SELECT j.jobname, d.start_time, d.end_time, d.status, d.return_message
FROM cron.job_run_details AS d
JOIN cron.job AS j ON j.jobid = d.jobid
WHERE j.jobname = 'ori-ht10-conciliacion-diaria'
ORDER BY d.start_time DESC LIMIT 20;
```

### Desactivación operativa

```sql
SELECT cron.unschedule('ori-ht10-conciliacion-diaria');
```

No modificar otros jobs. Un job fallido no garantiza la transición a medianoche:
revisar el historial y contar con una comprobación de operación periódica.

## Reversión

1. Desprogramar `ori-ht10-conciliacion-diaria` en el ambiente correspondiente.
2. Revisar las transiciones ya realizadas; **NO** revertirlas masivamente ni
   borrar las filas de auditoría.
3. Solo después, evaluar downgrade de la migración en el flujo regular.

## Pendientes deliberados

- Definir con PO la convención de cálculo `fecha_inicio + duracion_meses` y su relación
  con una `fecha_vencimiento` modificada manualmente (HT-08 / HT-14); es un cambio
  de contratos distinto, no debe mezclarse en esta migración.
- En una segunda iteración evaluar si la implementación Python del CLI debe delegar
  en la función SQL para evitar mantener reglas equivalentes en dos lenguajes.
- Añadir vigilancia de última ejecución exitosa antes de liberar a producción.
