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

## Programador propuesto

Recomiendo GitHub Actions con runner efímero que ejecute el CLI directamente
contra PostgreSQL. El repositorio ya usa Actions para CI/migraciones y Python
3.13/uv. Los Blueprints actuales tienen backend Render `plan: free`, que se
duerme por inactividad y no ofrece one-off jobs ni shell. Un scheduler dentro
de Uvicorn no asegura ejecución diaria. [Restricciones oficiales de Render
Free](https://render.com/docs/free).

Render Cron es una alternativa operativa si se aprueba gasto: garantiza una
ejecución activa por servicio, pero exige pago mínimo de USD 1/mes por cron.
No se provisionó. [Documentación oficial de Render Cron](https://render.com/docs/cronjobs).

La propuesta en `conciliacion-convenios.workflow.yml.example` usa:

- `17 5 * * *`: 00:17 America/Bogota, todos los días (UTC-5).
- Ejecución manual `workflow_dispatch`, seleccionando ambiente.
- Programación para producción y checkout explícito de `main`; manual staging
  usa `develop`. Esto queda sujeto a aprobación; hoy no está activo.
- Variable del ambiente `CONCILIACION_CONVENIOS_HABILITADA=true`, ausente/desactivada
  por defecto. Si el environment exige revisión, también debe aprobarse el job.
- Concurrencia por ambiente, `cancel-in-progress: false`, timeout de 10 minutos.
- Tres intentos del CLI para errores transitorios, esperas de 2 y 4 segundos,
  nueva sesión y misma fecha por intento. Los errores permanentes no se reintentan.
- Checkout, dependencias y versiones alineadas con CI. No ejecuta migraciones,
  tests ni GET de negocio en el job operativo.

GitHub puede retrasar o descartar horarios bajo carga. El evento programado
requiere el workflow en la rama predeterminada y usa esa rama para cargarlo;
el checkout de código selecciona explícitamente main. En repositorios públicos
el scheduler puede deshabilitarse tras 60 días sin actividad. Por ello 00:17 es
un objetivo operativo, no una garantía de actualización a medianoche exacta.
[Reglas oficiales de schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Hasta que el job termine, el estado puede quedar desactualizado; las alertas ya
filtran fechas pasadas, pero HU-32 esperará FINALIZADO persistido. Si el negocio
exige una garantía estricta de hora, corresponde aprobar un programador con ese
nivel de servicio. El siguiente run recupera cambios pendientes usando su fecha
real de Bogotá; no necesita recorrer días omitidos.

## Configuración pendiente antes de automatizar

1. Aprobar programador, horario, ambiente inicial, tolerancia a retrasos y responsable
   operativo. Revisar cuota/minutos y límite de gasto de Actions: no asumir costo
   cero para cualquier plan ni habilitar consumo facturable sin aprobación.
2. Aprobar/desplegar la migración y el código por el proceso habitual; la validación
   local usó las bases aisladas `ori_manager_ciclo_vida_test` y
   `ori_manager_ciclo_vida_manual`, sin cambios en ambientes desplegados.
3. Crear una credencial de PostgreSQL específica para el job. Necesita SELECT de
   convenio, UPDATE de sus columnas estado/actualizado_en, INSERT de la bitácora
   y acceso a su secuencia. No necesita credenciales de correo/documentos, acceso
   humano ni capacidad de borrar datos. Migraciones usan otro principal.
4. Confirmar acceso externo, TLS y hostname/puerto compatibles con runners de
   GitHub. Cargar secrets `CONCILIACION_DATABASE_HOST`, `_PORT`, `_NAME`, `_USER`,
   `_PASSWORD` en cada environment. No reutilizar automáticamente credenciales
   de migración con mayores privilegios.
5. Antes de habilitar, ejecutar el CLI en simulación bajo control del responsable
   y revisar VENCIDO legado/fechas nulas. Este trabajo no ejecuta esa simulación
   contra staging/producción.
6. Tras aprobación, copiar la plantilla a `.github/workflows`, ajustar environments
   y branches a la configuración real y habilitar la variable solo en el ambiente
   autorizado. La plantilla no se activa por estar en docs.
7. Configurar notificación de workflows fallidos, responsable de revisar anomalías,
   conservación de logs (p. ej. 90 días si el plan lo permite) y revisión diaria
   de último run exitoso. Una ejecución sin cambios solo queda evidenciada en
   logs/Actions, no en filas de transición. No se configuraron notificaciones.

Después de agotar reintentos, el job falla y requiere revisión; no hace un bucle
indefinido. Se puede reejecutar manualmente con el CLI. Si se conoce un commit
ambiguo por desconexión, la repetición es segura: la bitácora y el estado se
confirmaron juntos o ninguno se confirmó. Una vez FINALIZADO, cambiar la fecha
de referencia no reactiva automáticamente el convenio.

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
