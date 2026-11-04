# HT-01 — Validación funcional de solicitudes

Validación del 13 de octubre de 2026 para revisión del PR #124 hacia `develop`.
Checkout inicial: `/home/deltec/Proyectos/ori-manager`, rama
`feature/ht-01-consistencia-retroalimentacion-solicitudes`, HEAD
`e0de331a336ffcac2ed20e01e0f9000cee952c27`, árbol limpio y rama cuatro commits
por delante de su seguimiento remoto. Se conserva el merge existente.

Al comenzar la revisión adicional de presentación, el diff ya incluía cinco
archivos, 630 líneas añadidas y 10 eliminadas. Tras estos ajustes incluye
también `SolicitudPage.tsx`, por lo que el resumen final comprende seis archivos.

## CA-03: investigación y límite de la conclusión

No se reprodujo el mensaje «Solicitud no encontrada» original de QA. No se
afirma haber identificado su causa ni haber demostrado la corrección de ese
incidente histórico. Faltan las peticiones/respuestas, la ruta y la sesión
del caso original para atribuirlo a API, autorización, navegación o caché.

El flujo actual tiene evidencia automatizada:

1. La bandeja y el detalle consultan una solicitud existente en `RADICADA`
   o `EN_ESTUDIO`.
2. La confirmación ejecuta `POST /api/solicitudes/recibidas/41/aceptar`.
3. El backend responde 200, persiste `APROBADA` y mantiene consultable el detalle
   y la bandeja. Aprobar no crea un convenio automáticamente.
4. El frontend escribe el resultado en `['solicitudes', 'recibidas', id]` e
   invalida detalle y bandejas. La respuesta se muestra incluso con el refetch
   del detalle demorado.
5. La consulta posterior mantiene `APROBADA`; desaparecen Aprobar, Rechazar y
   Devolver, y aparece Iniciar elaboración. Volver consulta nuevamente la
   bandeja y muestra Aprobada.
6. Las pruebas verifican la secuencia HTTP completa y las rutas: no hay
   consultas incorrectas, navegación a rutas inexistentes ni mensajes de 404.

La consulta backend de recibidas excluye únicamente `BORRADOR`. La aprobación
retorna `obtener_recibida`, sin aplicar la visibilidad del portal Solicitante
al Gestor. Las claves de consulta e invalidación coinciden. No se encontró un
defecto actual en esos puntos; se conserva el cambio de caché de HT-01.

En un experimento local se retiró temporalmente únicamente `setQueryData`:
las dos pruebas con refetch demorado fallaron al esperar `APROBADA`, dejando
el estado anterior visible. Se restauró automáticamente el archivo y se
volvieron a ejecutar las nueve pruebas con éxito. Esto demuestra la protección
de la escritura de caché previa, **no reproduce el 404 de QA**.

Gestor ORI y Administrador ORI conservan la gestión de recibidas. Revisor ORI
conserva sus permisos actuales y las decisiones están prohibidas para ese rol.
Un reporte que atribuya esa operación a Revisor ORI requeriría aclarar la sesión
utilizada; no autoriza ampliar permisos.

## CA-01 y CA-02

- Se adapta la prueba de rechazo para decidir como Gestor y consultar después
  como Solicitante, comprobando identidad, estado y motivo exacto.
- Se verifican las tres decisiones desde ambos estados pendientes, leyendo
  PostgreSQL nuevamente y comparando respuesta, detalle ORI, bandeja ORI,
  detalle propio y bandeja propia. Un tercero sin relación obtiene 404 al
  consultar el detalle propio y no ve la solicitud en su bandeja.
- El portal Solicitante se prueba con caché vacía, los hooks y el cliente HTTP
  reales y respuestas HTTP simuladas: muestra rechazo, devolución y las
  observaciones anteriores en `RADICADA`, `EN_ESTUDIO`, `APROBADA` y `RECHAZADA`.
- En ORI, Decisión ORI muestra el motivo de rechazo solo en `RECHAZADA` y las
  observaciones de devolución solo en `DEVUELTA`. Si existen observaciones y
  el estado ya no es `DEVUELTA`, aparecen en una tarjeta independiente de
  devolución anterior, incluso cuando hay una nueva decisión vigente.
- En Solicitante, la devolución vigente conserva su tarjeta e instrucciones.
  En los demás estados consultables, las últimas observaciones se identifican
  como devolución anterior y se separan del motivo de rechazo actual.
- Las pruebas recorren `DEVUELTA → RADICADA → EN_ESTUDIO → APROBADA/RECHAZADA`
  mediante consultas HTTP simuladas en ambos portales con cachés nuevas.
  Verifican que los textos históricos no aparezcan dentro de la decisión o
  del rechazo vigente y que ORI oculte motivos de rechazo residuales en otros
  estados. Estas pruebas verifican presentación; no cambian reglas de negocio.
- La transición sigue siendo `APROBADA`; la interfaz utiliza Aprobada/Aprobar.
  Se conserva `/aceptar` y no cambian enums persistidos ni contratos API.

## CA-04

La decisión, su cambio de estado y su motivo utilizan el mismo instante UTC.
Antes la auditoría dependía de `now()` de PostgreSQL, que representa el inicio
de la transacción y podía diferir del instante registrado en la solicitud.
Se reutiliza la tabla `auditoria` y los commits existentes.

Una radicación desde `DEVUELTA` ahora audita `DEVUELTA → RADICADA`, con el
Solicitante responsable y la fecha de radicación. No borra las observaciones
ni auditorías anteriores. Los campos de la decisión vigente siguen limpiándose
como antes. Se verifica un ciclo de dos devoluciones, dos nuevas radicaciones
y aprobación final: cinco cambios de estado y dos cambios de observaciones
permanecen en auditoría con responsables y fechas. Las consultas autorizadas
conservan el estado y la última observación.

La API existente expone la decisión vigente y las últimas observaciones; las
rondas anteriores completas permanecen en auditoría. No se añade un endpoint
ni una pantalla de historial, tabla o migración.

## Archivos

- `backend/src/backend/services/solicitudes.py`: instantes coherentes en
  auditoría de decisiones y auditoría de nueva radicación desde DEVUELTA.
- `backend/tests/test_hu07_revision_solicitudes.py`: consultas entre perfiles,
  aislamiento, persistencia, estados, motivos y varias rondas de trazabilidad.
- `frontend/src/pages/SolicitudRecibidaPage.tsx`: observaciones anteriores
  visibles después de nueva radicación y separadas de la decisión vigente.
- `frontend/src/pages/SolicitudPage.tsx`: últimas observaciones anteriores
  consultables también en APROBADA/RECHAZADA, en una tarjeta identificada.
- `frontend/src/pages/SolicitudRecibidaPage.test.tsx`: trece pruebas de
  integración con componentes, router, TanStack Query y cliente HTTP reales.
- `docs/ht01-validacion.md`: evidencia y límites para revisar el PR.

## Ejecución

Backend ejecutado en el DevContainer `/workspace/backend`, con Python 3.13.15.
PostgreSQL 18 local: base exclusiva `ori_ht01_test_20261013`, creada para esta
validación y migrada con Alembic hasta el head existente. Host `db`, usuario
local `ori_user`, SSL desactivado, correo y almacenamiento locales. No se
utilizaron staging ni producción. Frontend ejecutado en el host.

- Focalizadas backend: **90 passed**, incluyendo HU-07/HT-01, permisos,
  HU-11 e integraciones solicitud/elaboración y HU-07/HU-17.
- Integración frontend HT-01: **13 passed** en la revisión adicional.
- Frontend completo: **159 passed**, 13 archivos, en la revisión adicional, con
  `npm test -- --maxWorkers=1 --no-file-parallelism`.
- TypeScript: `npm run typecheck`, código 0.
- ESLint: `npm run lint`, código 0.
- Ruff: `.venv/bin/ruff check src tests`, `All checks passed!`.
- Build: `npm run build`, código 0.
- Backend completo: **1371 passed**, 20 advertencias, en 244,97 segundos,
  ejecutando `.venv/bin/pytest -q` sobre la base local aislada.

En la revisión adicional solo se modificaron frontend y documentación. Se
comprobó que el diff Python conserva exactamente los cambios ya validados;
no se repitieron las pruebas backend ni Ruff. TypeScript, ESLint, la suite
frontend completa y el build se ejecutaron de nuevo con éxito.

Advertencias sin fallo: deprecaciones de Starlette/httpx/AnyIO y Pydantic
(`datetime.utcnow()` en pruebas de HU-24), avisos de
navegación de jsdom en pruebas de descargas y aviso de Vite por bundle mayor
de 500 kB. El sandbox del host falla al configurar loopback; las ejecuciones
se realizaron con aprobación, usando el contenedor y las dependencias locales
existentes. No son fallos funcionales introducidos por HT-01.

Pendiente externo: reproducir el incidente histórico de QA con su traza de
red y sesión. Las pruebas frontend simulan HTTP; la API y persistencia se
verifican separadamente con PostgreSQL, sin un navegador conectado a la API.
La base local aislada se conserva para revisión. No hubo commit, push, merge,
rebase ni cambios de roles, permisos o migraciones.

`git diff --check`: sin salida, código 0.

Salida final de `git diff --stat`:

```text
 backend/src/backend/services/solicitudes.py       |  21 +-
 backend/tests/test_hu07_revision_solicitudes.py   | 239 +++++++++++++++-
 docs/ht01-validacion.md                           | 172 ++++++++++++
 frontend/src/pages/SolicitudPage.tsx              |   4 +-
 frontend/src/pages/SolicitudRecibidaPage.test.tsx | 322 ++++++++++++++++++++++
 frontend/src/pages/SolicitudRecibidaPage.tsx      |  10 +-
 6 files changed, 754 insertions(+), 14 deletions(-)
```

Salida final de `git status --short`:

```text
 M backend/src/backend/services/solicitudes.py
 M backend/tests/test_hu07_revision_solicitudes.py
 A docs/ht01-validacion.md
 M frontend/src/pages/SolicitudPage.tsx
 A frontend/src/pages/SolicitudRecibidaPage.test.tsx
 M frontend/src/pages/SolicitudRecibidaPage.tsx
```
