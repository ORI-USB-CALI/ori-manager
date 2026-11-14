# HT-16 — Contraparte por definir: auditoría correctiva del PR #180

Referencia: [incidencia #172](https://github.com/ORI-USB-CALI/ori-manager/issues/172),
[PR #180](https://github.com/ORI-USB-CALI/ori-manager/pull/180).
Rama: `feature/ht-16DesbloquearRevsDeContraprPorDefnr`.
Auditoría y cierre técnico: 14/11/2026, sobre `9c802e7`.
El inventario documental de octubre no contiene HT-16; este documento no asigna
un sprint ni cambia el estado oficial del backlog. Dependencias: HU-10, HU-12/13,
HU-14, HT-09 y las correcciones de HT-18 ya presentes en la rama.

## Hallazgos y causa raíz

| Hallazgo | Causa | Corrección |
|---|---|---|
| Catálogo incompatible y truncado | Se pedía `solo_activos=true` y se trataba `{items,total}` como arreglo; el hook existente solo leía 100 aliados | Reutilizar `useAliados(true, enabled)`, usar `activo=true`, recorrer las páginas y renderizar `items` |
| Reutilización de avales incompatibles | Se excluía `aliado_id` de todos los snapshots manuales | Comparar versión, RJ1 y RJ2; excepción inicial explícita y auditada; rectificación vuelve a Elaboración |
| Identidad mutable con el mismo ID | El FK no detectaba modificaciones de razón social o identificación del registro compartido | Congelar `aliado_identidad`, verificarla en RJ1/RJ2, envío y reenvío; conservar huella de la asignación inicial |
| Carrera entre asignar y enviar | `actualizar()` leía sin bloqueo, mientras el envío sí bloqueaba | `SELECT FOR UPDATE` y `populate_existing` en ambos caminos, antes de verificar revisión pendiente |
| Reenvíos repetidos | Bloquear serializaba las peticiones, pero cada petición podía rotar otra vez el enlace | `expected_invitacion_id` obligatorio en HTTP y servicio, comprobado antes de revocar o enviar |
| Revisión manual sin invitación | El servicio hacía commit si no tenía enviador | Exigir correo y URL pública en el servicio, también para llamadas directas |
| Persistencia ambigua tras correo aceptado | El helper de correo ocultaba el commit y no distinguía su fallo | El servicio controla commit/rollback, responde 503 y registra correlación sin tokens |
| Ruff y cobertura insuficiente | Supresión EXE002 en un archivo Git 100644 y pruebas que reproducían el contrato HTTP equivocado | Retirar la supresión; verificar modos correctos y contratos reales; ampliar escenarios |

## Comportamiento y excepción de negocio

Los convenios manuales pueden seguir elaborándose y obtener RJ1/RJ2 mientras la
contraparte está **Por definir**, como permite HU-10. El envío permanece bloqueado
hasta seleccionar un aliado activo con nombre, tipo, identificación y correo válido.
Un aliado sin correo se puede guardar; no se puede invitar hasta completar su ficha.

Se mantiene una excepción limitada para **la primera asignación desde Por definir**
después del aval: la versión formal y ambos avales deben contener explícitamente
`aliado_id=null` y `aliado_identidad=null`; debe existir exactamente un cambio auditado
`null -> aliado actual` en esa versión y etapa, con evento `CONTRAPARTE_ASIGNADA`,
y la identidad actual debe coincidir con la huella SHA-256 auditada al asignar.
Todos los demás campos
congelados deben coincidir. Los snapshots permanecen inmutables. Un snapshot ausente
o sin `aliado_id` no demuestra que se avaló un proyecto sin contraparte y bloquea el
envío manual hasta obtener nuevos avales.

Esta excepción permite completar el flujo que originó #172; **no autoriza sustituir
una contraparte identificada**. Si ya había un aliado y se elige otro, el guardado
registra `CONTRAPARTE_RECTIFICADA`, conserva los avales anteriores y vuelve a
**ELABORACION** con una transición en el historial. Al finalizar se crea la versión
que incorpora la nueva contraparte y se abre otra ronda RJ1/RJ2. Sin ambas nuevas
aprobaciones no se puede enviar. Guardar repetidamente el mismo aliado es inocuo;
si la identidad no coincide con la versión ni tiene asignación inicial verificable,
el guardado permite recuperar el convenio volviendo a Elaboración.

`aliado_identidad` es un objeto JSON con `nombre`, `tipo`, `tipo_identificacion`,
`identificacion` y `digito_verificacion` (nulo si no corresponde). Se captura en
versiones y revisiones jurídicas a partir del aliado persistido, no de una relación
ORM potencialmente desactualizada. `CAMPOS_SNAPSHOT` tiene ahora quince campos.
La huella inicial se añade a la bitácora existente como campo
`aliado_identidad_sha256`, con actor, evento, etapa y versión, en la misma transacción
de asignación. No se reescriben los snapshots aprobados ni se añade una migración.

RJ1 y RJ2 comprueban identidad tanto en la revisión recibida como en la versión
actual; RJ2 comprueba además el primer aval. El envío compara versión y ambos avales;
el reenvío también verifica identidad. Si cambia cualquiera de esos cinco datos,
incluso conservando el ID, se responde 409 con
`detail.codigo=IDENTIDAD_ALIADO_CAMBIADA` y un `message` que exige nuevos avales.
Correo, teléfono y otros datos de contacto no forman parte de la identidad congelada.

Para recuperar un convenio habilitado para contraparte, la UI ofrece **Volver a
Elaboración para revisar la identidad** después de ese error. La acción funciona
para manuales y solicitudes, verifica versión, permisos y ausencia de revisión
pendiente, y solo permite reabrir si la identidad de la versión es incompatible.
No cambia el aliado ni la solicitud. Finalizar nuevamente crea una versión con la
identidad actual e inicia RJ1/RJ2. Un snapshot sin `aliado_identidad` exige esa nueva
versión; no se completa el JSON histórico. Si la discrepancia se detecta durante
RJ1/RJ2, se conserva la revisión pendiente y se utiliza la devolución a Elaboración
con observaciones existente.

La lectura de identidad mantiene un bloqueo compartido `FOR SHARE` del aliado hasta
el commit de la operación. Así una edición concurrente espera y no puede cambiar la
identidad entre validar y confirmar. Se conserva la edición normal del catálogo
fuera de esa transacción; no existe un veto global por tener convenios aprobados.

Mientras exista una revisión de contraparte pendiente no se permite cambiar su
aliado, ni siquiera mediante una petición repetida. Cambiar objeto, fechas u otros
datos congelados en esa etapa continúa prohibido. El flujo `SOLICITUD` mantiene su
Solicitante autenticado, sus notificaciones internas y la prohibición de cambiar
aliado desde este PATCH. No se habilitan enlaces públicos para solicitudes.

## UI y catálogo

El detalle carga `GET /api/aliados?limite=100&activo=true`, seguido de
`&desplazamiento=100`, etc., hasta cubrir `total`. Conserva los tipos `Aliado` y el
resultado `{items,total}` usado por Nuevo y Elaboración. El selector espera a que
termine la carga completa; informa error con reintento y catálogo vacío. Una página
vacía antes de alcanzar `total` informa que el catálogo cambió y pide reintentar.
La contraparte actual sigue visible aunque esté inactiva o ausente del catálogo.
El botón de envío depende además de los requisitos del aliado y de la etapa.

Al rectificar, la UI avisa que se requieren nuevos avales y muestra el acceso a
Elaboración. Ante conflictos o persistencia no confirmada, recarga el historial.
El visor PDF, la navegación y los permisos de HT-18 se conservan.

## API, permisos y errores

| Operación | Contrato y resultado |
|---|---|
| `PATCH /api/convenios/{id}` | `{aliado_id: id}`. 200 al asignar, rectificar o repetir un guardado válido. En contraparte solo admite este campo y origen manual |
| `POST /api/convenios/{id}/revision-contraparte/enviar` | `{expected_version: numero}`. 201 solo después de confirmar revisión e invitación manual, o revisión/notificación autenticada para solicitudes |
| `POST /api/convenios/{id}/revision-contraparte/{revision}/reenviar-invitacion` | UI: `{expected_invitacion_id: ultimo_id}`. 200 con `{id,enviado_en}`; 409 si otra operación ya reemplazó esa invitación |
| `POST /api/convenios/{id}/revision-juridica/reabrir-por-identidad` | `{expected_version: numero}`. 200: vuelve a Elaboración por identidad incompatible; 409 si coincide, cambió la versión, no está en etapa de contraparte o existe revisión pendiente |
| `GET /api/convenios/{id}/revisiones` | Conserva avales, transiciones e invitaciones anteriores con actor, fechas, revocación y uso |

Gestor ORI y Administrador ORI conservan los permisos centralizados de edición y
gestión de contraparte. Revisor ORI y solicitantes reciben 403 en mutaciones; sin
sesión se conserva 401. No se amplían permisos de lectura ni se alteran las
decisiones autenticadas/públicas de HU-14.

- 404: convenio o revisión inexistente.
- 409: etapa/versión incompatible, revisión pendiente duplicada, avales incompatibles,
  contraparte Por definir o sin requisitos de envío, invitación reemplazada.
- 422: aliado inexistente/inactivo al guardar, asignación nula en esa etapa,
  campos o cuerpos inválidos; reenvío sin cuerpo, sin `expected_invitacion_id`,
  con nulo, cero u otro valor inválido.
- 502: fallo del proveedor al entregar el correo; se revierte la operación.
- 503: falta enviador/URL pública o no se confirmó el commit después de aceptar correo.

El cuerpo de reenvío y **`expected_invitacion_id` son obligatorios**, sin ruta de
compatibilidad. El esquema prohíbe campos adicionales y exige un entero positivo.
Repetir o concurrir con el mismo ID produce un solo nuevo correo y luego 409.
Un reenvío deliberado posterior debe utilizar el nuevo ID consultado en el historial.
La UI siempre lo envía; si no dispone de una invitación, informa error sin emitir
una petición incompleta. No hay reintentos automáticos de mutaciones en la UI.

## Correo, transacción y recuperación

El servicio mantiene el bloqueo del convenio durante la entrega. Primero escribe
revisión/invitación sin confirmar; luego entrega el correo y confirma todo. El
helper de entrega ya no hace commit. Un rechazo confirmado revierte revisión,
invitación y su auditoría transaccional. En un reenvío fallido también se revierte
la revocación: la invitación anterior conserva exactamente su disponibilidad previa.

Cada entrega registra `intento_id`, convenio, revisión, invitación y actor. Eventos:
`contraparte_correo_intento`, `contraparte_correo_fallido`,
`contraparte_correo_aceptado`, `contraparte_correo_confirmado` y
`contraparte_correo_commit_no_confirmado`. No contienen destinatario, token, mensaje
ni parámetros de la excepción SQL. Conservar logs del servicio; habilitar INFO en
el logger `backend.services.convenios` para ver también intentos y éxitos. Los fallos
y commits no confirmados se registran en WARNING/ERROR. Las invitaciones confirmadas
y la bitácora conservan la evidencia de negocio. Los intentos revertidos se conservan
en logs, no como revisiones ficticias en base de datos.

**Límite distribuido del MVP:** correo y PostgreSQL no comparten transacción. Si el
proveedor acepta y luego falla el commit, el correo puede llegar con enlace inválido.
Se devuelve 503, se intenta rollback y se exige recargar el historial antes de
reintentar. Si el commit realmente se confirmó pero se perdió su respuesta, el
historial/índice único evita crear otra revisión; si se revirtió, el reintento crea
un token nuevo. En reenvío se compara el ID vigente. Un timeout del proveedor también
puede significar aceptación sin respuesta; no se garantiza un único correo físico.

Recuperación operativa:

1. Consultar historial y correlacionar logs por convenio, actor e intento; no reenviar
   a ciegas tras un 503. La UI vuelve a consultar el estado.
2. Si existe revisión confirmada, usar su invitación actual; reenviar expresamente
   con su ID si hace falta. Si no existe, repetir el envío una vez restablecido el servicio.
3. Ante identidad incompatible, utilizar la reapertura por identidad (o guardar la
   contraparte correcta en manuales), completar Elaboración y obtener otra ronda
   RJ1/RJ2; no editar snapshots ni reutilizar la excepción inicial después de cambiar
   la identidad elegida.
4. Conservar las invitaciones anteriores: quedan revocadas al confirmarse su reemplazo.

La evolución recomendada si se necesita entrega recuperable automáticamente es un
**outbox transaccional** con estado de entrega, trabajo idempotente y conciliación del
proveedor. La revisión no debe presentarse como enviada hasta confirmar la entrega.
Requeriría almacenar de forma protegida lo necesario para reintentar el enlace y
añadir un worker y política de expiración; no se introduce esa infraestructura en
este MVP. La solución actual prioriza no habilitar revisiones sin invitación válida.

## Pruebas y evidencias

| Criterio de HT-16 | Cobertura verificable |
|---|---|
| CA-01 | Por definir, aliado inactivo, inexistente, sin correo, correo inválido y requisitos de envío |
| CA-02 | Asignación/rectificación, Gestor/Admin, denegación a Revisor/solicitantes y auditoría de anterior/nuevo |
| CA-03 | Estados UI, errores 409/502/503, rollback sin revisión fantasma y sin revocar el enlace previo |
| CA-04 | Comparación de versión/RJ1/RJ2, asignación inicial auditada, rectificación con nueva ronda, metadatos congelados |
| CA-05 | Reintentos, POST duplicado, ID de invitación esperado, carreras reales y logs por intento |
| CA-06 | Regresión de manual/solicitud, HU-10/HU-14 y navegación/visor de HT-18 |

Archivos de pruebas: `backend/tests/test_ht16_contraparte_por_definir.py`,
`backend/tests/test_ht16_concurrencia.py`, suites de HU-10/12/13/14 y los tests de
detalle, creación, elaboración, contraparte, rutas por rol y visor PDF del frontend.
La cobertura se evalúa por escenarios observables; no se atribuye un porcentaje de
líneas ni una aceptación UAT a estas ejecuciones locales.

La base de pruebas es `ori_manager_ht16_audit_20261114`, creada en PostgreSQL local
y migrada desde cero a `0b2fb1bed5b2`; no se migró producción.

Ejecuciones locales del cierre, 14/11/2026:

| Ejecución | Resultado |
|---|---|
| Backend, 11 archivos de HT-16 y HU-10/12/13/14 | **287 passed**, 73,79 s; incluye 67 casos HT-16, de los cuales cinco comprueban concurrencia PostgreSQL |
| Reverificación HT-16 tras endurecer la condición inicial de ambos nulos | **67 passed**, 23,96 s |
| HU-31 sobre el código de cierre | **49 passed, 47 errors**, 45,37 s; mismos errores previos de fixture, sin cambios en HU-31 |
| Frontend, 11 archivos con HT-18, HU-10/14 e historial de versión | **199 passed**, 336,34 s; incluye 21 pruebas del detalle |
| TypeScript, ESLint y build de frontend | Pasan; build mantiene el aviso de tamaño del bundle |
| Ruff completo sobre `src`, `tests` y `migrations` con modos Git 100644 | **All checks passed!**; sin nuevas supresiones |
| `git diff --check` | Pasa |

Evidencia conservada de la auditoría anterior: backend completo **2806 passed,
47 errors**, 449,59 s; todos los errores pertenecen al fixture manual de HU-31.
Su reproducción sobre copia limpia del HEAD original `9c802e7` obtuvo **49 passed
y los mismos 47 errors**, 37,22 s. No se atribuye esa ejecución global al código
definitivo ni se presenta como verde.

Los 47 errores de HU-31 no son regresiones de HT-16: su fixture fija
`FECHA_REFERENCIA=2026-10-07`, crea un manual que vence 30 días después y solo
congela el reloj de renovaciones. La validación de creación usa la fecha real,
14/11/2026, por lo que rechaza el vencimiento 06/11/2026. Se reprodujo con los
mismos 47 identificadores de prueba sobre el código original exportado mediante
`git archive HEAD`; se verificó que el módulo cargado procediera de esa copia.
No se modifica HU-31 ni se presenta la suite completa como verde.

Comando del backend final (desde `backend`, con la base local aislada en el entorno):

```sh
.venv/bin/pytest tests/test_ht16_contraparte_por_definir.py tests/test_ht16_concurrencia.py tests/test_hu10_convenio_manual.py tests/test_hu10_exportacion.py tests/test_hu12_elaboracion.py tests/test_hu12_editor_versiones.py tests/test_hu13_revision.py tests/test_hu13_acciones.py tests/test_hu13_historial.py tests/test_hu14_revision_contraparte.py tests/test_hu14_revision_contraparte_publica.py -q --tb=short --junitxml=/tmp/ori-ht16-cierre-backend.xml
```

Comando de regresión frontend (desde `frontend`):

```sh
npm test -- --pool=threads --maxWorkers=2 src/pages/ConvenioDetallePage.test.tsx src/pages/ConvenioVersionPage.test.tsx src/pages/ConvenioNuevoPage.test.tsx src/pages/ConvenioElaboracionPage.test.tsx src/pages/RevisionContrapartePage.test.tsx src/pages/RevisionContrapartePublicaPage.test.tsx src/app/router.permisos.test.tsx src/components/DocumentoPreviewModal.test.tsx src/components/SoportesConvenio.test.tsx src/pages/BitacoraPage.test.tsx src/index.responsive.test.ts
npm run typecheck
npm run lint
npm run build
```

El montaje Windows causó un timeout de arranque con el pool `forks`; la ejecución
con `threads` pasó sin cambiar la configuración de pruebas del repositorio. Ruff
se ejecutó sobre una copia Linux del contenido final, con permisos 0644 para evitar
el EXE002 artificial del volumen Windows; no se ignoró la regla en el control final.
Los logs y el XML se conservan localmente en `backend/var/ht16-audit/` (ignorado por
Git), además de `/tmp/ori-ht16-*` en el contenedor. El cierre se publica mediante
commit y push a la rama de HT-16. Los resultados de esta ficha son locales; el
estado del CI remoto debe verificarse en el PR después del push. Esta evidencia
no sustituye QA/UAT ni la aprobación del líder técnico para merge.

La [descripción completa del PR](../development/pr-180-ht16-cierre.md) queda versionada
para actualización manual: al reintentar la edición durante el cierre, el conector
volvió a devolver GitHub 403 `Resource not accessible by integration`. En la auditoría
previa también se verificó la ausencia de GitHub CLI y de sesiones de navegador.
No se presenta la descripción remota como actualizada sin confirmar su publicación.

## Archivos de la corrección y justificación

| Archivo | Motivo |
|---|---|
| `frontend/src/pages/epica02.ts` | Reutilizar el catálogo tipado y completar su paginación conservando `{items,total}` |
| `frontend/src/pages/ConvenioDetallePage.tsx` | Integración real, estados de catálogo, contraparte visible, aviso de nuevos avales, reenvío obligatorio con ID y reapertura por identidad |
| `frontend/src/pages/ConvenioVersionPage.tsx` | Etiqueta de la identidad jurídica almacenada en la versión histórica |
| `frontend/src/pages/ConvenioDetallePage.test.tsx` | Respuestas HTTP reales, segunda página, carga/error/vacío, rectificación y reenvío |
| `backend/src/backend/services/convenios.py` | Identidad jurídica, excepción inicial auditada, bloqueo, rectificación, correo obligatorio, rollback y correlación de intentos |
| `backend/src/backend/services/contraparte_externa.py` | Entrega de correo sin commit oculto; el servicio controla la transacción completa |
| `backend/src/backend/services/identidad_aliado.py` | Comparte la lectura bloqueada de identidad, su huella y la excepción inicial con el enlace público y la recuperación |
| `backend/src/backend/schemas/convenio.py` | Cuerpo estricto de reenvío con `expected_invitacion_id` obligatorio |
| `backend/src/backend/api/routers/convenios.py` | Delegar validación bajo bloqueo, mapear errores 503 y propagar la precondición de reenvío |
| `backend/tests/test_ht16_contraparte_por_definir.py` | Corregir expectativa de rectificación, retirar Ruff innecesario y agregar integridad, permisos, fallos y recuperación |
| `backend/tests/test_ht16_concurrencia.py` | Comprobar carreras con dos sesiones reales y estado precargado, sin mocks de bloqueos |
| `backend/tests/test_hu12_elaboracion.py`, `backend/tests/test_hu14_revision_contraparte_publica.py` | Verificar el nuevo campo del snapshot y el cuerpo obligatorio del reenvío; no se relajan expectativas ajenas |
| `docs/README.md`, `docs/hu/hu-14-contraparte.md`, `docs/development/pr-180-ht16-cierre.md` y este documento | Índice, contrato, descripción del PR, límites, pruebas y recuperación según la política documental |

## Corrección residual posterior a `b46b4d9`: identidad al utilizar el enlace público

La revisión de GitHub detectó que, después de invitar, `_contexto()` solo verificaba
token, etapa y versión. Una edición posterior del aliado podía dejar un enlace
utilizable para una identidad distinta de la avalada. Se conserva el cierre anterior
y se añade la comprobación de identidad antes de devolver contenido o aceptar una
aprobación/devolución pública.

La lectura de identidad y la comprobación de la asignación inicial se comparten en
`services/identidad_aliado.py`, evitando dependencias circulares entre servicios.
El enlace compara la identidad persistida con la versión efectivamente enviada y
los dos avales de la misma ronda, resueltos y aprobados por revisores distintos.
Para Por definir exige los tres snapshots expresamente nulos y la asignación/huella
auditadas de esa versión. Una edición posterior incompatible invalida el uso del
enlace; cambiar solo correo, teléfono, dirección o ciudad mantiene su validez.
El destinatario de una invitación existente no se sustituye al editar el correo del
catálogo: continúa siendo el registrado en la invitación.

El acceso, la aprobación y la devolución rechazados devuelven exclusivamente
**400 `{"detail":{"codigo":"ENLACE_NO_DISPONIBLE"}}`**, igual que un enlace revocado.
No se revelan nombre, identificación, identidad anterior/actual ni motivo interno.
El rechazo público no modifica revisiones, invitaciones, observaciones ni avales.

Orden de bloqueo: convenio, revisión, invitación y aliado. Acceder utiliza bloqueos
compartidos para mantener consistente el contenido hasta construir la respuesta;
aprobar/devolver y recuperar usan `FOR UPDATE` en convenio/revisión/invitación.
Todos mantienen `FOR SHARE` sobre el aliado hasta terminar la transacción y releen
el estado con `populate_existing`. Una edición ganadora se relee antes de permitir
el uso; una operación pública ganadora impide editar identidad durante su validación
y decisión. Fuera de esas transacciones se conserva la edición normal del catálogo.

### Recuperación administrativa de una invitación ya enviada

`POST /api/convenios/{id}/revision-contraparte/{revision_id}/invalidar-por-identidad`
exige `{expected_version: numero, expected_invitacion_id: ultimo_id}`. El esquema
prohíbe campos adicionales. Solo Gestor ORI y Administrador ORI, con el permiso
centralizado de gestionar contraparte, pueden operar sobre una revisión manual
pendiente en etapa de contraparte cuya identidad ya no esté autorizada/verificable.
El servicio también comprueba el rol para llamadas directas.

La operación bloquea y relee los registros; valida versión, revisión e invitación
esperadas antes de modificar nada. En un único commit:

1. Revoca todas las invitaciones activas de esa revisión, sin consumirlas ni cambiar
   las revocaciones/consumos históricos.
2. Resuelve la revisión como `RESUELTA / DEVUELTA`, con `resuelta_por_id` del gestor o
   administrador, fecha y versión enviada. Es una **devolución administrativa** por
   identidad incompatible; no simula una decisión externa ni crea una respuesta,
   firma u observaciones atribuidas a la contraparte.
3. Registra una transición explícita a Elaboración y el evento humano
   `CONTRAPARTE_INVALIDADA_IDENTIDAD` para revisión/convenio; cada revocación añade
   su auditoría con actor, rol, etapa, versión e instante, sin token ni mensaje.

Respuesta 200 con el convenio actualizado. 401 sin sesión; 403 sin permiso; 404 si
no existe convenio/revisión; 422 por cuerpo inválido; 409 si cambió la versión o
invitación, no hay revisión manual pendiente o la identidad sigue autorizada.
Repetir/concurrir con la misma recuperación produce un solo cierre y luego 409.
Un error de persistencia revierte también revocaciones, transición y auditoría.

La UI ofrece **Recuperar por cambio de identidad** durante la revisión manual y
exige confirmar las consecuencias. Envía los identificadores que el usuario vio,
conservados al abrir la confirmación. Rechazos del servidor conservan el estado y
recargan el historial. Después de recuperar, el usuario completa Elaboración y
obtiene una nueva versión y ambos RJ1/RJ2 antes de generar otra invitación. Los
avales anteriores y enlaces revocados permanecen como historial.

Las pruebas nuevas cubren los cinco datos de identidad tras enviar, acceso,
aprobación/devolución, ambos tipos de asignación, cada snapshot, datos de contacto,
permisos, precondiciones, recuperación/reintentos/rollback y nuevas rondas. Las
carreras PostgreSQL comprueban ambos órdenes entre editar y usar el enlace, dos
recuperaciones simultáneas y recuperación frente a las tres operaciones públicas.
HU-31 permanece fuera del cambio.

Evidencia local de esta corrección residual (14/11/2026), sobre el cierre `b46b4d9`:

| Validación | Resultado |
|---|---|
| HT-16 y regresiones de HU-10/12/13/14, mismos once archivos del cierre | **361 passed**, 101,46 s; incluye 141 casos HT-16, 15 de concurrencia PostgreSQL |
| Detalle, contraparte pública/autenticada, rutas por rol y visor PDF | **134 passed**, 128,13 s; cinco archivos, 23 pruebas del detalle |
| Ruff completo de backend | **All checks passed!** sobre copia Linux 100644, sin supresiones nuevas |
| TypeScript, ESLint y build | Pasan; se conserva el aviso de tamaño del bundle |
| `git diff --check` | Pasa |

Comando backend: el mismo listado de once archivos documentado arriba, con JUnit
en `/tmp/ori-ht16-publica-regresion.xml`. Comando frontend:

```sh
npm test -- --pool=threads --maxWorkers=2 src/pages/ConvenioDetallePage.test.tsx src/pages/RevisionContrapartePublicaPage.test.tsx src/pages/RevisionContrapartePage.test.tsx src/app/router.permisos.test.tsx src/components/DocumentoPreviewModal.test.tsx
```

Logs `ori-ht16-publica-*` y JUnit se conservan en `backend/var/ht16-audit/`, ignorado
por Git. No se vuelve a atribuir la ejecución histórica global a este cambio ni se
modifican los 47 errores conocidos de HU-31. Sin migraciones, dependencias nuevas,
reescritura de avales ni modificaciones de producción. Como toda lectura web, una
respuesta ya entregada no se puede retirar; cada uso posterior del enlace vuelve a
verificar identidad, y una recuperación confirmada deja los enlaces revocados de
forma permanente. La edición del aliado permanece disponible fuera de la operación.

## Integración de auditoría HU-18 posterior a `2a179e5`

GitHub Actions detectó dos construcciones directas de registros de auditoría en
el servicio de convenios: la huella inicial y cada revocación administrativa.
Se sustituyen por `registrar_huella_identidad_inicial` y
`registrar_revocacion_por_identidad`, funciones explícitas de `services/bitacora.py`.
Ambas reutilizan `_fila` y la inserción central en la conexión de la transacción
existente, sin flush, commit ni rollback propios. El servicio revierte el negocio
si falla esa inserción o su commit.

La primera función solo admite una huella SHA-256 hexadecimal de 64 caracteres;
la segunda recibe únicamente ID de invitación e instante de revocación. Los campos,
contextos y eventos son fijos: no hay una interfaz para serializar invitaciones,
identidades o tokens arbitrarios. Se mantienen actor, rol, evento, etapa, versión,
ejecución humana y fecha; para revocaciones, la fecha auditada coincide con el
instante del cambio. No se añaden invitaciones a `ENTIDADES_AUDITADAS`.

El test arquitectónico `test_ningun_modulo_escribe_la_bitacora_a_mano` permanece
intacto. Se amplían las comprobaciones de metadatos y la prueba de rollback de la
asignación inicial; las pruebas de recuperación siguen verificando una evidencia
por invitación y rollback de toda la operación. No se cambia el funcionamiento del
enlace, snapshots o recuperación. HU-31 permanece sin modificaciones; sus fixtures
de fechas vencidas y la reproducción independiente documentada arriba no dependen
de estas dos funciones, que no intervienen en creación/renovación de HU-31.

Validación local: **209 pruebas aprobadas**, 69,55 s, ejecutando exclusivamente
`test_hu18_registro_automatico.py`, `test_ht16_contraparte_por_definir.py`,
`test_ht16_concurrencia.py` y `test_hu14_revision_contraparte_publica.py`.
Ruff completo pasa sobre copia Linux 100644, sin supresiones nuevas;
`git diff --check` pasa. Logs y JUnit `ori-ht16-hu18-*` se conservan en
`backend/var/ht16-audit/`, fuera del commit.
La comprobación separada de HU-31 obtuvo **49 aprobadas y 47 errores**, 55,88 s:
los 47 identificadores coinciden exactamente con la reproducción del código base.
Ni HU-31 ni el test arquitectónico de HU-18 tienen modificaciones en este commit.

## Compatibilidad, alcance y reversión

No se añaden dependencias, tablas, columnas ni migraciones. `CAMPOS_SNAPSHOT` y
`_snapshot_de` incorporan `aliado_identidad`; `_datos_difieren` conserva su comparación
de los campos congelados y las validaciones jurídicas exigen además la identidad.
La excepción se limita a la asignación inicial manual y nunca reescribe los JSONB.
El cuerpo de reenvío obligatorio sustituye la compatibilidad opcional de la auditoría
anterior: no existen clientes productivos que requieran preservarla.
Se retiró la supresión Ruff del
test; los modos Git de los Python siguen siendo 100644. En el montaje Windows,
EXE002 puede depender del permiso ejecutable aparente; el control completo de Ruff
se realiza además sobre una copia Linux de los archivos con sus modos Git.

Para revertir, retirar juntos código/UI/documentación de esta corrección mediante
un commit revisado. No hay downgrade de esquema. Conservar auditorías, invitaciones
y nuevas rondas ya generadas. Volver al código anterior reintroduciría la exclusión
general de contraparte y la ruta de revisión sin correo; no es una recuperación
segura para continuar envíos. Hasta corregirlo, suspender esos envíos y conservar el
historial en lugar de reescribir aprobaciones.

Los cambios previos de HT-18 forman parte del PR auditado; esta corrección no edita
sus componentes de visor, tablas, bitácora ni rutas. El commit y push del cierre están
autorizados después de validar pruebas y alcance. No se realiza merge, despliegue
ni modificación de staging o producción; el merge a `develop` corresponde al líder técnico.
