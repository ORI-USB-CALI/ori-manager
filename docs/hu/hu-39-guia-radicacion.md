# HU-39 — Guía contextual para crear y radicar solicitudes

## Propósito, fuentes y estado de revisión

La guía explica cómo diligenciar, guardar y radicar una solicitud sin cambiar sus datos ni ejecutar sus acciones. Se ofrece manualmente en el formulario editable para Solicitantes Internos y Externos. Esta ficha registra la auditoría correctiva del [PR #170](https://github.com/ORI-USB-CALI/ori-manager/pull/170), realizada el 01/11/2026. No declara la historia terminada ni aceptada por QA.

Fuentes contrastadas: descripción del PR, [matriz QA de HU-39](https://drive.google.com/file/d/1u2AGFc24UBAzCEYOBMB7dNjmiOruyww_/view), código de `SolicitudPage`, esquemas y servicio de solicitudes, pruebas de HU-38/HU-39 y [política documental](../development/documentation-policy.md). La matriz reúne TC-01 a TC-15: apertura manual, ocho secciones, contenido por rol, acciones/documentos, ausencia de efectos sobre solicitudes, seguimiento, persistencia independiente, recorrido único y responsive.

No se encontró una ficha oficial completa con el texto de todos los CA y RN de HU-39 en las fuentes accesibles. El texto facilitado durante la revisión corresponde a HU-38. No se inventan números ni se presenta la matriz como sustituto de esa ficha; las referencias CA/RN de pruebas preexistentes deben contrastarse cuando esté disponible la fuente oficial de HU-39.

## Dependencias e integración

- [HU-38](hu-38-onboarding-inicial.md) aporta driver.js, `TourProvider`, reglas de cierre, persistencia y estados individuales. Sus correcciones integradas en develop se conservan.
- HT-04 aporta la navegación responsive real. HU-39 no abre ni reproduce otro menú móvil; utiliza el DOM disponible y el motor compartido.
- [HT-12](ht-12-accion-volver.md) conserva la navegación de retorno existente. La guía contextual permanece en el formulario y no navega al avanzar.
- [HT-14 / PR #171](ht-14-validacion-formatos-solicitud.md) incorpora validación por tipo/DV, país del catálogo y formatos de teléfono, ciudad y dirección. La guía refleja ahora esos controles sin validar ni modificar el formulario por sí misma.

Contexto histórico de la auditoría propia de HU-39, anterior a HT-14: al iniciar, `HEAD=42d1933` ya contenía el merge de `origin/develop=769b355`. `git fetch origin develop` confirmó esa referencia. No había `MERGE_HEAD`, archivos sin fusionar ni conflictos pendientes; por tanto no se resolvieron conflictos ni se creó un commit técnico. Había 0 commits exclusivos de develop y 15 exclusivos de la rama (incluido su historial de integración). La rama ya estaba 10 commits por delante de su remoto al iniciar aquella corrección. La auditoría de HT-14 parte de `47c74fc`; sus resultados se registran en su ficha, sin reescribir estas evidencias históricas.

En aquella revisión de HU-39, `OnboardingSolicitantes`, `TourProvider`, `recorrido`, `AppLayout`, `AccionVolver`, `retornoVolver` y el backend de producción coincidían con develop. `estadoGuias.ts` se amplió conservando los tipos, las funciones HTTP y las claves de HU-38. No se seleccionó automáticamente una versión ours/theirs ni se incorporó entonces HT-14. Estos mecanismos de recorrido permanecen intactos en la corrección actual de HT-14.

## Alcance, acceso y permisos

La opción **Ayuda: cómo diligenciar la solicitud** aparece para los dos roles solicitantes con el permiso existente `solicitudes.crear`, sobre una solicitud nueva o editable (`BORRADOR`/`DEVUELTA`). No aparece en una solicitud `RADICADA`. No agrega rutas ni permisos. Las autorizaciones de lectura, creación, edición, documentos y radicación permanecen a cargo de los controles existentes del servidor.

La API de `GUIA_RADICACION` conserva el contrato compartido de HU-38: un usuario autenticado puede leer o registrar únicamente su propio estado personal de esta guía, incluso si tiene un rol ORI. Esta es una preferencia individual sin capacidad de crear/editar/radicar solicitudes ni acceder a datos de otra cuenta. La UI del recorrido sí exige el rol solicitante y el permiso indicado. El contrato genérico está expresamente cubierto por `test_onboarding_solo_para_solicitantes_sin_cambiar_el_contrato_de_radicacion` de HU-38; no se cambia por inferencia sin una regla oficial adicional de HU-39.

`ONBOARDING_INICIAL` mantiene su restricción del servidor a solicitantes. No se amplía su autorización ni se habilita una guía desde la otra. El usuario autorizado se obtiene de la sesión autenticada; ningún ID enviado por el cliente constituye autoridad. Un `usuario_id` en el cuerpo es rechazado (422), una ruta de otro propietario no existe (404) y un parámetro de consulta no cambia el propietario. Sin sesión o con sesión expirada se responde 401. Los códigos de guía desconocidos se rechazan por el esquema existente.

## Arquitectura y contenido

`SolicitudPage` conserva los valores, documentos y operaciones del formulario. Monta `AyudaRadicacion`, identificado por usuario y solicitud, solo en modo editable. Este componente no recibe valores ni funciones de guardar, adjuntar o radicar: únicamente configura el recorrido y sincroniza su estado.

`guiaRadicacion.ts` declara los destinos `data-tour` y las ocho secciones. `pasosAccionesRadicacion.ts` declara las acciones y orientaciones adicionales, utilizando `PasoRecorrido` del motor compartido. El motor sigue siendo driver.js 1.9.0, declarado en `package.json` y fijado en `package-lock.json`, sin cambios de dependencias.

| Sección | Correspondencia con el formulario y servidor actuales |
|---|---|
| 1. Información del solicitante | Interno: datos precargados, nombre y cargo; Facultad/Dependencia y Programa/Unidad según vinculación. Externo: nombre, tipo de documento, Identificación y Empresa/Entidad; base y DV separados para NIT. |
| 2. Información de la contraparte | Nombre, tipo de entidad, tipo/número de identificación y DV para NIT, correo, país del catálogo, ciudad como texto, teléfono y dirección; sector económico para empresa. Se explican límites de ciudad/dirección, indicativo internacional y extensiones, sin prometer existencia geográfica/física. |
| 3. Contacto de contraparte | Nombre, cargo, teléfono y correo obligatorios al radicar. |
| 4. Información del convenio | Tipo, vigencia, justificación, objeto, actividades, metas, implicación financiera y requisitos de renovación obligatorios. |
| 5. Supervisor USB | Nombre, cargo, teléfono y correo. |
| 6. Supervisor de contraparte | Nombre, cargo, teléfono y correo. |
| 7. Documentación | Seleccionar tipo/archivo y Adjuntar; PDF/JPG/PNG, máximo 10 MB, al menos un soporte de representación legal. Otro soporte no lo sustituye. Adjuntar puede guardar primero el borrador. |
| 8. Observaciones adicionales | Texto opcional. |

Después explica Adjuntar documentos, Guardar borrador/Guardar cambios, Radicar solicitud/Volver a radicar, errores de validación y Mis solicitudes. Para `DEVUELTA` agrega la lectura de observaciones ORI, corrección de datos/soportes y nueva radicación. Hay 13 pasos ordinarios y 14 en devueltas, tras filtrar el contenido por rol.

Guardar borrador conserva información incompleta sin enviarla a revisión; los campos diligenciados deben tener formatos válidos. Radicar verifica formatos, campos y soportes requeridos; un rechazo mantiene la solicitud editable. Los mensajes por campo permiten corregir y reenviar conservando los valores. El recorrido no pulsa esos botones, no adjunta archivos, no cambia valores ni abre Mis solicitudes. El seguimiento se explica al final y queda a decisión del usuario. La repetición manual tampoco altera el formulario ni provoca activación automática de ninguna guía.

En HU-39 aislada se habían retirado instrucciones que anticipaban HT-14. Ahora HT-14 sí forma parte del candidato: existen `backend/core/validaciones.py`, selector de país y campos de tipo/DV. El contenido vuelve a corresponder al DOM, esquema y servicio integrados. Los teléfonos de contactos y supervisores siguen las mismas reglas. Los límites y la política de dirección, su carácter sintáctico, los históricos y el downgrade conservador se documentan en la [ficha de HT-14](ht-14-validacion-formatos-solicitud.md).

## Contrato de caché y sincronización

`estadoGuias.ts` centraliza las operaciones HTTP y los hooks reutilizables. Se elimina `guias.ts`, que duplicaba el contrato y usaba una clave global. Se verificaron sus consumidores antes de retirarlo.

La clave continúa siendo `['guias', usuarioId, codigoGuia]`, exactamente la utilizada por HU-38. El identificador es exclusivamente local: GET y PUT no lo envían. Cada guía y cada cuenta tienen entradas separadas. No se alteran las claves ni las funciones que ya consume el onboarding.

1. Abrir Ayuda inicia manualmente el recorrido y habilita una sola consulta. No consulta ni abre la guía de radicación automáticamente al cargar el formulario.
2. Si se cierra antes del GET, se cierra el recorrido de inmediato y se conserva en memoria la intención `OMITIDO`; Finalizar conserva `COMPLETADO`. Un estado todavía desconocido nunca se interpreta como `PENDIENTE`.
3. La consulta sigue habilitada después del cierre. Solo una respuesta exitosa permite decidir si hace falta PUT. Ante un estado final igual o `COMPLETADO` no se escribe de nuevo.
4. Si hace falta persistir, se cancela la lectura obsoleta de esa clave, se verifica usuario/rol de la sesión antes de escribir y antes de aplicar la respuesta, y se deduplican las escrituras en curso del coordinador.
5. La caché solo cambia tras éxito; conserva el avance `PENDIENTE < OMITIDO < COMPLETADO` frente a respuestas fuera de orden. El servidor es la autoridad final y mantiene COMPLETADO aun entre dispositivos.
6. Logout/cambio de cuenta cierra silenciosamente el recorrido desde el proveedor existente. Los callbacks del propietario anterior no escriben ni reconstruyen su caché después de limpiarla, ni cambian la de la nueva cuenta. Una petición ya enviada puede terminar en el servidor para su propietario original; no puede reasignarse a otra cuenta desde el cliente.

| Estado confirmado | Acción manual | Resultado |
|---|---|---|
| Desconocido / GET pendiente | X, Escape, Omitir o Finalizar | Cerrar inmediatamente; retener intención y esperar respuesta/reintento, sin PUT especulativo. |
| PENDIENTE | Finalizar | PUT COMPLETADO. |
| PENDIENTE | Omitir, X o Escape | PUT OMITIDO. |
| OMITIDO | Finalizar | PUT COMPLETADO. |
| OMITIDO | Omitir, X o Escape | Continúa OMITIDO; sin escritura redundante. |
| COMPLETADO | Finalizar o cerrar | Continúa COMPLETADO; sin escritura redundante. |

## API, modelo y concurrencia

Se reutilizan `GET /api/guias`, `GET /api/guias/{guia}` y `PUT /api/guias/{guia}` de HU-38. Ejemplo de escritura: `{"estado":"OMITIDO","version":1}`. La respuesta contiene `guia`, `estado`, `version` y `actualizado_en`. La ausencia de registro significa PENDIENTE; no se almacena una fila ficticia ni se hace backfill de usuarios.

`estado_guia_usuario` conserva FK a `usuario`, unicidad `(usuario_id, guia)`, códigos de guía conocidos, estados finales OMITIDO/COMPLETADO, versión positiva y fechas. No se agrega otra tabla ni migración. El servicio integrado usa bloqueo de fila y savepoint ante una inserción simultánea; las transiciones son idempotentes y COMPLETADO no retrocede. Las pruebas de concurrencia de HU-38 permanecen en la suite completa.

La migración existente `a109c8f2b10b_hu38_estado_guia_usuario.py` depende de `b704d4a8102f`. `heads` e `history` confirman una cadena lineal. Se creó únicamente la base **local aislada** `ori_manager_hu39_review_20261101` en el contenedor de desarrollo, PostgreSQL 18.6; `upgrade head` desde cero terminó en a109c8f2b10b. Se inspeccionaron sus constraints reales, incluida la unicidad por usuario/guía. No se ejecutaron migraciones remotas ni se reescribieron revisiones.

## Errores y continuidad de uso

Un GET fallido informa que el estado no pudo confirmarse, sin asignar PENDIENTE. Si había intención de cierre/finalización, se conserva para un reintento explícito de consulta. No hay reintentos automáticos, refetch por foco/reconexión ni bucles de peticiones.

Un PUT fallido informa que no se pudo guardar, mantiene la caché anterior y ofrece Reintentar guardado. La intención permanece; el doble clic no duplica escrituras. Solo se considera guardada tras respuesta exitosa. Los mensajes no exponen detalles técnicos del servidor. Se puede seguir utilizando el formulario durante consultas y errores; únicamente se evita abrir otro recorrido de radicación mientras su sincronización sigue pendiente.

La intención pendiente es local al formulario, no una cola durable ni un registro offline. Salir de la pantalla/cerrar la aplicación antes de completar la consulta o reintentar un error puede descartarla; no se afirma que quedó guardada. No se bloquea la salida ni se almacena información de solicitudes en un mecanismo nuevo.

## Accesibilidad y responsive

Se conservan los controles del motor de HU-38: Siguiente, Anterior, Finalizar, Omitir, X con nombre accesible y Escape, progreso en español, foco y estilos compartidos, `prefers-reduced-motion`, bloqueo de interacción con el elemento resaltado y exclusión de recorridos simultáneos. La X, Escape y Omitir comparten la misma finalización funcional.

Las ocho secciones y las acciones esenciales utilizan `mantenerSinDestino` del motor existente para centrar la explicación si el elemento está ausente/oculto, conservando el contenido. El resolver y el reposicionamiento ante resize pertenecen a HU-38/driver.js. No se duplica el comportamiento del menú de HT-04. Los estilos de onboarding existentes limitan el ancho/alto del tooltip y permiten scroll del contenido. La regla de HU-39 ya existente para `.header-banner .btn-outline` conserva el fondo legible del botón Ayuda.

Las pruebas de teclado y visibilidad usan driver.js real con geometría declarada en JSDOM. Verifican eventos y decisiones, **no** certifican layout, contraste renderizado ni responsive en navegador. No hubo superficie de navegador disponible en esta sesión. La aceptación visual/assistiva sigue pendiente de QA.

## Diagnóstico y correcciones de esta revisión

| Hallazgo | Diagnóstico y corrección |
|---|---|
| H-01 | Develop ya estaba incorporada sin conflictos. Se comprobó el historial, el diff y la conservación del motor y coordinador HU-38. Sin merge/commit adicional. |
| H-02 | Omitir dependía de una entrada de caché aún inexistente y podía perderse. Ahora se retiene la intención hasta el GET, con errores/reintentos explícitos y sin degradación de estados finales. |
| H-03 | `guias.ts` usaba una clave sin propietario y duplicaba el HTTP de HU-38. Se consolida en `estadoGuias.ts`, con clave vigente por usuario/guía, control de sesión, cancelación y aplicación monotónica de respuestas. |
| H-04 | El contenido describía reglas de HT-14 ausentes. Se ajusta al DOM y esquema/servicio actuales, sin cambiar campos ni validaciones de solicitudes. |
| H-05 | Faltaba ficha propia. Se agrega este documento y su enlace en el índice, con permisos, errores, pruebas, límites y reversión. |
| H-06 | Se verifica recorrido único, cierre/control por teclado, independencia de HU-38, ausencia de acciones sobre solicitudes y contenido esencial sin destinos visibles, reutilizando el motor existente. |

## Pruebas y evidencias

- `SolicitudPage.guia-asincronia.test.tsx`: 21 casos nuevos con formulario y driver reales; X/Omitir/Escape antes del GET, finalización antes/después del GET, COMPLETADO/OMITIDO, error de lectura, error de escritura/reintento/doble clic, respuestas GET/PUT fuera de orden, logout durante PUT, cambio de cuenta/GET previo, caché independiente del onboarding, campos reales internos/externos, nueva/borrador/devuelta/radicada, rol ORI, sección oculta y Tab/Shift+Tab/Enter sin modificar ni enviar el formulario.
- `SolicitudPage.guia.test.tsx` y `SolicitudPage.guia-fe04.test.tsx`: conservan los recorridos completos, estados, ausencia de apertura automática y convivencia con HU-38. Se actualiza la prueba de Ayuda: Inicio antes del onboarding y enlace de retorno al formulario, en vez de esperar el formulario detrás del onboarding.
- `guiaRadicacion.test.tsx` y `pasosAccionesRadicacion.test.tsx`: contenido actual, rol, documentación y retención del contenido esencial. Las comprobaciones de texto se complementan con el DOM y peticiones HTTP reales de pruebas de integración.
- `backend/tests/test_hu39_guia_radicacion.py`: se amplía la expiración de sesión, intento de propietario por query/ruta, constraint único real y correspondencia con la validación HTTP actual. Continúan aislamiento, independencia, estados/transiciones, persistencia entre sesiones y ausencia de efectos sobre solicitudes/auditoría.
- La suite completa incluye HU-38 (API/modelo/concurrencia/recorrido), HT-12, sesión/autenticación, formulario, documentos, devoluciones y radicación.

| Validación | Resultado local real |
|---|---|
| HU-38/HU-39 backend: `uv run pytest tests/test_hu38_guias_api.py tests/test_hu39_guia_radicacion.py -q` | 86 aprobadas; 2 avisos de deprecación, 9.61 s. |
| `uv run pytest` | 2201 aprobadas, 20 avisos de deprecación; salida 0, 279.92 s. |
| `uv run ruff check .` en montaje Windows | Salida 1, 96 EXE002 por modos ejecutables del montaje. |
| `uv run --no-sync ruff check .` en copia temporal con `.py` 0644 | Aprobado, sin ignorar reglas ni cambiar archivos/permisos del repositorio. |
| `uv run alembic heads` | Una cabeza: a109c8f2b10b. |
| `uv run alembic history` | Aprobado; cadena lineal, predecesora b704d4a8102f. |
| `uv run alembic upgrade head` con base local aislada | Aprobado desde cero en PostgreSQL 18.6; constraints inspeccionados. |
| Pruebas específicas frontend de HU-39 | Primera ejecución final de cinco archivos: 56 aprobadas; después se añadieron 2 casos (destino oculto y teclado), ambos aprobados e incluidos en la suite de 528. |
| Regresión específica final HU-38/HU-39/HT-12, 12 archivos | 162 aprobadas, salida 0, 9.05 s; incluye coordinador/motor, contenido, estado, retorno y errores de Elaboración. |
| `npm test -- --pool=threads --maxWorkers=2` | 528 aprobadas en 44 archivos sobre el candidato final, sin omisiones, 26.18 s. |
| `npm run typecheck` | Aprobado, salida 0. |
| `npm run lint` | Aprobado, salida 0. |
| `npm run build` | Aprobado, 229 módulos; aviso de chunk JS >500 kB (aprox. 1101 kB), sin error. |
| Comparación del candidato con las copias validadas | Sin diferencias de contenido frontend/backend, excluyendo dependencias, entornos, datos, cachés y artefactos generados. |
| `git diff --check`, archivos sin fusionar y marcadores de conflicto | Diff sin errores, salida 0; sin archivos sin fusionar ni marcadores en fuentes, pruebas y documentación. |

Las primeras ejecuciones identificaron selectores ambiguos de pruebas, una espera innecesaria de animación y expectativas antiguas de Ayuda. Se corrigieron los auxiliares: no se omitieron casos ni se modificó el motor para hacerlos aprobar. Para comprobar Tab, la geometría JSDOM incluye también los botones del popover; de lo contrario el propio driver los considera invisibles.

## Reproducción de las validaciones locales

Backend sobre `/workspace/backend`, utilizando las dependencias existentes, sin exponer valores de `.env`:

```sh
DATABASE_NAME=ori_manager_hu39_review_20261101 uv run alembic upgrade head
DATABASE_NAME=ori_manager_hu39_review_20261101 uv run pytest
uv run alembic heads
uv run alembic history
uv run ruff check .
```

El montaje de Windows atribuye ejecución a archivos cuyo modo Git es 100644. Para Ruff se copió el backend (excluyendo `.venv`, `.env`, datos y cachés) a `/tmp/ori-hu39-backend-20261101-42d1933`, se normalizaron solo sus `.py` a 0644 y se enlazó la `.venv` local existente. Allí `uv run --no-sync ruff check .` aprobó con las mismas reglas, sin exclusiones. No se modificó la configuración de Ruff ni el repositorio para ocultar EXE002.

Para evitar los problemas de E/S de Vitest sobre el montaje ya observados en HU-38, se copió el frontend a `/tmp/ori-hu39-frontend-20261101-42d1933`, excluyendo únicamente el `node_modules`/`dist` de raíz y entornos. Se enlazó la copia Linux completa de las dependencias ya instaladas de la validación HU-38, cuyo lockfile coincide, sin instalar/actualizar paquetes. En esa copia se ejecutaron los comandos de la tabla; se conservó el aislamiento de pruebas, usando dos workers de tipo threads. La comparación final excluye únicamente dependencias, entornos y artefactos generados. Las suites JSDOM conservan avisos preexistentes de navegación de documentos; no son evidencia de navegador.

## Archivos y compatibilidad

Cambios locales de esta corrección: `SolicitudPage.tsx`, nuevo `AyudaRadicacion.tsx`, `estadoGuias.ts`, eliminación de `guias.ts`, `guiaRadicacion.ts`, `pasosAccionesRadicacion.ts`, sus cuatro archivos de pruebas existentes, el nuevo `SolicitudPage.guia-asincronia.test.tsx`, `backend/tests/test_hu39_guia_radicacion.py`, esta ficha e índice. El CSS y el resto del alcance propio de HU-39 ya estaban en la rama.

La auditoría original de HU-39 no modificó backend de producción, permisos globales, modelos, enums, migraciones, HT-14 ni dependencias; conservó HEAD 42d1933. La auditoría posterior de HT-14 modifica sus propios validadores/servicio y el downgrade del catálogo según su ficha. La API de guías permanece compatible con HU-38, y el ID de caché no cambia su contrato HTTP. La corrección actual se entrega local sobre `47c74fc`, sin nuevos commits, push ni merge.

Para revertir solo esta corrección, retirar conjuntamente sus cambios de código/pruebas/documentación mediante revisión, teniendo presente que eso reintroduciría las carreras corregidas. Para retirar HU-39 completa, retirar su integración en el formulario y configuración de pasos conservando HU-38, la infraestructura de guías y los estados existentes. No se necesita ni se debe ejecutar un downgrade de HU-38 para revertir HU-39: eliminaría también los estados del onboarding.

## Riesgos residuales y QA pendiente

- Obtener/contrastar la ficha oficial completa de CA/RN de HU-39 y aprobar el contenido con negocio; no se certifica su cobertura literal sin esa fuente.
- Probar con backend y sesiones reales ambos roles, usuarios con estados finales en otros dispositivos, desconexión, logout y cambio de cuenta. Las pruebas automatizadas no sustituyen UAT.
- Validar Chrome/Firefox/Safari, teléfono físico, 320/375/768/820/1366 px, zoom, scroll, tooltips dentro del viewport y ausencia de desbordamiento horizontal.
- Probar menú HT-04 cerrado/abierto/colapsado, cambios de tamaño durante el recorrido, foco visible y recuperación de foco al cerrar, lector de pantalla/progreso y `prefers-reduced-motion` con layout real.
- Una intención no sincronizada requiere permanecer en la pantalla y reintentar; no hay garantía offline ni cola durable. El error es visible y el formulario permanece utilizable.
- La sincronización técnica del contenido con HT-14 está realizada en el candidato del PR #171. QA debe confirmar su claridad con datos y sesiones reales; no se declara aceptación de las reglas ni del contenido.
- Confirmar CI remoto y revisión técnica antes de merge. Las pruebas locales aprobadas no constituyen aceptación QA ni autorización de despliegue.
