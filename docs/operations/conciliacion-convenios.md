# Conciliación diaria del ciclo de vida de convenios

Propuesta para revisión del líder técnico. No se agregó un programador activo,
no se modificaron los Blueprints de Render y no se ejecutó nada contra ambientes
desplegados. La plantilla adyacente termina en `.example` y GitHub no la ejecuta.

## Comportamiento

El comando `python -m backend.cli.conciliar_convenios` usa el día calendario de
`America/Bogota`. Para VIGENTE/POR_VENCER calcula:

| Vencimiento respecto al día de referencia | Estado persistido |
| --- | --- |
| Más de 120 días | VIGENTE |
| Entre hoy y hoy + 120, inclusive | POR_VENCER |
| Antes de hoy | FINALIZADO |

También convierte VENCIDO legado con fecha pasada a FINALIZADO. VENCIDO con
fecha presente/futura se conserva y genera `VENCIDO_SIN_FECHA_PASADA` para revisión.
Se conserva el enum y todos los contratos históricos. No se modifica EN_TRAMITE,
CANCELADO, RENOVADO ni FINALIZADO persistido. Un candidato sin fecha conserva su
estado y genera `SIN_FECHA_VENCIMIENTO` con ID y referencia en los logs.

La conciliación posee una transacción completa: bloquea candidatos con
`SELECT FOR UPDATE` en orden de ID, recarga valores persistidos y confirma
estado y bitácora juntos. No usa `SKIP LOCKED`: una disputa no omite silenciosamente
un convenio. El CLI limita espera de locks a 5 segundos y cada sentencia a
120 segundos. Un error revierte toda la ejecución. Una repetición solo registra
transiciones reales. La conciliación no consulta ni cancela renovaciones hijas.

Solo cambian `estado` y el timestamp técnico `actualizado_en`. Las fechas del
convenio, relaciones, documento/versiones e historial previo se conservan.

## Registro auditable

La migración `a9c72d104e6b` agrega `transicion_estado_convenio`. Cada fila contiene
ID del convenio, actor fijo `SISTEMA`, estado anterior/nuevo, fecha de referencia,
fecha de vencimiento usada y hora real de ejecución con zona. Se guarda en la
misma transacción del cambio. No usa el usuario creador como actor, no crea un
usuario artificial ni modifica la auditoría humana existente.

La tabla es la bitácora de transiciones automáticas; no se agrega un endpoint ni
se altera el historial de etapas. Consulta operativa de revisión:

```sql
SELECT convenio_id, actor, estado_anterior, estado_nuevo,
       fecha_referencia, fecha_vencimiento,
       ejecutado_en AT TIME ZONE 'America/Bogota' AS ejecutado_en_bogota
FROM transicion_estado_convenio
ORDER BY id DESC;
```

Los logs de éxito se emiten después del commit. Incluyen transiciones,
referencia, intento, simulación y conteos de anomalías. Los fallos muestran clase
de error y SQLSTATE, sin parámetros SQL ni credenciales. Las anomalías se
registran en logs, no crean filas diarias repetidas en la bitácora.

## Relación con HU-30, HU-31 y HU-32

Las alertas conservan la ventana inclusiva de 120 días y las exclusiones por
NO_SE_RENOVARA y renovación EN_TRAMITE. Desde el día siguiente al vencimiento
FINALIZADO no produce alerta. Los GET no ejecutan la conciliación ni escriben.

FINALIZADO se admite como origen en el POST de renovación existente y como
estado del padre al formalizar el hijo. Se mantienen validaciones de fecha,
versión actual existente y ausencia de hijo activo, el índice único parcial y
la transacción de formalización. Cancelar un intento conserva el padre. Las
decisiones negativas históricas se conservan. FINALIZADO no se agrega a
Pendientes preventivos; con hijo activo o decisión histórica puede continuar
visible en las vistas de seguimiento correspondientes.

El detalle ofrece Iniciar renovación a quienes tienen el permiso existente
`convenios.gestionar_renovaciones` (Gestor/Admin ORI). Reutiliza el modal, POST y
tratamiento de errores; al confirmar navega al detalle de la nueva elaboración.
La API valida de nuevo la versión y el hijo activo ante concurrencia.

HU-32 y HU-33 no se modifican. No se infiere un estado de evaluación durante
consultas: HU-32 continúa dependiendo de FINALIZADO persistido. La renovación
no elimina registros históricos ni evaluaciones. Esta rama base no contiene
implementación ni tests identificables de HU-32; no se afirma una regresión
ejecutada sobre una función ausente. Su integración debe verificarse cuando
esa historia esté disponible, sin cambiar sus criterios.

## Ejecución automática aprobada para HT-10

La arquitectura seleccionada utiliza Supabase Cron (`pg_cron`) para
ejecutar diariamente una función privada de PostgreSQL.

La función versionada `ori_internal.conciliar_estados_ht10` actualiza
el estado contractual y registra las transiciones y la auditoría
en una misma transacción.

El horario objetivo es 05:00 UTC, equivalente a las 00:00 de
America/Bogota.

La migración instala únicamente la función SQL. No habilita
`pg_cron`, no programa jobs y no ejecuta conciliaciones sobre datos
existentes.

La configuración y validación operativa se documentan en
`docs/operations/ht10-supabase-cron.md`.

El CLI Python se conserva como herramienta de diagnóstico y
conciliación manual. No debe activarse un segundo programador
que provoque ejecuciones redundantes.

La activación del job requiere validación previa en Staging,
auditoría, respaldo y autorización del responsable técnico.

## Validación manual local

Usar exclusivamente la configuración de desarrollo local. En `backend`:

```bash
uv run alembic upgrade head
uv run python -m backend.cli.conciliar_convenios --simular --fecha-referencia 2026-10-08
uv run python -m backend.cli.conciliar_convenios --fecha-referencia 2026-10-08
uv run python -m backend.cli.conciliar_convenios --fecha-referencia 2026-10-08
```

La segunda ejecución real no debe duplicar transiciones. `--simular` calcula
cambios bajo lock pero revierte y no guarda bitácora. Sin fecha inyectada se usa
hoy en Bogotá. El comando devuelve 0 tras éxito y 1 tras fallo; argumentos
inválidos devuelven el código estándar de argparse.

El CLI permite ejecuciones reales con `--fecha-referencia` únicamente cuando
`settings.app_env` es `development` o `test`. En `staging`, `production` y
cualquier otro entorno, una fecha personalizada requiere `--simular`. Las
combinaciones no permitidas se rechazan antes de abrir una sesión de base de
datos, con un error operativo claro, sin credenciales y código de salida 2.
Las ejecuciones reales sin fecha personalizada continúan usando hoy en
`America/Bogota` en todos los entornos.

Con Docker se puede usar la base aislada creada para estas pruebas:

```bash
docker exec -e DATABASE_NAME=ori_manager_ciclo_vida_test -w /workspace/backend ori-manager-workspace-1 .venv/bin/python -m backend.cli.conciliar_convenios --simular --fecha-referencia 2026-10-08
```

Pruebas de frontend: `cd frontend && npm test`. El CI existente ejecuta estas
pruebas; no se agregó ningún job operativo al CI. Se validan permisos,
confirmación, doble clic, POST, errores y navegación con React Testing Library/jsdom.

La prueba manual en navegador se completó satisfactoriamente sobre la base
aislada `ori_manager_ciclo_vida_manual`. El convenio #294 recorrió
VIGENTE → POR_VENCER → FINALIZADO, con dos entradas de actor `SISTEMA` en la
bitácora. Se comprobó la idempotencia: repetir la conciliación no duplicó las
transiciones. Desde el convenio finalizado se inició la renovación tardía #3954,
que quedó EN_TRAMITE, con el mismo solicitante y el documento heredado del
convenio original.
