# HU-38 — Onboarding inicial para solicitantes

Ficha técnica del [PR #169](https://github.com/ORI-USB-CALI/ori-manager/pull/169), destinado a `develop`. Estado: corrección local para revisión técnica; **sin declaración de terminación ni aceptación QA**. Los CA y RN usados son los aportados por el responsable durante esta revisión, contrastados con la [matriz de QA Sprint 4](https://drive.google.com/file/d/1u2AGFc24UBAzCEYOBMB7dNjmiOruyww_/view). Los casos de esa matriz no constituyen evidencia de ejecución de esta corrección.

## Objetivo y alcance

Presentar a Solicitantes Internos y Externos el propósito de ORI Manager, el proceso de una solicitud y los módulos autorizados. Es informativo y opcional: no crea solicitudes, no guarda formularios, no radica y no concede permisos. Omitir, X y Escape permiten salir inmediatamente. Ninguna operación exige completar el onboarding.

El recorrido diferencia crear/radicar una solicitud de obtener un convenio formalizado. Explica Inicio, Nueva solicitud, Mis solicitudes, Revisiones de contraparte y Centro de notificaciones según los permisos de la sesión. La bienvenida adapta su explicación a la persona interna de la Universidad o a quien propone un convenio desde una entidad externa; no cambia las reglas de negocio de esos módulos.

La corrección comprende autorización del onboarding, reproducción completa desde Ayuda, errores recuperables, cierre por cambio de sesión, adaptación al DOM responsive, pruebas y documentación. No cambia autenticación, permisos globales, dependencias, HU-39, HT-14 ni lógica de negocio de HT-12.

## Diagnóstico y decisiones

- **H-01:** la API autenticaba e identificaba al propietario correctamente, pero aceptaba ONBOARDING_INICIAL para cualquier rol. El servicio ahora verifica expresamente los dos roles solicitantes, incluso si se invoca sin pasar por el router. El listado excluye esa guía para otros roles.
- **H-02:** Ayuda abría el recorrido sobre la pantalla actual; los pasos de Inicio desaparecían. Ahora navega a Inicio, espera su contenedor real y abre una sola instancia. Ofrece regresar a la ruta anterior con sus filtros y retorno HT-12 validado.
- **H-03:** faltaba la ficha técnica de HU-38 y su entrada en el índice.
- **H-04:** el mensaje genérico no diferenciaba fallo de consulta de fallo de escritura y no reintentaba explícitamente la operación fallida. Ahora cada operación tiene su reintento, no se inventa un estado tras un GET fallido ni se actualiza optimistamente la caché tras un PUT fallido. El motor conserva explicaciones esenciales cuando falta un destino.

## Roles y autorización por guía

| Operación | Solicitante Interno / Externo | Administrador / Gestor / Revisor ORI |
|---|---|---|
| GET/PUT ONBOARDING_INICIAL | Estado propio, autorizado | HTTP 403 |
| GET listado de guías | Incluye onboarding | Excluye onboarding |
| API GUIA_RADICACION | Contrato previo de estado propio | Contrato previo autenticado conservado |

La política se implementa en `ServicioGuias`, sin crear permisos generales ni modificar `core/permisos.py`. El onboarding corresponde a los roles solicitantes de CA-01/CA-05; el tipo INTERNO/EXTERNO adapta el contenido, no sustituye la validación del rol.

**Decisión de compatibilidad con HU-39:** se revisó su diseño en [PR #170](https://github.com/ORI-USB-CALI/ori-manager/pull/170): usa el motor compartido y persiste GUIA_RADICACION de forma independiente. Esta corrección restringe únicamente ONBOARDING_INICIAL. Conserva para GUIA_RADICACION el contrato autenticado de preferencias propias que ya tenía la API, sin acceso a datos de solicitudes ni nuevas operaciones. La política contextual de acceso al formulario pertenece a HU-39. No se implementa ni se modifica esa guía en esta rama.

El ID del usuario siempre procede de la sesión. El cuerpo no acepta `usuario_id` ni campos adicionales; una ruta que añada un ID no existe y los parámetros de consulta no cambian el propietario. El servicio filtra toda lectura/escritura por usuario y guía. Una sesión ausente o expirada recibe 401; un usuario inactivo mantiene el rechazo de autenticación existente. No se exponen estados de otras cuentas.

## API y persistencia

Rutas autenticadas en `backend/api/routers/guias.py`:

| Método y ruta | Contrato |
|---|---|
| `GET /api/guias` | Guías disponibles para la sesión, sin IDs de otras cuentas |
| `GET /api/guias/{guia}` | Estado propio; 422 para código de guía desconocido |
| `PUT /api/guias/{guia}` | Solo estado final y versión positiva; 422 para cuerpo inválido |

Ejemplo de escritura:

```json
{ "estado": "COMPLETADO", "version": 1 }
```

La respuesta contiene `guia`, `estado`, `version` y `actualizado_en`. Sin fila, devuelve PENDIENTE y los dos últimos campos son nulos; no crea un registro por consultar.

`estado_guia_usuario` contiene `id`, `usuario_id`, `guia`, `version`, `estado`, `creado_en` y `actualizado_en`. Mantiene FK al usuario con borrado restringido, índice por usuario y el constraint único `uq_estado_guia_usuario_usuario_guia`. Los checks admiten solo ONBOARDING_INICIAL/GUIA_RADICACION, estados finales COMPLETADO/OMITIDO y versión ≥ 1. PENDIENTE es lógico y no se almacena.

| Estado existente | Acción | Resultado persistido |
|---|---|---|
| Sin fila / PENDIENTE | Finalizar | COMPLETADO |
| Sin fila / PENDIENTE | Omitir, X o Escape | OMITIDO |
| OMITIDO | Finalizar manualmente | COMPLETADO |
| OMITIDO | Omitir, X o Escape | OMITIDO, idempotente |
| COMPLETADO | Cualquier cierre o nueva finalización | COMPLETADO, sin reescribir versión/fecha |
| Cualquier estado | Solo abrir/reproducir | Sin escritura |
| PENDIENTE | Recargar o cerrar sesión sin una acción final | Sigue PENDIENTE |

Se conserva la transición existente: `SELECT FOR UPDATE` en filas existentes, savepoint y recuperación ante colisión de inserción por el constraint único. Las nueve pruebas concurrentes usan sesiones PostgreSQL independientes, con y sin fila previa y con órdenes opuestos de completar/omitir. COMPLETADO prevalece y queda una sola fila. No se sustituyó esta lógica por almacenamiento local ni por un estado optimista de frontend.

## Arquitectura y driver.js

- `pages/onboardingInicial.ts`: código ONBOARDING_INICIAL, versión 1, contenido y filtros de rol/permiso.
- `components/recorrido.ts`: único adaptador de driver.js, tipos y contexto reutilizables, filtrado, controles, resolución de destinos y cierre silencioso.
- `TourProvider`: mantiene una sola instancia; otro recorrido recibe `false` mientras haya uno abierto. Desmontar, perder la sesión o cambiar de cuenta/rol cierra silenciosamente sin registrar omisión.
- `OnboardingSolicitantes`: consulta, activación automática, coordinación manual, persistencia y reintentos.
- `AppLayout` monta esa coordinación con una clave de usuario/rol para separar ciclos de cuenta; `HomePage` conserva sus identificadores `data-tour`.
- `pages/estadoGuias.ts`: HTTP autenticado sin ID de usuario; la consulta recibe AbortSignal para cancelar lecturas al desmontar.

Se conserva **driver.js 1.9.0**, declarado en `package.json` y `package-lock.json`. No se instalaron ni actualizaron dependencias. Avanzar/Anterior/Finalizar, X y Escape siguen perteneciendo al motor; Omitir se agrega en su footer. El elemento resaltado no puede ejecutar operaciones mediante interacción accidental. Se respeta `prefers-reduced-motion`.

Las extensiones `destinosAlternativos` y `mantenerSinDestino` son opcionales. Sin ellas se conserva la política de omitir destinos ausentes. HU-38 conserva centradas sus explicaciones esenciales; las restricciones de permiso/rol se aplican antes y nunca se sustituyen por ese fallback. El runtime de driver.js 1.9 admite un resolver que no encuentra elemento y centra el paso; sus tipos aún declaran que ese callback devuelve Element. La adaptación utiliza una aserción limitada a `DriveStep.element`, sin cambiar la biblioteca.

## Activación automática, Ayuda y retorno

Una sesión solicitante con GET exitoso PENDIENTE inicia automáticamente en `/`, después de que exista `[data-tour="inicio-accesos-rapidos"]`. COMPLETADO y OMITIDO no abren automáticamente. Una referencia impide reabrir mientras se sincroniza una acción final.

Desde otra pantalla, Ayuda navega a Inicio y espera su DOM. Guarda la URL previa con búsqueda/hash solo si supera la validación de ruta interna de HT-12, y exclusivamente su retorno validado. Un origen anómalo como `//host` no genera un enlace externo. Al cerrar el recorrido ofrece **Volver a la pantalla anterior**; el usuario decide cuándo regresar. Desde Inicio no genera un retorno artificial. No usa navegación retrospectiva indiscriminada ni propaga estados ajenos al contrato.

La espera usa MutationObserver y un límite de cinco segundos. Si Inicio no queda disponible, muestra un aviso y Reintentar recorrido. No entra en un bucle de consultas. La preparación, el recorrido activo y el guardado impiden aperturas o escrituras duplicadas, sin deshabilitar las operaciones normales de los otros módulos.

Una reproducción de COMPLETADO no hace PUT. Finalizar desde OMITIDO sí puede hacer la transición. Hay protección contra callbacks repetidos y respuestas tardías tras desmontar la cuenta anterior; la caché nunca sustituye COMPLETADO por un resultado de menor estado.

## Errores recuperables

- **GET fallido:** se informa que no se pudo consultar el estado. No se supone PENDIENTE ni se abre automáticamente. Reintentar consulta vuelve a hacer GET. Se desactivan los reintentos automáticos y el refetch por foco de ventana de esta consulta.
- **PUT fallido:** se informa que no se pudo guardar. Se conserva la caché anterior y la acción final por sincronizar. Reintentar guardado repite esa misma acción, sin reproducir otra vez ni anunciar éxito. No hay reintento automático de escrituras.
- **Cambio de sesión:** los recorridos se destruyen silenciosamente. Las consultas consumen AbortSignal y los callbacks tardíos no reconstruyen la caché de la cuenta anterior. Una escritura que ya fue enviada puede terminar en el servidor para su sesión original; no se promete deshacerla.

## HT-04, accesibilidad y responsive

No se cambian `HeaderNav` ni sus breakpoints, apertura, cierre o gestión de grupos. El adaptador consulta visibilidad real del DOM (`getClientRects` y `visibility`): con navegación expandida usa el panel; con el menú cerrado usa el botón existente; con menú abierto prefiere el panel visible. Se muestra un único paso de navegación. Al cambiar el tamaño se vuelve a resolver el destino equivalente y driver.js reposiciona su tooltip.

El CSS compartido del recorrido limita el popover al viewport, permite ajustar controles en varias filas, evita ancho mínimo fijo y habilita scroll vertical para contenido alto. La X usa texto oscuro; todos los botones tienen contorno visible con teclado. Las etiquetas se mantienen en español. La superposición es temporal y se elimina al cerrar el recorrido.

**Las simulaciones geométricas de jsdom no son una prueba responsive en navegador.** En esta sesión el navegador in-app no está disponible. Quedan pendientes validación visual de posición, superposición, reflujo, zoom y ausencia real de desbordamiento, contra HT-04 integrado. No se certifica WCAG ni aceptación responsive a partir de pruebas DOM.

## Trazabilidad CA y RN

| Criterio | Cobertura técnica |
|---|---|
| CA-01 | Automático solo para solicitantes pendientes, con sesión y DOM de Inicio disponibles |
| CA-02 / CA-03 | Pruebas del contenido: propósito, proceso, solicitud distinta de formalización |
| CA-04 / CA-05 | Módulos reales, permisos y roles; destinos DOM de Inicio/HT-04; autorización del estado propio |
| CA-06 | Controles reales de driver.js, avance/retroceso/finalización y equivalencia X/Omitir/Escape |
| CA-07 | API, persistencia individual, constraints, sesiones y concurrencia PostgreSQL |
| CA-08 | Reproducción desde Inicio/otras rutas; COMPLETADO conservado y OMITIDO actualizable |

| Regla | Aplicación |
|---|---|
| RN-01 | Informativo, opcional y sin requisito de completar para trabajar |
| RN-02 | Estados lógicos PENDIENTE, COMPLETADO y OMITIDO |
| RN-03 | Ausencia de fila equivale a PENDIENTE para cuentas nuevas y antiguas; sin backfill |
| RN-04 | X equivale a Omitir; se respeta el COMPLETADO previo conforme a CA-08 |
| RN-05 | Onboarding independiente de la guía contextual HU-39 |
| RN-06 | Identidad usuario/guía en tabla, API y clave de caché |
| RN-07 | Propietario derivado de sesión, sin consulta ni escritura de otras cuentas |
| RN-08 | Fallos no bloquean la plataforma; fallo de PUT explícito, sin éxito ni caché falsos |

## Migración, compatibilidad y reversión

Se conserva intacta `a109c8f2b10b_hu38_estado_guia_usuario.py`, hija de `b704d4a8102f` existente en `develop`. No se reescriben migraciones ya desplegadas ni se crean revisiones de merge. El grafo tiene una sola cabeza `a109c8f2b10b`.

La validación usa exclusivamente PostgreSQL **18.6** del contenedor local y la base nueva **ori_manager_hu38_review_20261101**. Se comprobó que no existía antes de crearla y se aplicó `alembic upgrade head` desde cero. Las pruebas inspeccionan columnas, checks, FK y unicidad usuario/guía. No se ejecutaron migraciones en Staging/Producción ni se alteró la base ordinaria de desarrollo.

La rama parte de `386e7d5`, que ya incorpora `develop`/HT-12. `develop` remoto se verificó en `6b056b3`; es ancestro de esta rama. Antes de esta corrección había siete commits locales por delante de la rama remota de HU-38 y 18 respecto a `develop`; no se hicieron commits, pushes ni merges durante este trabajo.

Para revertir la corrección, retirar conjuntamente sus cambios de código/pruebas/documentación mediante el proceso normal de revisión. No necesita downgrade: la tabla sigue siendo compatible. Revertir HU-38 entera requiere coordinar consumidores de HU-39; el downgrade original elimina la tabla y sus estados, por lo que requiere respaldo y autorización operativa. Este trabajo no ejecuta ese downgrade ni programa cambios remotos.

## Pruebas y resultados locales

Archivos de esta corrección:

- Backend: `backend/src/backend/services/guias.py`, `backend/tests/test_hu38_guias_api.py`, `backend/tests/test_hu38_guias_concurrencia.py` (nuevo).
- Coordinación frontend: `frontend/src/app/AppLayout.tsx`, `frontend/src/components/OnboardingSolicitantes.tsx`, `frontend/src/components/TourProvider.tsx`.
- Motor, contenido y HTTP: `frontend/src/components/recorrido.ts`, `frontend/src/components/onboarding.css`, `frontend/src/pages/onboardingInicial.ts`, `frontend/src/pages/estadoGuias.ts`.
- Pruebas frontend: `frontend/src/components/OnboardingSolicitantes.test.tsx`, `frontend/src/components/TourProvider.test.tsx`.
- Documentación: esta ficha (nueva) y `docs/README.md`.

Backend: `test_hu38_guias_api.py`, `test_hu38_estado_guia_modelo.py` y el nuevo `test_hu38_guias_concurrencia.py`. Cubren ambos solicitantes, roles ORI, ausencia/expiración de sesión, códigos desconocidos, intento de ID ajeno en cuerpo/ruta/query, aislamiento, independencia de guías, estados idempotentes, constraints y carreras de dos dispositivos.

Frontend: `OnboardingSolicitantes.test.tsx` usa driver.js real, HomePage, HeaderNav y rutas controladas. Cubre Ayuda desde Inicio/Mis solicitudes/otra pantalla, DOM diferido, retorno con filtros, estados finales, X/Omitir/Escape, GET/PUT fallidos, reintentos, límite de preparación y cambio de cuenta. `TourProvider.test.tsx` cubre controles, exclusión de recorridos simultáneos, destinos ausentes y cambios del DOM de navegación. Las pruebas existentes de contenido/identificadores/API se conservan. La suite completa incluye la regresión de HT-12.

| Comando | Resultado real |
|---|---|
| `uv run alembic heads` | Una cabeza: a109c8f2b10b |
| `uv run alembic history` | Cadena lineal con b704d4a8102f como predecesora |
| `uv run alembic upgrade head` | Aprobado desde cero en base local aislada |
| `uv run alembic check` | Salida 1: solo detecta el índice parcial preexistente de notificaciones ausente del modelo; sin diferencias propuestas para estado_guia_usuario |
| `uv run pytest tests/test_hu38_guias_api.py tests/test_hu38_estado_guia_modelo.py tests/test_hu38_guias_concurrencia.py -q` | 50 aprobadas, dos avisos de deprecación de TestClient/anyio |
| `uv run pytest -q` | **2147 aprobadas**, 20 avisos de deprecación, 259.76 s |
| `uv run ruff check .` sobre montaje Windows | Falló con 97 EXE002 por bits de ejecución del montaje, incluyendo el archivo de prueba nuevo; no se alteraron modos del repositorio ni se ignoró la regla |
| `uv run --no-sync ruff check .` en copia temporal con modos 0644 | Aprobado, sin errores; mismo backend actual, sin .env, datos ni nueva instalación de dependencias |
| Pruebas específicas frontend (cinco archivos de HU-38) | 48 aprobadas antes de los dos últimos casos; los 50 casos finales de esos archivos aprobaron dentro de la suite completa |
| `npm run typecheck` | Aprobado, salida 0 sobre el candidato final; se corrigió antes el tipado contextual del arreglo de pasos |
| `npm run lint` | Aprobado, salida 0 sobre el candidato final |
| `npm test -- --maxWorkers=2` en montaje Windows | Detectó el caso de caché tardía y se interrumpió por E/S y timeouts de workers; no se registra como ejecución completa aprobada |
| `npm test -- --pool=threads --maxWorkers=2` en copia Linux | **470 aprobadas en 39 archivos**, sin omisiones ni errores no controlados, 46.74 s; incluye los 18 casos del coordinador HU-38 y la regresión HT-12 |
| `npm run build` | Aprobado, salida 0; 226 módulos, chunk JS de 1091.30 kB (>500 kB), aviso de tamaño sin error de build |
| Comparación del frontend de trabajo con la copia validada | Sin diferencias de contenido, excluyendo dependencias, entornos y artefactos generados |
| `git diff --check` | Aprobado, salida 0 |

Las primeras pruebas frontend detectaron dos selectores ambiguos en los auxiliares de prueba (`output` también tiene rol status); se corrigieron esos auxiliares, sin ocultar mensajes de error del producto. La repetición específica aprobó. Los resultados de CI remoto no se infieren de estas ejecuciones locales.

La prueba adicional de escritura tardía encontró una carrera entre limpiar la sesión y desmontar el componente. Se añadió verificación de usuario/rol de la sesión activa antes de registrar o actualizar la caché, además de la comprobación de montaje. La primera suite completa falló en ese nuevo caso; su revalidación se registra en el resultado final. Un intento específico posterior sufrió timeout de arranque del worker y no ejecutó pruebas: no se cuenta como aprobado.

Para completar la validación frontend se copió el candidato con sus dependencias ya instaladas a `/tmp/ori-hu38-frontend-20261101-386e7d5`, sin instalar ni actualizar paquetes ni crear otra rama. El primer intento de copia excluyó por error también los `dist` de dependencias y no pudo iniciar Vitest; se completó esa copia antes de la ejecución aprobada. Se usaron dos threads por recursos del entorno, manteniendo el aislamiento por archivo y todas las pruebas. La suite conserva dos avisos de jsdom sobre navegación a otro documento en pruebas de exportación; esos casos aprueban. No se convierten simulaciones DOM en evidencia de navegador real.

Tras la suite se comparó el contenido del frontend de trabajo y la copia temporal (excluyendo node_modules, entornos y artefactos generados): no hubo diferencias. Sobre ese mismo candidato se ejecutaron de nuevo typecheck, lint y build, todos con salida 0. La corrección de caché tardía y el rechazo del retorno externo están incluidos en los 18 casos finales del coordinador.

`alembic check` se repitió después de terminar pytest y produjo el mismo aviso: propone eliminar `uq_notificacion_pendiente_por_usuario`. Es un índice de HU-33 ya documentado como ajeno al autogenerate en la cabecera de `2fa11b85762d_ht_06_contador_de_codigo_institucional.py`; el modelo de notificaciones coincide con develop. Se conserva el índice: eliminarlo alteraría la deduplicación de notificaciones y excedería HU-38. El upgrade, la cabeza única y los constraints propios de esta HU sí se validaron.

## Limitaciones y aceptación QA pendiente

- Probar contra backend y sesiones reales: ambos solicitantes, usuarios previos al despliegue, distintos dispositivos y pérdida de conexión.
- Probar HT-04 en escritorio y 320/375/768/820/1366 px, menú cerrado/abierto, cambio de tamaño durante un paso, zoom, scroll y tooltips; Chrome/Firefox/Safari y teléfono físico.
- Verificar Tab/Shift+Tab/Enter, foco visible, lector de pantalla, X/Escape/Omitir y recuperación del foco al cerrar en la aplicación completa.
- La navegación manual conserva URL/filtros/retorno validado, no una copia de cambios locales de formularios que no se hayan guardado. Usar la guía contextual de HU-39 para permanecer sobre el formulario; su implementación queda fuera del alcance de esta corrección.
- La integración futura de HU-39 debe repetir sus pruebas contra este motor. No se afirma que HU-39 o HT-14 estén validadas por esta rama.
- El aviso de Ruff del montaje se distingue de los resultados con modos Linux de Git. Confirmar CI remoto antes de integrar.
- No se cambia el estado del backlog ni se declara aceptación de HU-38 por las pruebas automatizadas.
