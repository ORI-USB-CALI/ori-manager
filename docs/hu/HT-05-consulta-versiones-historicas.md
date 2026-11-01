# HT-05 — Consulta de versiones históricas del convenio

## Objetivo y alcance

Permitir consultar el contenido y los metadatos almacenados de una versión formal
del convenio desde su historial, en cualquier etapa y dentro del alcance autorizado.
Referencia: [PR #159](https://github.com/ORI-USB-CALI/ori-manager/pull/159).
Esta ficha describe la implementación y sus pruebas; no acredita aceptación QA,
merge ni despliegue.

Depende de [HT-13 — Borrador y versionamiento](ht-13-borrador-versionamiento.md),
que separa el borrador de trabajo de las versiones formales e inmutables. Guardar
avances no agrega versiones; al finalizar Elaboración se crea o reutiliza una
versión conforme a las reglas vigentes de HT-13.

## Criterios de aceptación

| CA | Comportamiento implementado y evidencia |
|---|---|
| CA-01 — Abrir desde el historial | «Ver contenido» abre `/convenios/:convenioId/versiones/:numero` desde el historial del editor y desde «Versiones del convenio» en la pestaña Historial del detalle. Se puede volver al historial o ir al proyecto. Cubierto por `ConvenioVersionPage.test.tsx`, `VersionesConvenio.test.tsx` y `ConvenioDetallePage.test.tsx`. |
| CA-02 — Contenido y metadatos exactos | Se muestran `contenido` y `snapshot_metadata` de la versión solicitada, sin reconstruirlos con los datos actuales del convenio. Cubierto por el visor y `test_ca02_ca04_la_version_devuelve_contenido_y_metadatos_del_snapshot`. |
| CA-03 — Solo lectura | El editor recibe `editable={false}`. No hay acciones para editar, guardar, finalizar ni restaurar. El test del visor comprueba la propiedad enviada al editor y la ausencia de acciones de escritura. |
| CA-04 — Datos de la versión | Se presentan número, autor, fecha, etapa, contexto de generación y plantilla asociada. Cubierto por el visor y el test backend de CA-02/CA-04. |
| CA-05 — Distinguir borrador y versiones | El visor se identifica como «Versión histórica · Solo lectura» y distingue su contenido del borrador actual. Los historiales aclaran que guardar avances no agrega versiones. Cubierto por el visor, los historiales y `test_ca05_el_historial_excluye_los_guardados_de_avance`. |
| CA-06 — Sin efectos secundarios | Consultar no altera contenido, borrador, `version_actual`, versiones, referencias de revisiones o firmas ni auditoría. Cubierto por `test_ca06_consultar_versiones_no_modifica_el_convenio` y por la comprobación de peticiones GET en el visor. |
| CA-07 — Permisos y errores | Se conservan `convenios.ver` y el alcance operativo existente. La interfaz controla parámetros inválidos y errores del servidor sin exponer el documento. Una versión exclusiva de otro convenio responde 404 al consultarla bajo el ID del primero. Cubierto por los casos CA-07 de frontend y backend. |
| CA-08 — Versiones anteriores a HT-13 | Se listan y consultan versiones legadas, incluidas las de contexto `GUARDADO`, sin plantilla o con snapshot parcial o vacío. Cubierto por los casos CA-08 del visor y backend. |

## Permisos actuales y endpoints reutilizados

La ruta del visor está protegida por `RequierePermiso` con `convenios.ver`.
El backend exige sesión, ese mismo permiso y `verificar_alcance_operativo`.
Gestor ORI y Administrador ORI pueden consultar los convenios de su alcance general.
Revisor ORI conserva el acceso a los convenios en trámite, en Revisión Jurídica,
con una revisión elegible para él según las reglas existentes. Los solicitantes
internos y externos carecen del permiso y reciben 403; sin sesión se devuelve 401.
Convenios inexistentes o fuera de alcance responden 404 «Convenio no encontrado».
HT-05 no agrega permisos ni amplía el alcance de ningún rol.

| Endpoint existente | Respuesta |
|---|---|
| `GET /api/convenios/{convenio_id}/versiones` | 200 con resúmenes de versiones formales, en orden descendente de número, sin contenido documental. |
| `GET /api/convenios/{convenio_id}/versiones/{numero}` | 200 con contenido, snapshot y metadatos de una versión perteneciente a ese convenio. Si no existe esa combinación, 404 «Versión de convenio no encontrada». |

`numero` es el número de versión dentro del convenio, no el ID global de la fila.
Los contratos HTTP permanecen iguales: parámetros de ruta no enteros reciben 422
en llamadas directas al backend. En el visor, tanto `convenioId` como `numero`
deben convertirse en enteros positivos. Si cualquiera es inválido, se muestra
«Versión no encontrada» sin consultar versiones por HTTP ni quedar en carga.
Un error 404 muestra ese mismo estado controlado; otros errores muestran
«No se pudo consultar la versión» con el mensaje disponible y sin documento.

## Solo lectura y compatibilidad

El visor consulta únicamente el detalle de la versión; no carga ni guarda el
borrador. Las pruebas backend comparan el estado antes y después de consultas
repetidas. No se cambian reglas de negocio, contratos API, esquema de base de
datos ni permisos, y no se implementa restauración de versiones.

Los snapshots se presentan tal como fueron almacenados. Las claves conocidas
tienen etiquetas; las desconocidas se muestran con su clave original y los
valores estructurados se representan como JSON. No se completan campos ausentes
con información actual ni se renumeran o reescriben versiones históricas.
Una plantilla ausente muestra «Sin plantilla asociada»; un snapshot vacío muestra
«Esta versión no registró datos del convenio». Las versiones antiguas de guardado
siguen disponibles aunque los avances nuevos ya no generen versiones formales.

## Pruebas y validación

Backend: `backend/tests/test_ht05_consulta_versiones.py` verifica snapshots,
historial, inmutabilidad, permisos, errores y compatibilidad. CA-07 crea V2 con
contenido exclusivo en un segundo convenio, comprueba su lectura allí y exige
404 sin contenido al solicitar V2 mediante el ID del primer convenio, que solo
tiene V1.

Frontend: `ConvenioVersionPage.test.tsx` verifica navegación, documento y metadatos,
solo lectura, versiones legadas, errores y permisos. Los casos de parámetros
inválidos cubren texto, decimales, cero, negativos, `NaN` e `Infinity` tanto para
`convenioId` como para `numero`; comprueban ausencia de peticiones de convenios,
documento y carga indefinida. Las pruebas de `VersionesConvenio`,
`HistorialConvenioContenido` y `ConvenioDetallePage` cubren la integración de los
historiales. El test del visor sustituye el editor por un componente de prueba.

Comandos desde `backend`, con Python 3.13, dependencias instaladas y PostgreSQL
local con las migraciones vigentes:

```sh
.venv/bin/pytest tests/test_ht05_consulta_versiones.py
.venv/bin/pytest
.venv/bin/ruff check .
```

Comandos desde `frontend`, con las dependencias del lockfile instaladas:

```sh
npm test -- src/pages/ConvenioVersionPage.test.tsx src/components/VersionesConvenio.test.tsx src/components/HistorialConvenioContenido.test.tsx src/pages/ConvenioDetallePage.test.tsx
npm test
npm run typecheck
npm run lint
npm run build
```

Desde la raíz, ejecutar también `git diff --check`. Los resultados de esta revisión
se registran en el PR; las pruebas de interfaz usan jsdom y no sustituyen la
validación manual del editor real y la navegación con sesiones autorizadas.

## Reversión

Para deshacer únicamente estos ajustes, revertir el commit adicional de revisión
del PR #159. Si se requiere retirar el visor completo de HT-05, revertir sus
commits de interfaz e integración mediante un cambio revisado, conservando los
endpoints y las reglas existentes de HT-13. HT-05 no introduce migraciones ni
transformaciones de datos: no requiere downgrade, borrado de versiones ni
restauración de contenido. Verificar después el acceso al historial y al editor,
los permisos y las suites afectadas. La reversión del código no modifica versiones,
borradores ni referencias de revisiones o firmas almacenadas.
