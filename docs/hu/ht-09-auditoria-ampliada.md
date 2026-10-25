# HT-09 — Información y autoría de la bitácora de auditoría

Referencia: [PR #149](https://github.com/ORI-USB-CALI/ori-manager/pull/149),
[QA #140](https://github.com/ORI-USB-CALI/ori-manager/issues/140) y dependencia
[HT-13 / PR #148](https://github.com/ORI-USB-CALI/ori-manager/pull/148).
Esta ficha describe el contrato técnico de la revisión; no acredita aceptación QA,
despliegue ni cierre de issues.

## Git y dependencia verificados

El trabajo comienza sin modificaciones locales, en
`feature/ht-09-completar-la-informacion-y-autoria-de-la-bitacora-de-auditoria`,
HEAD `c2d5a80`. El PR #149 tiene base `develop` (`f046d1b`). La punta publicada
de HT-13 es `5d7d83b`, ya incorporada en HEAD por `c2d5a80`; los archivos del
editor y sus pruebas coinciden con esa punta. No se necesita sincronización
adicional. No se cambió `develop` ni se hizo merge, commit o push en esta revisión.

Si la dependencia vuelve a avanzar, comparar su punta con HT-09 antes de integrar;
conservar primero cualquier trabajo local y revisar el diff. La sincronización
debe acordarse con el líder técnico, sin sobrescribir archivos ni publicar cambios
automáticamente.

## Criterios de aceptación CA-01 a CA-08

Síntesis técnica de los criterios del PR y del contrato funcional aprobado:

| Criterio | Contrato y evidencia prevista |
|---|---|
| CA-01 — Etapa y versión | Columnas propias cuando aplican. Creación de convenio: Elaboración/V1; corrección jurídica: etapa jurídica y versión resultante; formalización HT-13: versión generada o reutilizada. Una solicitud sin convenio no recibe una etapa o versión formal inventada. |
| CA-02 — Originador | `usuario_id` identifica quién inició la operación; `rol` conserva el rol con que actuó. No se sustituye por «Sistema» en efectos derivados de una acción humana. |
| CA-03 — Ejecución automática | `ejecucion` distingue el cambio humano del automático. Un proceso autónomo admite originador nulo; un automático con originador conocido conserva su usuario y rol. La radicación sigue siendo humana y sus efectos se declaran automáticos por campo. |
| CA-04 — Responsable | `responsable_id` utiliza únicamente una asignación verificable del contexto de la operación; no deriva siempre del creador ni del originador. Sin asignación queda NULL. |
| CA-05 — Contexto funcional | Evento estructurado y descripción funcional. Se conservan `BORRADOR_GUARDADO`, `VERSION_GENERADA` y `VERSION_REUTILIZADA`; la radicación conserva `SOLICITUD_RADICADA` o `SOLICITUD_RERADICADA`. |
| CA-06 — Consulta | API y vista muestran originador, naturaleza, responsable, evento, etapa y versión. Un usuario conocido puede figurar con naturaleza automática. Lo no disponible o histórico se muestra sin fabricar información. |
| CA-07 — Histórico | Las columnas nuevas admiten NULL. La migración no rellena ni reclasifica registros previos. La revisión tampoco reescribe auditorías ya persistidas. |
| CA-08 — Integridad y seguridad | La auditoría se inserta en la transacción de negocio; el rollback elimina también sus entradas. Se conserva la redacción de contraseñas, hashes de tokens, firmas y documentos, la inmutabilidad y los permisos de HU-18. |

## Reglas RN-01 a RN-08

Matriz técnica de aplicación, sin añadir asignaciones institucionales:

| Regla | Aplicación soportada |
|---|---|
| RN-01 | Conservar el usuario originador y el rol de la operación, independientemente del ejecutor de sus efectos. |
| RN-02 | Declarar la naturaleza de ejecución por su semántica. Ejecutarse en el backend no convierte por sí solo una operación en automática. |
| RN-03 | **El responsable se registra cuando existe una asignación verificable.** Se distingue del originador y del creador histórico. |
| RN-04 | Asociar evento, etapa y versión del contexto real de la operación cuando sean aplicables; no usar la versión anterior para una versión recién generada ni la del convenio padre para una renovación hija. |
| RN-05 | Registrar dentro de la misma transacción, sin entradas huérfanas ni modificaciones de auditorías anteriores. No registrar diferencias inexistentes. |
| RN-06 | Mantener la protección de datos sensibles y contenido documental; registrar que cambiaron sin copiar sus valores. |
| RN-07 | No utilizar usuarios ficticios para procesos autónomos. El originador nulo se admite únicamente con ejecución explícita `AUTOMATICA`. |
| RN-08 | Conservar compatibilidad histórica, consulta y permisos de HU-18; los datos desconocidos permanecen nulos. |

## Columnas y semántica

La migración `9d53cf1dcef3`, posterior a `bca1bf4a042d` de HT-13, añade:

| Columna | Tipo | Significado |
|---|---|---|
| `evento` | VARCHAR(40), nullable | Identificador funcional independiente del texto de `contexto`. |
| `etapa` | VARCHAR(40), nullable | Código de etapa del contexto de la operación, cuando aplica. |
| `version` | INTEGER, nullable | Versión formal asociada, independiente de la revisión del borrador. |
| `ejecucion` | VARCHAR(20), nullable | `HUMANA`, `AUTOMATICA` o NULL para información no declarada/histórica. |
| `responsable_id` | INTEGER, nullable | FK a `usuario.id`, `ON DELETE RESTRICT`; asignación de negocio verificable. |

`usuario_id` pasa a nullable y conserva su FK. Los CHECK existentes exigen un valor
válido de ejecución y `usuario_id IS NOT NULL OR ejecucion IS NOT DISTINCT FROM
'AUTOMATICA'`. Así se permite AUTOMATICA con o sin originador; NULL/NULL no cumple.
No se añaden columnas adicionales en esta revisión: originador y ejecución ya
permiten expresar el contrato. Modelo y esquema de respuesta aclaran esa diferencia.

## Diagnóstico y mecanismo transaccional

Antes de esta revisión, `describir_accion()` clasificaba como humana toda la
transacción de radicación. `after_flush` aplicaba esa clasificación a los cambios
de estado y fechas. `describir_accion_automatica()` solo permitía un proceso sin
usuario, por lo que no expresaba directamente un automático con originador conocido.

Se conserva el mecanismo central de HU-18: historial ORM en `after_flush`, filas
por campo modificado, y `INSERT` directo mediante la misma conexión transaccional.
No se abren sesiones ni se confirman transacciones independientes para auditar.

`describir_cambios_automaticos(db, objeto, *campos)` captura la acción humana y
declara sus efectos para un objeto persistido de esa sesión y su próximo flush.
La marca conserva el contexto aunque después se declare otra acción sobre otro
objeto; no cambia globalmente la ejecución de todos los cambios pendientes.
Rechaza objetos de otra sesión, columnas inexistentes y acciones ambiguas para
el mismo objeto sin un flush intermedio. Varias marcas de la misma acción unen campos.
Las marcas se consumen al hacer flush y se limpian al cerrar o revertir la transacción.

Si hubo modificaciones reales se emite una entrada humana de evento, `UPDATE` con
`campo = NULL`, seguida de sus cambios por campo. Esto usa el contrato ya existente
de auditoría y diferencia el evento de negocio de sus efectos. No representa un
segundo cambio de estado ni crea una versión. Los campos marcados son automáticos;
los demás mantienen la naturaleza de su acción. Sin diferencias no se generan filas.

En radicación y re-radicación se marcan explícitamente `estado`, `fecha_radicacion`,
`fecha_recibido_ori` y la limpieza de `decidida_por_id`/`fecha_decision` cuando cambian.
Todos conservan originador, rol, instante, evento y descripción de la radicación.
El primer evento habitual queda así:

| Entrada | Originador | Ejecución | Campo |
|---|---|---|---|
| Radicó la solicitud | Solicitante autenticado | HUMANA | NULL (evento) |
| BORRADOR → RADICADA | El mismo solicitante | AUTOMATICA | `estado` |
| Fecha de radicación | El mismo solicitante | AUTOMATICA | `fecha_radicacion` |
| Fecha recibido ORI | El mismo solicitante | AUTOMATICA | `fecha_recibido_ori` |

`describir_accion_automatica(..., originador=usuario)` permite declarar una operación
automática con usuario conocido. Si se omite, no hereda al usuario autenticado de
la sesión: usuario y rol quedan nulos. El fallback de las mutaciones autenticadas
de HU-18 se conserva; los efectos automáticos requieren declaración explícita.
No se reclasifican indiscriminadamente aprobaciones, firmas u otros flujos ajenos
a los efectos identificados en QA #140.

## Responsable: referencias utilizadas y límites

Se revisaron los constructores de `responsable_id` y los consumidores de
`contexto_auditoria()` en convenios, firmas, actividades, evaluaciones, renovaciones
y solicitudes. Las asignaciones de dominio existentes no se cambian en esta revisión.

- Una operación sobre una revisión u observación concreta usa su `responsable_id`,
  comprobando que pertenece al convenio. Esta referencia tiene prioridad, incluso
  cuando es NULL; no se sustituye por el creador ni por otro ciclo.
- En las demás operaciones de convenio se consulta la última transición de
  `HistorialEtapa`, ordenada por fecha e ID. Solo se usa su responsable si su destino
  corresponde a la etapa actual. No se busca una asignación anterior para rellenar
  un NULL. La consulta y las cargas diferidas se hacen con `no_autoflush`, antes
  de declarar la nueva acción, para evitar persistir cambios con un contexto anterior.
- En creación e inicio de Elaboración y renovación, el servicio asigna explícitamente
  al usuario en el historial de entrada. Su auditoría puede utilizar esa asignación;
  no se generaliza a una responsabilidad administrativa permanente.
- Al radicar, el solicitante es un responsable verificable de su propia presentación:
  `_cargar_editable()` exige que sea el titular. En las decisiones de ORI, ser titular
  no lo convierte en responsable institucional: al no existir asignación, queda NULL.
- `creado_por_id` se conserva intacto como autor histórico. Las referencias al creador
  que otros flujos usan para destinatarios de correcciones no se reinterpretan como
  un responsable administrativo general ni se reescribe su historial.

El sistema no dispone de una asignación administrativa global separada del creador.
No se inventa tal asignación. Si negocio requiere otra, debe definir su fuente y
vigencia antes de incorporarla; tampoco se reconstruye retroactivamente por inferencia.

## API, permisos y visualización

`GET /api/auditoria` mantiene `auditoria.ver` y devuelve `{items, total}`. Cada item
incluye los campos de HU-18, `usuario` nullable, `rol` histórico, `evento`, `etapa`,
`version`, `ejecucion` y `responsable` nullable (usuario con ID, nombre y correo).
No se agregan rutas de escritura ni de borrado.

Conserva filtros `entidad`, `registro_id`, `usuario_id`, `rol`, `accion`, `desde`,
`hasta`, `orden=asc|desc`, `limite=1..100` y `desplazamiento>=0`. Sin sesión: 401;
sin permiso: 403; parámetros inválidos o intervalo invertido: 422. `usuario_id`
filtra al originador, incluyendo sus efectos automáticos, no a un supuesto ejecutor humano.

La vista actual ya muestra originador y naturaleza por separado: un automático
con originador conocido conserva su nombre; sin originador muestra «Proceso automático».
Lo histórico/no aplicable conserva los indicadores de ausencia existentes, sin
completar campos. Una entrada de evento `UPDATE` sin campo se muestra con campo vacío.
El caso mixto necesita comprobación manual en navegador con datos generados por la API.

## Migración y rollback conservador

El upgrade conserva filas anteriores y no rellena las columnas nuevas. Su esquema
no cambia en esta revisión. El downgrade original intentaba restaurar NOT NULL en
`usuario_id`, incompatible con los procesos autónomos legítimos. Además, eliminar
las columnas nuevas perdería contexto aunque todos los registros tuvieran usuario.

El downgrade ahora toma un bloqueo exclusivo transaccional de `auditoria` y comprueba
antes de cualquier DDL si existe originador NULL o información en alguna columna
de HT-09. Si existe, aborta con una explicación: **el esquema anterior no puede
preservar esa historia**. El bloqueo impide una escritura entre comprobación y DDL;
la transacción de Alembic debe revertirse y liberar el bloqueo ante el rechazo.
Solo se permite revertir si todas las filas son compatibles y las columnas a retirar
están vacías. No se borran filas, se inventan usuarios ni se reclasifican procesos.

Procedimiento seguro ante un bloqueo:

1. No forzar el downgrade ni hacer `stamp` para ocultar la incompatibilidad.
2. Coordinar escrituras y conservar un respaldo verificable del esquema y la
   auditoría completa, incluidas las columnas nuevas, referencias y versión Alembic.
3. Preferir una migración correctiva hacia adelante que conserve todos los registros
   y permita la compatibilidad de la aplicación necesaria.
4. Si se necesita recuperar un respaldo anterior, restaurarlo primero en un entorno
   aislado; conservar íntegra la base original y su historia posterior. Diseñar la
   recuperación y reconciliación sin eliminar auditorías antes de autorizar un corte.
5. Validar recuperación, integridad y permisos con el líder técnico. Un eventual
   rollback adicional de HT-13 requiere proteger también los borradores sin formalizar.

No se ejecutó downgrade, migración ni escritura sobre bases compartidas o persistentes.

## Pruebas y resultados de esta revisión

Se conserva la cobertura de HU-18 y se amplía
`backend/tests/test_ht09_auditoria_ampliada.py` con radicación real mediante API y
consulta como administrador, efectos por campo, originador conocido en automático,
aislamiento entre objetos/acciones, no-op, responsable de etapa distinto del creador,
ausencia de asignación, decisiones ORI, rechazo de asignaciones antiguas, protección
contra autoflush, rollback tras flush, redacción, versión inicial y versión de
corrección jurídica, persistencia de eventos HT-13 y límites del downgrade.

La incompatibilidad NOT NULL se reproduce en una **tabla temporal**, sin alterar
`auditoria`. El guard del downgrade tiene pruebas con operaciones Alembic sustituidas
para verificar que rechaza antes del DDL; esto no sustituye una prueba operativa de
restauración. El test automático sin originador se refuerza con un actor de sesión
presente para comprobar que no lo hereda.

Resultados locales, 24/10/2026:

| Validación | Resultado |
|---|---|
| Ruff completo | Correcto con el binario existente `.venv/bin/ruff` desde WSL; equivalente al check solicitado, sin instalar herramientas. |
| Sintaxis Python y grafo Alembic por AST | Correctos; una punta `9d53cf1dcef3`, sin antecesores ausentes. Es lectura estática, no ejecución de Alembic. |
| `npm run typecheck` / `npm run lint` | Correctos. |
| `npm test` | 25 archivos, 269/269 pruebas correctas, incluidas las regresiones del editor HT-13. |
| `npm run build` | Correcto; advertencia de chunk JavaScript mayor de 500 kB. |
| `git diff --check` | Correcto. |
| Pytest backend / `uv run alembic heads` | **Pendientes en DevContainer**. No se atribuye un resultado de ejecución a las pruebas añadidas. |

No hay `uv` local ni contenedores activos. El virtualenv es del DevContainer
(Python 3.13) y su intérprete no existe en el host/WSL; el Python alternativo no
dispone de FastAPI. No se instalaron herramientas globales ni se cambiaron conexiones.
No se considera suficiente Ruff o AST para acreditar integridad transaccional PostgreSQL.

Desde `/workspace/backend`, con el entorno de desarrollo/pruebas preparado y su
base local autorizada (no Staging/producción), ejecutar:

```sh
uv run pytest tests/test_ht09_auditoria_ampliada.py tests/test_hu18_registro_automatico.py tests/test_hu18_consulta_bitacora.py -q --tb=short
uv run ruff check .
uv run alembic heads
uv run pytest tests/test_ht13_guardar_avance.py tests/test_ht13_borrador_modelo.py tests/test_ht02_versiones_solicitud.py tests/test_hu12_editor_versiones.py tests/test_hu13_revision.py tests/test_hu13_acciones.py tests/test_hu14_revision_contraparte.py tests/test_hu15_revision_final_firmas.py tests/test_hu31_acciones_renovacion.py tests/test_ciclo_vida_convenios.py -q --tb=short
```

Pendientes manuales: radicación/re-radicación y consulta de los eventos mixtos,
validación del significado de las asignaciones de negocio con el responsable
funcional y un ensayo de recuperación desde respaldo en entorno aislado. Repetir CI
cuando se publiquen los cambios; la aprobación previa no certifica este diff local.
Los issues #140 y #144 permanecen abiertos; no se realizó commit, push ni merge.
