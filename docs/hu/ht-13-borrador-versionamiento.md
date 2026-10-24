# HT-13 — Borrador persistente y versionamiento formal del convenio

Referencia técnica: [PR #148](https://github.com/ORI-USB-CALI/ori-manager/pull/148),
rama `feature/ht-13-separar-el-guardado-de-avances-del-versionamiento-del-convenio`.
Incidencia de origen: [QA #144](https://github.com/ORI-USB-CALI/ori-manager/issues/144).
Esta ficha describe el contrato implementado y su revisión de frontend; no acredita
despliegue, aceptación de negocio ni cierre del issue.

## Criterios de aceptación

| Criterio | Comportamiento verificable |
|---|---|
| CA-01 — Guardar avances sin versionar | Guardar persiste contenido y metadatos editables sin aumentar `version_actual`. La confirmación anuncia un avance, no una versión nueva. |
| CA-02 — Recuperar avances | Al abrir Elaboración se recupera el último borrador persistido; si no existe, se usa el contenido de la versión formal actual. |
| CA-03 — Formalizar al enviar a revisión | Finalizar crea una versión con contenido y snapshot de metadatos si difieren de la última versión. Si son idénticos, reutiliza esa versión. La revisión jurídica referencia una versión inmutable. |
| CA-04 — Ciclos de corrección | Una devolución permite nuevos avances sin versionar. El reenvío formaliza las correcciones y conserva la versión revisada. Los ciclos devueltos exigen una versión posterior para reenviar. |
| CA-05 — Proteger versiones anteriores | Guardar avances nunca modifica versiones existentes ni las referencias de revisiones o firmas. |
| CA-06 — Concurrencia | El guardado envía `expected_revision`. Una revisión obsoleta recibe 409 sin sobrescribir datos. El editor conserva documento y metadatos locales hasta cargar explícitamente el borrador reciente. |
| CA-07 — Integridad | Versión, transición, apertura de revisión y eliminación del borrador se confirman en una transacción. Un error revierte todo. Guardar sin cambios no aumenta revisión ni versión ni deja auditorías nuevas. |
| CA-08 — Compatibilidad | No se renumeran ni reescriben versiones históricas. Se conservan los flujos manuales, desde solicitudes, revisiones, contraparte, firmas y exportación. |

## Reglas técnicas de negocio

Síntesis del comportamiento de HT-13 y del contrato de su PR, para mantenimiento:

| Regla | Aplicación |
|---|---|
| RN-01 | Guardar avance persiste trabajo parcial durante `ELABORACION`; no formaliza una versión. |
| RN-02 | El envío a revisión jurídica es el punto de formalización del trabajo de Elaboración, sujeto a completitud, vigencia y atención de observaciones. |
| RN-03 | El documento de trabajo se almacena separado del historial en `borrador_convenio`, con un registro como máximo por convenio. Los metadatos editables permanecen en `convenio`. |
| RN-04 | La revisión del borrador es independiente de la versión formal. Cada guardado con cambios reales incrementa la revisión; el control optimista rechaza una revisión de partida obsoleta. |
| RN-05 | Las versiones formales y sus snapshots históricos son inmutables; no se completan retrospectivamente sus claves ni se actualizan sus datos. |
| RN-06 | La identidad de una versión depende del contenido y los metadatos congelados. Un envío idéntico reutiliza la versión sin duplicarla, siempre que las restricciones del ciclo permitan el reenvío. |
| RN-07 | Las correcciones parten de la última versión formal. Guardar correcciones no versiona; reenviar formaliza y conserva las referencias históricas. |
| RN-08 | La transición es atómica. Un guardado sin diferencias reales no crea borrador ni aumenta revisión, versión o bitácora; un conflicto o error no deja cambios parciales. |
| RN-09 | La interfaz distingue versión formal, borrador persistido y cambios locales del documento, de los metadatos o de ambos. No anuncia «Borrador guardado» con cambios locales pendientes. |
| RN-10 | Los convenios y snapshots anteriores conservan su contrato. La migración no rellena borradores históricos; los consumidores usan la versión formal cuando no hay borrador. |

## Modelo y contadores

La migración `bca1bf4a042d`, posterior a `e77280c6486a`, crea únicamente
`borrador_convenio`; no copia ni transforma contenido histórico.

| Columna | Tipo y restricciones |
|---|---|
| `id` | Entero, clave primaria autoincremental. |
| `convenio_id` | FK obligatoria a `convenio.id`, única, `ON DELETE RESTRICT`. |
| `contenido` | JSONB obligatorio con el documento editable. |
| `revision` | Entero obligatorio, `CHECK (revision > 0)`. |
| `actualizado_por_id` | FK obligatoria a `usuario.id`, `ON DELETE RESTRICT`. |
| `creado_en` | Fecha/hora con zona, obligatoria, valor inicial `now()`. |
| `actualizado_en` | Fecha/hora con zona, obligatoria, inicial `now()`; actualización gestionada por SQLAlchemy. |

`convenio.version_actual` identifica la última versión formal en `version_convenio`.
`revision_borrador` es el valor expuesto de `borrador_convenio.revision`, o **0** si no
hay fila. Por ejemplo, V2 puede tener avances R1, R2 y R3 sin dejar de ser V2. Al
enviar cambios se crea V3 y se elimina el borrador. Si vuelve a Elaboración, parte
de V3 y revisión 0: la revisión no es un contador global de toda la vida del convenio.
`borrador_guardado_en` expone la última actualización del borrador o `null`.

El contenido se guarda en la tabla de borrador; los metadatos se actualizan en
`convenio` dentro de la misma transacción. Un cambio exclusivamente de metadatos
también incrementa la revisión del borrador y puede producir una versión al enviar.
El servicio bloquea la fila del convenio con `SELECT ... FOR UPDATE` antes de
comparar revisiones, serializando guardados concurrentes y la finalización.

## Contratos HTTP

Rutas bajo `/api`, con sesión y permisos centrales: consultar requiere
`convenios.ver`; guardar y finalizar requieren `convenios.editar`.

| Método y ruta | Entrada | Respuesta correcta |
|---|---|---|
| `GET /convenios/{id}/elaboracion` | ID del convenio. | 200, datos editables y contenido de trabajo, `version_actual`, `revision_borrador`, `borrador_guardado_en`. |
| `PATCH /convenios/{id}/elaboracion` | `contenido` JSON obligatorio, `expected_revision` entero ≥ 0 obligatorio y metadatos opcionales. | 200 con el estado persistido. La revisión aumenta solo con cambios; la versión formal no cambia. |
| `POST /convenios/{id}/elaboracion/finalizar` | Contenido y metadatos opcionales, `expected_revision` opcional por compatibilidad. El frontend siempre envía la revisión de su lectura. | 200, convenio en revisión jurídica; crea o reutiliza la versión y consume el borrador. |
| `GET /convenios/{id}/elaboracion/validacion` | ID del convenio. | 200, faltantes de completitud del estado guardado. |
| `GET /convenios/{id}/versiones` | ID del convenio. | 200, historial de versiones formales, sin los guardados parciales. |

Los metadatos editables son `tipo_convenio_id`, `objeto`, `alcance`,
`unidad_organizacional_id`, `implicacion_financiera`, `duracion_meses`,
`fecha_inicio`, `fecha_vencimiento` y, solo en origen `MANUAL_ORI`, `aliado_id`.
Vacíos se envían como `null`, referencias y duración como números, fechas como
`YYYY-MM-DD`. El frontend recorta texto al enviar. Guardar valida vigencia solo si
cambian las fechas; finalizar siempre la revalida y exige completitud. El esquema
rechaza campos extra: `expected_version` no sustituye `expected_revision`.

Errores relevantes: 401 sin autenticación, 403 sin permiso, 404 sin convenio,
409 por etapa/transición no disponible o por concurrencia; 422 por validaciones
de entrada, faltantes o vigencia. No todo 409 indica conflicto de borrador:
la concurrencia se identifica por ambos contadores dentro de `detail`:

```json
{
  "detail": {
    "message": "Descripción del conflicto",
    "expected_revision": 2,
    "current_revision": 3
  }
}
```

No se reintenta automáticamente el guardado con `current_revision`: hacerlo
convertiría datos antiguos en una sobrescritura aceptada.

## Estado de edición y recuperación de conflictos

El frontend usa controles de metadatos con `value` y `onChange`. Al primer cambio
conserva juntos el documento, todos los metadatos y la respuesta base del servidor.
Los indicadores comparan contra esa base, no contra un refetch posterior:

- Documento modificado: contenido local diferente del contenido base.
- Metadatos modificados: uno o más valores visibles distintos de la base.
- Ambos modificados: las dos condiciones anteriores.
- Sin cambios pendientes: valores iguales a la base; se muestra «Borrador guardado»
  cuando existe un borrador persistido y no hay conflicto.

Una pantalla limpia se sincroniza con React Query. Si se está editando, un refetch
conserva el documento, todos los metadatos y la revisión original para el siguiente
guardado. Si detecta otra revisión o versión, muestra la advertencia de conflicto.
Un 409 conserva igualmente los cambios y ofrece **Cargar el borrador más reciente**.
La advertencia explica que esa acción reemplazará documento y todos los metadatos;
el usuario puede copiar sus cambios antes de elegirla.

La carga explícita deshabilita temporalmente la edición y las acciones de guardado
y finalización. Solo tras una consulta exitosa reemplaza el conjunto completo. Si
falla, conserva la pantalla y permite volver a intentarlo. El guardado posterior
envía los metadatos recuperados y su revisión, evitando sobrescribir valores de la
otra persona con controles obsoletos.

Un guardado exitoso establece la respuesta como nueva base. Si se continuó editando
mientras se esperaba, conserva los campos y el documento que difieran de lo enviado;
esas modificaciones siguen pendientes y el siguiente envío usa la revisión recibida.
Los errores de guardado conservan la edición. No hay combinación automática de
cambios entre usuarios ni reemplazo silencioso de una edición por un refetch.

## Snapshots, exportación y compatibilidad

El snapshot de una versión congela: `codigo`, `solicitud_id`, `origen`, `aliado_id`,
`tipo_convenio_id`, `objeto`, `alcance`, `unidad_organizacional_id`,
`implicacion_financiera`, `fecha_inicio`, `fecha_vencimiento`, `duracion_meses`,
`convenio_origen_id` y `numero_renovacion`. Las fechas se serializan en ISO.
No incluye estado posterior de firmas o avance, ni objetos ORM.

Al decidir si cambió metadata se comparan solo las claves que el snapshot anterior
ya congeló. Una clave introducida posteriormente, como `origen`, no fuerza por sí
sola una versión nueva. **Los snapshots históricos no se reescriben**, aunque no
tengan las claves del esquema actual. Revisión jurídica conserva su snapshot y la
referencia a la versión formal; revisiones y firmas anteriores no apuntan al borrador.

En Elaboración, los consumidores de documento de trabajo y la exportación en modo
borrador usan el avance guardado cuando existe. La exportación oficial usa la
versión formal y mantiene sus validaciones y permisos. Los cambios que solo están
en pantalla no están disponibles para exportación hasta persistirlos.

## Dependencia con HT-09

HT-09 depende de esta rama para la auditoría estructurada. HT-13 declara mediante
`describir_accion` los eventos `BORRADOR_GUARDADO`, `VERSION_GENERADA` o
`VERSION_REUTILIZADA`, con actor, etapa `ELABORACION` y número de versión formal.
`borrador_convenio` está registrado entre las entidades auditadas; su contenido
JSON se identifica como cambiado sin copiarlo como texto legible a bitácora.

En esta rama la firma de `describir_accion` acepta `evento`, `etapa` y `version`,
pero su persistencia estructurada en columnas de `auditoria` corresponde a HT09-BE02.
No se atribuye aquí esa implementación futura. Guardar sin cambios revierte la
transacción y no deja auditorías nuevas. La integración de HT-09 debe conservar
este comportamiento y los eventos declarados, sin crear una versión por cada avance.
Esta revisión no modifica la rama ni los archivos de HT-09.

## Migración y rollback

El upgrade crea la tabla vacía y conserva versiones, numeración y snapshots.
El downgrade elimina `borrador_convenio`. **Antes de revertir la migración hay que
proteger los borradores todavía no formalizados**, mediante un respaldo recuperable
que incluya contenido, revisión, autor, fechas, metadatos actuales de `convenio` y
su vínculo con la versión formal. Los metadatos por sí solos no permiten recuperar
el documento de trabajo tras eliminar la tabla.

El procedimiento operativo debe coordinar la suspensión de escrituras, el respaldo
y la verificación de recuperación antes del downgrade y del retorno al código
anterior. No se deben formalizar artificialmente versiones ni reescribir históricos
para facilitar el rollback. Esta revisión no ejecuta migraciones, rollback,
operaciones sobre datos ni acciones en Staging o producción.

## Pruebas y validación de esta revisión

`frontend/src/pages/ConvenioElaboracionPage.test.tsx` conserva los casos anteriores
y añade recuperación de los nueve metadatos y del documento tras 409, reenvío sin
sobrescritura, estados de cambios, edición exclusiva de metadatos, refetch con y sin
edición local, fallo de carga explícita y ediciones durante un guardado exitoso.
Los formularios, React Query, serialización y peticiones son reales dentro del test;
se mantiene el sustituto del editor de texto que ya usaba la suite, sin sustituir
las interacciones de los metadatos.

Las pruebas backend existentes de referencia son `test_ht13_borrador_modelo.py`,
`test_ht13_guardar_avance.py` y `test_hu18_registro_automatico.py` (sin cambios,
sin nueva ejecución de backend en esta revisión). Cubren persistencia, snapshots,
concurrencia, transacciones, no-op, exportación y contrato de eventos.

Comandos de validación desde `/workspace/frontend` en el DevContainer de VS Code:

```sh
npm run typecheck
npm run lint
npx vitest run src/pages/ConvenioElaboracionPage.test.tsx
npm test
npm run build
git diff --check
```

Resultados locales del 24/10/2026, después de restaurar las dependencias con
`npm ci --ignore-scripts` (sin modificar manifiestos ni lockfile):

| Validación | Resultado |
|---|---|
| `npm run typecheck` | Correcto. |
| `npm run lint` | Correcto. |
| Vitest de `ConvenioElaboracionPage` | 15/15 pruebas correctas; 9 casos adicionales respecto a las 6 pruebas originales. |
| `npm test` | 25 archivos, 268/268 pruebas correctas. |
| `npm run build` | Correcto; advertencia de chunk de JavaScript mayor de 500 kB. |
| `git diff --check` | Correcto. |

También se ejecutaron las dos regresiones principales contra una copia temporal
del componente de `HEAD` (`2bb110e`): ambas fallan con la implementación original
(aliado visible obsoleto tras cargar el borrador y ausencia de detección de cambios
solo de metadatos) y pasan con la corrección. Las copias temporales se eliminaron.

El entorno inicial tenía ejecutables de dependencias Linux y carecía del binding
nativo de Windows. Tras restaurarlas se pudo validar en Windows con Node 24.14.1;
Vitest necesitó permiso para crear procesos fuera del sandbox (`spawn EPERM`).
No quedan comandos de frontend pendientes por falta de dependencias. La instalación
advirtió que jsdom y algunas dependencias requieren Node 24.15.0 o superior en la
rama 24, y reportó 5 vulnerabilidades altas; su evaluación y actualización quedan
fuera de esta revisión. No se ejecutó `npm audit fix` ni se cambiaron dependencias.

La aprobación CI previa del PR no certifica estos cambios locales posteriores;
debe repetirse CI cuando se publiquen. Quedan pendientes la reproducción manual
del conflicto con dos sesiones y el editor Tiptap real, y la validación conjunta
de la auditoría estructurada en la rama HT-09. No se ejecutaron nuevas pruebas de
backend ni se cerró el issue QA #144.
