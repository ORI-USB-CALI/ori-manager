# HU-23 — Previsualizar documentos adjuntos

## 1. Objetivo y relación con otras historias

El objetivo de **HU-23** es permitir a los usuarios internos autorizados de la ORI previsualizar documentos adjuntos directamente desde la interfaz web de ORI Manager, facilitando la consulta ágil de su contenido sin tener que descargarlos previamente al almacenamiento local ni abandonar su flujo de trabajo.

### Relación y dependencias
- **HU-11 (Radicación y gestión de solicitudes):** Provee la estructura y almacenamiento de documentos adjuntos asociados a las solicitudes radicadas (`Documento` con tipos como `CAMARA_COMERCIO`, `RUT`, `CEDULA_REPRESENTANTE_LEGAL`, etc.).
- **HU-22 (Carga y gestión de documentos de soporte de convenios):** Provee la carga de soportes PDF en convenios vigentes o por vencer y su consulta histórica por Gestor/Administrador, incluso en otros estados.
- **HU-23** se apoya en los modelos, almacenamiento y endpoints existentes introducidos por HU-11 y HU-22, incorporando la capacidad de previsualización interactiva y el parámetro de disposición en la entrega HTTP.

---

## 2. Alcance funcional del MVP

- **Formato admitido para previsualización:** Únicamente **PDF**. El MIME registrado debe ser `application/pdf` o `application/x-pdf`; si falta, se usa la extensión `.pdf` como indicio inicial. La respuesta debe tener MIME PDF o vacío y siempre debe comenzar con la firma `%PDF-`.
- **Otros formatos (ej. `.xlsx`, `.docx`, imágenes):** No se previsualizan interactivamente en este MVP; se informa al usuario mediante un estado amigable de formato no compatible y se conserva la acción de descarga directa autenticada.
- **Modo de visualización:** Estrictamente de **solo lectura**. La previsualización no altera, versiona ni edita el archivo en el almacenamiento.
- **Modal interactivo:** El visualizador se despliega dentro de un diálogo modal accesible sin redirigir al usuario ni alterar su estado de navegación.

---

## 3. Componentes y pantallas integradas

### Componente principal
- `frontend/src/components/DocumentoPreviewModal.tsx`: Componente reutilizable implementado sobre el elemento nativo `<dialog>`, accesible mediante teclado (<kbd>Esc</kbd>), con identificación del documento, gestión segura del foco y limpieza de memoria (`URL.revokeObjectURL`).

### Pantallas integradas
1. **Soportes de convenios (`SoportesConvenio.tsx`):**
   - El botón «Ver» de cada documento de soporte abre el modal de previsualización sin recargar la página. Conserva el botón «Descargar» autenticado.
2. **Solicitudes recibidas (`SolicitudRecibidaPage.tsx`):**
   - En la sección «Documentos adjuntos», cada documento cuenta con la acción «Previsualizar» para abrir el modal, y el botón «Descargar».
3. **Detalle de convenio / Revisión jurídica (`ConvenioDetallePage.tsx`):**
   - En la sección «Documentos asociados» durante la etapa `REVISION_AVAL_JURIDICO`, la acción «Ver» abre el modal de previsualización para el Revisor ORI.
4. **Revisión final del convenio (`RevisionFinalConvenio.tsx`):**
   - En la sección «Documentos asociados», la acción «Ver» abre el modal de previsualización.

---

## 4. Criterios de aceptación (CA)

| Criterio | Descripción y comportamiento implementado |
|---|---|
| **CA-01 — Iniciar la previsualización** | Al seleccionar «Previsualizar» o «Ver» en un documento PDF, se abre el modal dentro de ORI Manager sin descargar previamente ni abandonar la página. |
| **CA-02 — Mostrar el documento seleccionado** | Renderiza el PDF en un `<iframe>` de solo lectura y presenta el nombre del archivo en la cabecera del visor. |
| **CA-03 — Cerrar y regresar al contexto** | Al cerrar (vía botón «×», botón «Cerrar» o tecla <kbd>Esc</kbd>), regresa a la pantalla y sección original, restaurando el foco y conservando el estado. |
| **CA-04 — Conservar la descarga** | Se mantiene la descarga autenticada (`disposicion=attachment`), condicionada al permiso. El modal oculta sus enlaces cuando la consulta confirma 401/403. |
| **CA-05 — Respetar permisos y alcance** | El backend valida sesión, permisos y relación documental. Responde 401 sin sesión, 403 sin permiso y 404 para recursos ajenos, fuera de alcance o documentos no vigentes, sin exponer rutas internas. |
| **CA-06 — Manejar archivos no compatibles** | Si el archivo no es un PDF válido (o su tipo MIME es incompatible), el sistema muestra un mensaje informativo y ofrece descarga directa cuando el usuario tenga autorización. |
| **CA-07 — Manejar errores de consulta** | Informa con claridad errores 401/403/404/502 o de red. Ofrece reintento en errores recuperables; tras 401/403 corresponde cerrar y recuperar la sesión o el acceso. |
| **CA-08 — Integración y accesibilidad** | Componente con atributos WAI-ARIA (`aria-modal="true"`, `aria-labelledby`), soporte completo de teclado, diseño responsivo para móviles y escritorio, y sin efectos de modificación sobre los documentos. |

---

## 5. Reglas de negocio

- **RN-01:** El MVP de HU-23 previsualiza exclusivamente archivos PDF.
- **RN-02:** Se reutilizan la entidad `Documento`, el almacenamiento configurado (local o Microsoft Graph) y los endpoints documentales existentes.
- **RN-03:** La previsualización no reemplaza la descarga ni modifica el archivo.
- **RN-04:** El acceso depende de permisos y del alcance operativo autorizado por las reglas vigentes; para el Revisor se determina por elegibilidad jurídica, sin exigir asignación individual.
- **RN-05:** El rol Revisor ORI solo accede a los documentos de convenios para los que tenga autorización expresa; HU-23 no le concede acceso general a solicitudes recibidas ni a la gestión de soportes.
- **RN-06:** Los archivos se entregan mediante endpoints autenticados con cookies de sesión seguras, sin generar enlaces públicos ni exponer rutas de almacenamiento.
- **RN-07:** Se impiden accesos por manipulación de identificadores (IDOR) y se evitan cachés compartidas de contenido sensible mediante cabeceras `Cache-Control: no-store` y `X-Content-Type-Options: nosniff`.
- **RN-08:** Los formatos no compatibles conservan la consulta de metadatos y la descarga cuando el usuario tenga permiso.
- **RN-09:** La consulta es de solo lectura y no produce registros en el historial de versiones ni mutaciones en la entidad.

---

## 6. Roles autorizados y restricciones

| Rol | Alcance sobre HU-23 |
|---|---|
| **Administrador ORI** | Acceso general a previsualizar y descargar documentos de solicitudes y convenios dentro de su alcance. |
| **Gestor ORI** | Consulta operativa amplia de convenios y solicitudes recibidas, sin filtro por asignación individual. Gestiona soportes según HU-22. |
| **Revisor ORI** | Consulta y descarga de asociados vigentes mediante `/contenido`, incluidos soportes, únicamente en convenios jurídicamente elegibles. No recibe acceso a solicitudes recibidas ni al listado, carga o endpoint de gestión `/descargar` de soportes. |
| **Solicitante Interno / Externo** | No acceden a la previsualización interna de la bandeja ORI; sus accesos se limitan estrictamente a sus solicitudes propias según HU-11. |
| **Usuario anónimo** | Sin acceso (retorna `401 Unauthorized`). |

### Contrato validado para H-01 y H-02

Se conserva la matriz de `core/permisos.py`: Administrador y Gestor tienen `CONVENIOS_VER`, `SOLICITUDES_VER_RECIBIDAS` y `CONVENIOS_GESTIONAR_SOPORTES`; el Revisor tiene `CONVENIOS_VER` y `CONVENIOS_REVISAR`, pero ninguno de los otros dos permisos.

- `/convenios/{id}/documentos/{doc}/contenido` exige `CONVENIOS_VER` y `verificar_alcance_operativo`. Acepta cualquier tipo documental vigente que pertenezca al convenio o a su solicitud asociada. La consulta jurídica existente ya incluye ambos grupos, incluidos los de tipo `SOPORTE`. `inline` y `attachment` aplican exactamente la misma autorización.
- `/convenios/{id}/documentos/{doc}/descargar` pertenece al módulo de soportes de HU-22 y exige `CONVENIOS_GESTIONAR_SOPORTES`. Solo acepta `tipo=SOPORTE`, vigente y perteneciente directamente al convenio. El Revisor obtiene 403, incluso si puede consultar ese soporte por `/contenido`. Esta separación entre lectura jurídica y gestión es intencional y no constituye escalamiento de permisos; bloquear todos los soportes en `/contenido` rompería la consulta jurídica existente.
- Las restricciones de estado `VIGENTE`/`POR_VENCER` se aplican a **cargar** soportes, no a leerlos. Administrador/Gestor conservan lectura en convenios vencidos o finalizados; siempre se exige `Documento.es_vigente=True`.
- `_filtro_alcance_operativo` exige al Revisor convenio `EN_TRAMITE`, etapa `REVISION_AVAL_JURIDICO` y revisión jurídica elegible. `_filtro_revision_juridica_elegible` exige revisión pendiente, sin resultado y de la última ronda con coordenadas jurídicas. En RJ1 no exige asignación; en RJ2 exige RJ1 aprobada en esa misma ronda por otro usuario. `responsable_id` no sustituye estas reglas.
- Tras aprobar RJ1, su autor deja de ser elegible para consultar contenido operativo durante RJ2. Otro Revisor puede continuar. Tras RJ2, el contenido operativo queda fuera del alcance de ambos. El historial HU-21 conserva su autorización separada por participación persistida (asignación, resolución u observaciones), sin ampliar por ello `/contenido` ni las acciones operativas.

La evidencia previa se encuentra en `test_hu13_revision.py`, `test_hu13_acciones.py`, `test_hu17_tablero.py` (incluido el bloqueo de `/contenido` tras RJ1) y `test_hu21_historial_observaciones.py`. Los nuevos casos HU-23 fijan estos límites. No se modifican permisos, filtros ni servicios backend.

---

## 7. Endpoints documentales utilizados

Los endpoints existentes fueron fortalecidos para admitir el parámetro de consulta `disposicion`:

1. **Documentos de Convenios:**
   - `GET /api/convenios/{convenio_id}/documentos/{documento_id}/contenido?disposicion={inline|attachment}`
   - `GET /api/convenios/{convenio_id}/documentos/{documento_id}/descargar?disposicion={inline|attachment}`
2. **Documentos de Solicitudes Recibidas:**
   - `GET /api/solicitudes/recibidas/{solicitud_id}/documentos/{documento_id}/contenido?disposicion={inline|attachment}`

### Parámetros y cabeceras
- `disposicion=inline`: Indica al navegador o cliente que el contenido está destinado a visualización directa.
- `disposicion=attachment`: Fuerza la descarga del archivo como adjunto.
- Cabeceras de seguridad incorporadas:
  - `Content-Disposition: inline; filename*=UTF-8''...` o `attachment; filename*=UTF-8''...`
  - `X-Content-Type-Options: nosniff`
  - `Cache-Control: no-store`

---

## 8. Mecanismo de entrega autenticada y seguridad

1. La petición se realiza desde el cliente mediante `apiFetchArchivo`, que incluye las credenciales de sesión (`credentials: 'include'`).
2. El backend verifica la sesión activa, los permisos del rol y la relación del documento con la solicitud o convenio.
3. El backend lee los bytes del almacenamiento y devuelve una `Response` de FastAPI con el MIME y las cabeceras indicadas. Estos endpoints no utilizan `StreamingResponse` ni `FileResponse`.
4. En el frontend, el blob recibido se verifica:
   - Se valida que el tipo MIME no sea incompatible (ej. `text/html`, imágenes, etc.).
   - Se inspecciona la firma mágica del contenido binario (`%PDF-`).
   - Solo tras validar el formato se genera una URL temporal local mediante `URL.createObjectURL(blob)`.
   - Cada intento tiene su propio `AbortController`, pasado opcionalmente a `apiFetchArchivo` sin cambiar los consumidores existentes. Se verifica cancelación tras obtener el archivo y tras `Blob.slice(0, 5).text()`, que no es cancelable.
   - Cerrar, desmontar, cambiar de documento o reintentar aborta el intento anterior y revoca su URL. Una respuesta antigua, incluso si ignora `AbortSignal`, no puede crear URLs ni sobrescribir el estado de la visualización vigente. Hay como máximo una URL activa por visualización.
   - La descarga continúa mediante enlaces al backend autenticado con `attachment`. La autorización se vuelve a comprobar allí; ocultar enlaces no reemplaza esa validación.

### Cierre, accesibilidad y distribución (H-04)

`showModal()` utiliza la capa modal nativa, su gestión del foco y la inactividad del fondo. El primer control enfocable es «Cerrar previsualizador». Escape se recibe como `cancel`, se evita su cierre predeterminado y se llama a `dialog.close()`; solo el evento `close` notifica al padre, con protección frente a eventos repetidos. Se conserva un respaldo de restauración del foco cuando el activador sigue conectado, también al desmontar.

`.modal-preview` permanece `display:none` y solo `[open]` aplica `display:flex`. El contenido central puede encogerse y desplazarse; en móvil se usa `100dvh` con respaldo `100vh`, sin alturas mínimas que expulsaran los controles fuera de pantallas pequeñas. Se mantienen nombre accesible, `aria-modal`, `aria-live`, iframe con título y ambos botones de cierre. La contención real del teclado y del fondo corresponde al navegador, sin una trampa manual de foco.

---

## 9. Tratamiento de formatos incompatibles y errores

- **Extensión o MIME no PDF:** El componente detecta antes de la petición si el MIME explícito o la extensión corresponden a formatos incompatibles. No realiza peticiones innecesarias y muestra el estado `preview-no-compatible`.
- **Respuesta no PDF (ej. HTML por error o MIME incorrecto):** Si el servidor retorna un tipo distinto o el contenido carece de la firma `%PDF-`, el visualizador rechaza renderizarlo en el iframe y activa el estado de incompatibilidad.
- **Sesión expirada (401):** Mensaje indicando la necesidad de reiniciar sesión; oculta todas las descargas y el reintento dentro del modal.
- **Permiso denegado (403):** Mensaje indicando falta de autorización; oculta todas las descargas y el reintento dentro del modal.
- **Documento no encontrado o no vigente (404):** Mensaje indicando que el archivo no existe o no está activo.
- **Error de almacenamiento (502), otros errores HTTP o de red:** Mensajes controlados, sin mostrar `detail`, rutas o mensajes internos de excepciones. Conserva «Reintentar» y la descarga cuando `puedeDescargar` lo permite y no hay un 401/403 confirmado. Un reintento comienza sin errores ni iframe del intento anterior.

---

## 10. Pruebas y validaciones de la corrección

Entorno local Docker (`ori-manager-workspace-1` y PostgreSQL 18 de `compose.yaml`), Python 3.13.17, uv 0.13.5, Node 24.22.1 y npm 11.19.1. Sin servicios ni migraciones remotas. Fecha de revisión: 31/10/2026 (America/Bogota).

| Hallazgo | Diagnóstico y resolución |
|---|---|
| H-01 | Se descarta escalamiento por la diferencia de endpoints: consulta jurídica y gestión de soportes tienen contratos distintos, ya existentes. Se conservan permisos y se agregan pruebas comparativas e IDOR. |
| H-02 | Se descarta la exigencia de asignación individual. Se corrige documentación: manda elegibilidad jurídica; el historial HU-21 tiene autorización separada. Se agregan límites positivos/negativos. |
| H-03 | Carrera confirmada después de `Blob.text()`. Se agrega señal cancelable por intento y comprobación posterior a cada espera; cierre, desmontaje, cambio y reintento invalidan respuestas antiguas y liberan la URL. |
| H-04 | Visibilidad incorrecta y doble vía de notificación confirmadas. CSS solo muestra `[open]`; `cancel` delega el cierre a `close` y se notifica una vez. Se conservan mecanismos nativos y se adapta la altura móvil. |
| H-05 | Enlaces visibles tras 401/403 confirmados. Se ocultan junto al reintento en esos estados; errores recuperables conservan acciones y mensajes controlados. Se verifican las cabeceras y la autorización backend. |

### Cobertura agregada

- `DocumentoPreviewModal.test.tsx` (**38 casos, 19 nuevos**): cancelación al cerrar o desmontar durante fetch y durante `Blob.text()` (resolución y rechazo); respuestas HTTP y validaciones fuera de orden; reintento más reciente; una URL activa, revocación sin duplicados, cambio de documento/formato y tres aperturas consecutivas. Errores 401/403 sin enlaces ni reintento, errores recuperables con descarga autenticada, mensajes sin detalles internos. Nombre ARIA, foco inicial, Tab, Escape, notificación única, restauración del foco y activador eliminado. Prueba del CSS real para verificar `flex` abierto y `none` cerrado.
- `test_hu23_previsualizacion_documentos.py` (**49 casos, 28 nuevos**): matriz Administrador/Gestor/Revisor × SOPORTE/BORRADOR × vigente/no vigente, comparando ambos endpoints con `inline` y `attachment`; IDOR entre convenios y solicitudes; adjunto de la solicitud asociada accesible por convenio pero no por bandeja recibida para el Revisor; rechazo de listado/carga/descarga de gestión; RJ1 sin asignación individual, RJ2 con otra persona, conservación del historial HU-21. Límites por etapa, estado, resolución, resultado, ausencia de coordenadas, ronda antigua y RJ2 sin RJ1 aprobada; consulta de soportes en estados históricos sin aplicar la restricción de carga.
- Se ejecutan las integraciones existentes de `SoportesConvenio`, `SolicitudRecibidaPage`, `ConvenioDetallePage`, `RevisionFinalConvenio` y consumidores de `apiFetchArchivo` (`descargas` y `ExportarConvenioMenu`). No se implementa Excel ni se modifica su comportamiento.

### Registro de comandos

| Directorio | Comando | Resultado real |
|---|---|---|
| `backend` | `uv run pytest tests/test_hu23_previsualizacion_documentos.py tests/test_hu13_revision.py tests/test_hu13_acciones.py tests/test_hu17_tablero.py tests/test_hu21_historial_observaciones.py tests/test_hu22c_soportes.py -q` | Código 0; 139 aprobadas, 2 advertencias de deprecación. |
| Copia temporal de `backend` con modos Git | `uv run ruff check .` | Código 0; `All checks passed!`, sin desactivar reglas. |
| `backend` con base aislada | `uv run alembic upgrade head` | Código 0; esquema local en `b704d4a8102f`. |
| `backend` con base aislada | `uv run pytest` | Código 0; **2097 aprobadas**, 20 advertencias de deprecación, 342.42 s. Incluye las 49 de HU-23 y regresiones HU-11/HU-13/HU-21/HU-22. |
| `frontend` | `npm test -- src/components/DocumentoPreviewModal.test.tsx` | Código 0; **38 aprobadas**. |
| `frontend` | `npm run typecheck` | Código 0. |
| `frontend` | `npm test` | Código 0; **372 aprobadas en 32 archivos**, 135.85 s. |
| `frontend` | `npm run lint` | Código 0, sin errores. |
| `frontend` | `npm run build` | Código 0; build estático generado, advertencia por chunk mayor de 500 kB. |
| raíz | `git diff --check` | Código 0, sin errores de espacios. |

La base aislada es `ori_manager_hu23_review_20261031`, creada en el contenedor PostgreSQL **local**. Para las migraciones y la suite completa se fijaron `APP_ENV=test`, `DATABASE_HOST=db`, `DATABASE_NAME=ori_manager_hu23_review_20261031`, `DATABASE_SSLMODE=disable`, `EMAIL_PROVIDER=local`, `PUBLIC_FRONTEND_URL=http://localhost:5173`, `DOCUMENT_STORAGE_PROVIDER=local` y `DOCUMENT_STORAGE_PATH=/tmp/ori-hu23-tests`.

La primera ejecución general de pytest sobre la base de desarrollo encontró el esquema anterior `9d53cf1dcef3` (faltaban HT-06 y HT-10). Se interrumpió esa ejecución fallida y se repitió completa en la base aislada migrada, sin migrar la base de desarrollo ni cambiar código ajeno a HU-23. La ejecución final aprobada es la de 2097 casos indicada arriba.

La ejecución inicial de `uv run ruff check .` directamente sobre el montaje Windows terminó con código 1 y 98 `EXE002`: el montaje expone como ejecutables archivos que Git registra como `100644`. Para la verificación final se copiaron los archivos rastreados desde el **working tree**, incluyendo estas modificaciones, a un directorio temporal Linux y se aplicaron los modos registrados en `git ls-files -s`. Se ejecutó allí el mismo comando, sin ignorar reglas ni modificar archivos ajenos a HU-23. No se presenta la ejecución original como aprobada.

Las advertencias backend proceden de Starlette/httpx, AnyIO y uso preexistente de `datetime.utcnow()` en pruebas de exportación. JSDOM también informa que no implementa navegación de enlaces de descarga. El build advierte del tamaño de un chunk (aproximadamente 1.05 MB); no se amplió HU-23 para cambiar la arquitectura de carga. Las primeras ejecuciones de desarrollo detectaron expectativas de mensajes antiguas y limitaciones del arnés CSS/tipos Node; se corrigieron y la suite final indicada arriba incluye la prueba del CSS real.

---

## 11. Limitaciones conocidas y validaciones de QA

1. **Formatos no PDF:** Las hojas de cálculo (`.xlsx`) y documentos Word (`.docx`) no cuentan con visor integrado en el MVP; requieren ser descargados para su consulta.
2. **Validación en dispositivos reales:** Aunque el diseño cuenta con adaptaciones CSS responsivas (`max-width: 640px`), la experiencia visual en navegadores móviles específicos debe ser certificada por el equipo de QA en el entorno de Staging.
3. **Estado de aceptación:** El paso de las pruebas automatizadas y del CI no constituye por sí solo la aprobación definitiva de la historia; esta requiere la validación funcional del Product Owner y QA.
4. **QA pendiente en Staging:** Probar Administrador/Gestor y dos Revisores distintos en RJ1/RJ2, cambio de elegibilidad mientras el visor está abierto y descarga posterior al vencimiento de sesión. Confirmar PDF real en navegadores soportados (incluido móvil), cierre rápido con red lenta, reintento, repetidas aperturas, pantalla pequeña en ambas orientaciones y nombre largo. Validar Tab/Shift+Tab, Escape con foco dentro del visor PDF, foco inicial/restaurado, lector de pantalla e imposibilidad de interactuar con el fondo. JSDOM usa un sustituto de `showModal`/`close`; no certifica la capa modal ni el motor PDF nativo del navegador.
5. **Entrega en memoria:** Backend usa `Response` y frontend recibe un Blob completo. No hay streaming ni un motor PDF adicional; el consumo con archivos grandes y el proveedor de almacenamiento real requieren QA. La comprobación MIME/firma no sustituye la seguridad del motor PDF del navegador.

---

## 12. Seguridad, compatibilidad y reversión

- **Seguridad:** No se publican enlaces directos al almacenamiento ni tokens públicos. MIME y firma rechazan respuestas HTML o formatos incorrectos antes del iframe; no constituyen una sanitización completa del contenido PDF.
- **Compatibilidad:** Todos los cambios en endpoints conservan compatibilidad hacia atrás con los clientes que no envíen el parámetro `disposicion` (asumiendo `inline` por defecto o manteniendo el flujo previo).
- **Reversión:** Los cambios se limitan a componentes de presentación en frontend y parámetros opcionales en routers de FastAPI, sin modificaciones en el esquema de base de datos (`ALTER TABLE`), por lo que una reversión de código no requiere migraciones de esquema inversas.

---

## 13. Auditoría no destructiva de dependencias frontend

Se ejecutaron `npm audit --json`, `npm audit --omit=dev --json`, `npm ls --all --json` y consultas de versiones con `npm view`, desde `frontend` en el contenedor y contra `https://registry.npmjs.org/`. El audit completo devuelve código 1 y **17 paquetes afectados: 12 moderados y 5 altos**, sin críticos. La auditoría con `--omit=dev` devuelve código 0 y **0 vulnerabilidades de producción**. Las 17 entradas figuran con `dev: true` en el lockfile; varias son propagaciones de la misma vulnerabilidad transitiva, no 17 fallos independientes.

Una consulta inicial desde Windows devolvió 0 incluso con dev; ese resultado divergente no se usa para concluir ausencia de vulnerabilidades. La evidencia relevante reproduce las 17 en el mismo entorno de herramientas que las pruebas.

### Paquetes y rutas de dependencia

Todas las rutas parten de una dependencia de desarrollo. Se muestran las rutas principales; las referencias peer también propagan los avisos de ESLint.

| Paquete instalado | Severidad npm | Ruta principal |
|---|---|---|
| `@eslint-community/eslint-utils@4.10.1` | Moderada | `eslint → @eslint-community/eslint-utils`; también `typescript-eslint → @typescript-eslint/utils → …` |
| `@eslint/config-array@0.23.5` | Moderada | `eslint → @eslint/config-array → minimatch` |
| `@eslint/js@10.0.1` | Moderada | `@eslint/js → eslint` (peer) |
| `@typescript-eslint/eslint-plugin@8.70.0` | Moderada | `typescript-eslint → @typescript-eslint/eslint-plugin → parser/type-utils/utils/eslint` |
| `@typescript-eslint/parser@8.70.0` | Moderada | `typescript-eslint → @typescript-eslint/parser → typescript-estree/eslint` |
| `@typescript-eslint/type-utils@8.70.0` | Moderada | `typescript-eslint → @typescript-eslint/eslint-plugin → @typescript-eslint/type-utils` |
| `@typescript-eslint/typescript-estree@8.70.0` | Moderada | `typescript-eslint → @typescript-eslint/typescript-estree → minimatch` |
| `@typescript-eslint/utils@8.70.0` | Moderada | `typescript-eslint → @typescript-eslint/utils → eslint-utils/typescript-estree/eslint` |
| `eslint@10.10.0` | Moderada | `eslint → minimatch`; también a través de `@eslint/config-array` |
| `eslint-plugin-react-refresh@0.5.6` | Moderada | `eslint-plugin-react-refresh → eslint` (peer) |
| `minimatch@10.2.6` | Moderada | `eslint → minimatch`; también `typescript-eslint → @typescript-eslint/typescript-estree → minimatch` |
| `typescript-eslint@8.70.0` | Moderada | Directa, propagación desde sus componentes y ESLint |
| `brace-expansion@5.0.9` | Alta | `eslint → minimatch → brace-expansion` |
| `source-map-js@1.2.1` | Alta | `vite@8.3.0 → postcss@8.5.28 → source-map-js`; `jsdom@30.1.2 → css-tree@3.2.1 → source-map-js` |
| `undici@8.11.2` | Alta | `jsdom@30.1.2 → undici` |
| `vite@8.3.0` | Alta | Directa; compartida con `@vitejs/plugin-react` y `vitest` |
| `zod@4.6.1` | Alta | `eslint-plugin-react-hooks@7.1.1 → zod`; también mediante `zod-validation-error@4.0.2` |

### Impacto y soluciones evaluadas, sin aplicarlas

- `brace-expansion`: denegaciones de servicio por expansión/recursión. La rama instalada admite `5.0.12` mediante `^5.0.8`; cubre los tres avisos (incluido el de [expansión cuadrática](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr)).
- `source-map-js`: denegación de servicio al procesar mapas de fuentes; `1.2.2` satisface los rangos `^1.2.1` de PostCSS y css-tree. [Aviso y versión corregida](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).
- `undici`: ocho avisos sobre DoS, integridad, caché/redirecciones y TLS en Node. `8.12.2` satisface el rango `^8.11.2` de jsdom. No es el fetch nativo del navegador usado por `apiFetchArchivo`. [Aviso de caché y exposición entre usuarios](https://github.com/advisories/GHSA-4w7w-5xrc-9h26).
- `vite`: avisos del servidor de desarrollo y launch-editor, con posibles ejecuciones de comandos en ciertos escenarios de editor/Windows y accesos a archivos. `8.3.3` satisface `^8.2.2`. Los archivos de despliegue del repositorio publican `dist` como sitio estático; no ejecutan el servidor de desarrollo. [Aviso de launch-editor y versiones corregidas de Vite](https://github.com/advisories/GHSA-587h-7wmj-h5pm).
- `zod`: agotamiento de memoria; `4.6.6` satisface el rango `^3.25.0 || ^4.0.0` usado por las herramientas de lint. [Aviso y versión corregida](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5).
- `minimatch` y sus propagaciones moderadas: la versión corregida publicada es `11.0.1`, fuera de `^10.2.5` utilizado por ESLint. No se ha demostrado una solución compatible para toda la cadena. `npm audit` propone rebajas de versión mayor para `@eslint/js`/`typescript-eslint`, y para `eslint-plugin-react-refresh` señala `fixAvailable:false`. Esas sugerencias no garantizan compatibilidad con TypeScript/ESLint actuales y no deben aplicarse automáticamente. [Aviso de minimatch](https://github.com/advisories/GHSA-g3hv-75wg-m249).

Las versiones de corrección anteriores se confirmaron mediante consultas de solo lectura a npm. Los requisitos `engines` publicados de esos cinco parches admiten Node 24.22.1 (Zod no declara restricción). **No se instalaron ni probaron actualizaciones**. No se ejecutó `npm audit fix`, ni `--force`, ni se cambió el lockfile.

### Preexistencia y decisión sobre merge

`package.json` y `package-lock.json` son idénticos entre HEAD y `origin/develop` (`205152710e93c0277ef53c0167b06f7cf8445e42`, misma base del PR). El blob Git del lockfile es `a56a671311b88a13a2ff14854096b37ed788559b` en ambos. Por tanto, las versiones vulnerables ya están en `develop`; HU-23 no añade dependencias PDF ni modifica dependencias de autenticación o manejo de archivos.

El visor utiliza Blob, fetch e iframe del navegador; no incorpora PDF.js u otro paquete de renderizado PDF. No se identificó una ruta directa desde un documento HU-23 hacia los paquetes afectados en producción. Sí existe riesgo en herramientas de desarrollo/CI que procesen entradas no confiables y en servidores Vite expuestos: la condición `dev` no elimina ese riesgo.

**Recomendación:** seguimiento prioritario en un issue independiente de dependencias, con parches compatibles para los cinco paquetes altos y revisión separada de la cadena ESLint/minimatch. Estos avisos preexistentes no bloquean por sí solos el merge de HU-23 bajo el despliegue estático descrito; la aprobación final mantiene los controles habituales de CI, revisión técnica y QA. No se creó un issue ni se amplió este PR para remediarlos.
