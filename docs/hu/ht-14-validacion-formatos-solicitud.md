# HT-14 — Validación de formatos de la solicitud

## Objetivo, fuentes y estado

Corregir la incidencia [QA #146](https://github.com/ORI-USB-CALI/ori-manager/issues/146) en el formulario y la API de [HU-11](../hu11-solicitudes.md): identificaciones, teléfonos, país, ciudad y dirección. La incidencia incluye un NIT con letras, teléfonos inválidos y la frase «Hola como estas» como dirección. No se adopta una longitud universal de diez dígitos ni se promete verificar ubicaciones físicamente.

Esta ficha corresponde a la auditoría correctiva del [PR #171](https://github.com/ORI-USB-CALI/ori-manager/pull/171), rama `feature/ht-14-validar-formatos`, sobre `HEAD=47c74fc1a9b72f156117359e274e4a83954f5962`. El merge técnico previo se conserva. HT-14 permanece **En curso, pendiente de revisión del líder técnico y aceptación QA**. La fecha local de inicio de esta revisión es 01/11/2026; los registros de ejecución del contenedor utilizan UTC del 02/11/2026.

H-05 corrige la ausencia de ficha propia: se crea este documento, se enlaza desde `docs/README.md` y se actualiza la correspondencia vigente de HU-39, conservando como históricas sus evidencias de la revisión anterior. Código, pruebas, limitaciones y contingencia se entregan conjuntamente como cambios locales sin commit, push ni merge.

Fuentes: encargo de corrección H-01 a H-05 y CA/RN recibido, issue y PR consultados en GitHub, implementación, migraciones, pruebas y [política documental](../development/documentation-policy.md). No se sustituye el backlog oficial ni se infiere aceptación de una suite verde.

## Criterios de aceptación y reglas de negocio

| Criterio | Comportamiento implementado y evidencia |
|---|---|
| CA-01 Identificación | Reglas según tipo y DV separado. Matrices en `test_ht14_validaciones.py`, `test_ht14_pruebas_validacion.py` y `validacionesSolicitud.test.ts`. |
| CA-02 Teléfonos | Plan de numeración con `phonenumbers`; Colombia sin indicativo e internacional con `+`; extensiones e idempotencia para los cuatro campos. |
| CA-03 País/ciudad | ID existente de `pais`. No existe cobertura comprobada de localidades: ciudad como texto con validación sintáctica. |
| CA-04 Dirección | Longitud/caracteres y número o referencias separadas. Formatos urbanos, rurales e internacionales; límites explicados abajo. |
| CA-05 Borrador/radicación | Borrador parcial permitido; los campos diligenciados deben ser válidos. Al radicar se exigen campos y soportes pendientes. |
| CA-06 Backend | POST, PATCH, radicación y corrección de devueltas validados; 422 por campo y rechazo previo a los efectos de radicación. |
| CA-07 Errores accesibles | Mensaje asociado al control, `aria-invalid`, `aria-describedby`, conservación de lo escrito y posibilidad de corregir/reintentar. |

Se conservan los principios de RN-01 a RN-11 del encargo: backend como autoridad; frontend sin mayor restricción; borradores parciales; identificación por tipo; teléfonos internacionales; país del catálogo; ciudad geográfica solo con fuente confiable; dirección sin nomenclatura colombiana universal ni garantía física; mismas reglas para DEVUELTA; ausencia de correcciones automáticas de históricos; permisos y trazabilidad de HU-11. Las referencias numéricas preexistentes del código no se reinterpretan como una nueva ficha oficial.

## Identificación, NIT y DV

| Tipo | Longitud normalizada | Caracteres y normalización |
|---|---|---|
| NIT | 5–10 | Base de dígitos ASCII `0-9`, retirando puntos/espacios. DV separado, nunca `base-DV` en la base. |
| CEDULA_CIUDADANIA | 5–10 | Dígitos ASCII; retirar puntos/espacios. |
| CEDULA_EXTRANJERIA | 3–15 | Letras ASCII y dígitos; retirar espacios y convertir a mayúsculas. |
| PASAPORTE | 5–20 | Letras ASCII y dígitos; retirar espacios y convertir a mayúsculas. |
| IDENTIFICACION_FISCAL_EXTRANJERA | 3–40 | Letras ASCII, dígitos, espacio, guion, punto y barra; al menos una letra o dígito. |
| OTRO | 3–40 | Mismo repertorio general; colapsar espacios, sin cambiar mayúsculas o separadores significativos. |

Estas reglas validan sintaxis, no autenticidad, titularidad ni existencia del documento en registros oficiales. La diversidad internacional impide certificar la validez jurídica de todos los documentos. El repertorio de los tipos genéricos y los límites nacionales requieren contraste de negocio/QA; no se amplían silenciosamente a nuevos tipos.

El DV tiene un solo dígito ASCII. Cuando existe base válida se comprueba el algoritmo DIAN ya implementado. Un borrador puede contener tipo NIT y DV válido sin base: se comprueba la sintaxis del DV y se pospone el cálculo. Un DV inválido sin base devuelve 422 en lugar de alcanzar el CHECK de PostgreSQL. Al radicar se requiere el DV si el tipo es NIT.

Sin tipo seleccionado, un número escrito recibe la regla general de OTRO; se permite conservarlo parcialmente sin inventar su tipo. Radicar exige el tipo de la contraparte y, para solicitante externo, su tipo de documento. Cambiar de NIT a otro tipo elimina el DV anterior cuando no se envía otro; enviar un DV para un tipo distinto se rechaza. PATCH valida conjuntamente tipo/base/DV nuevos y guardados.

Las restricciones ASCII de base/DV se alinean con frontend y CHECK SQL; no se aceptan dígitos Unicode que puedan llegar a SQL con un formato incompatible. Las identificaciones históricas se siguen consultando sin normalización masiva. La base y el DV se muestran juntos mediante los campos calculados existentes; búsquedas, aliados, snapshots y renovaciones conservan el mecanismo de HT-14.

## Teléfonos, extensiones e idempotencia — H-01

Campos: `telefono_aliado_propuesto`, `contacto_contraparte_telefono`, `supervisor_usb_telefono`, `supervisor_contraparte_telefono`. Todos usan la misma regla del servidor.

- Sin indicativo, se interpreta Colombia (`CO`); con `+`, se usa el país del número. El país de la entidad no determina necesariamente el de sus contactos.
- Se revisa la sintaxis antes de invocar `phonenumbers`, evitando su conversión de letras a dígitos de teclados alfabéticos. Luego se comprueba `is_valid_number`, no solo el tamaño.
- Se admite formato humano con espacios, paréntesis, puntos y guiones; extensión mediante `ext`, `ext.`, `extensión`, `extension` o `x`, de 1 a 6 dígitos.
- Se almacena E.164, con el sufijo `;ext=` cuando hay extensión. Ejemplo: `6025551234 ext 000123` → `+576025551234;ext=000123`. Se conservan ceros de la extensión.
- La entrada admite exactamente ese canónico con extensión: `+` y 2–15 dígitos (primer dígito no cero), `;ext=` y 1–6 dígitos. El plan telefónico sigue validándose. No se acepta una URI `tel:`, parámetros arbitrarios, extensiones vacías o repetidas ni siete dígitos de extensión.
- Se cumple `normalizar_telefono(normalizar_telefono(x)) == normalizar_telefono(x)` para el repertorio admitido. Se prueba también un tercer pase.

El frontend comprueba sintaxis liviana y admite el canónico; el servidor conserva la autoridad del plan nacional/internacional. Se retira el límite frontend de 25 caracteres en la parte humana, que podía rechazar representaciones válidas para backend. Los campos HTTP mantienen el máximo existente de 40 caracteres. No se añade una biblioteca frontend ni se actualiza `phonenumbers`.

Se prueban móviles/fijos colombianos, internacionales, canónicos, extensiones de 1/6 dígitos y con ceros, errores alfabéticos/indicativos, recuperación/edición del dato guardado y ciclos POST→GET→PATCH→radicar, incluidos los cuatro teléfonos de una DEVUELTA.

Una comprobación adicional contra los ejemplos regionales/por tipo de `phonenumbers` ejecutó 2754 combinaciones admitidas, con y sin extensión `000123`, sin fallos de idempotencia. Es una exploración de metadata de la dependencia instalada, no 2754 tests Pytest adicionales ni una enumeración de todos los números posibles.

## País y ciudad

`GET /api/paises` requiere sesión y devuelve el catálogo ordenado para los formularios existentes, sin permisos nuevos. La entrada utiliza `pais_aliado_propuesto_id`; el servidor comprueba la FK y conserva el nombre de catálogo en `pais_aliado_propuesto` para consumidores e historial. Un ID desconocido produce 422 por campo. El cliente no puede enviar el nombre libre como sustituto del ID.

La tabla `pais` existe desde `e20406a1b2c3`, anterior a HT-14, con ID y unicidades de código ISO/nombre. `0b2fb1bed5b2` contiene 249 entradas y agrega solo faltantes por código o nombre, conservando valores y alias existentes. Es un catálogo versionado; cambios geopolíticos o de denominación requieren mantenimiento aprobado, no una verificación geográfica en tiempo real.

No existe una fuente de localidades integrada con cobertura demostrada. Se permite ciudad de 2 a 120 caracteres con letras, espacios, guion, punto o apóstrofo; empieza con una letra. Se normalizan espacios y composición Unicode NFC. No se afirma que «Cali» o cualquier otra cadena sintácticamente válida exista en el país elegido. El frontend cuenta caracteres Unicode, evitando ser más restrictivo que Python para letras fuera del plano básico.

## Política de direcciones y límites — H-02

Regla objetiva común frontend/backend:

1. Normalizar espacios y composición Unicode NFC.
2. Entre 5 y 200 caracteres, al menos una letra, y repertorio existente de letras/números/espacios y `# - . , / ° º ( ) '`.
3. Contener un número, **o** al menos dos segmentos con letras separados por coma o barra. Los segmentos vacíos no cuentan.

No hay lista negra del ejemplo QA ni palabras obligatorias como Calle/Carrera. Se admiten los ocho casos mínimos del encargo: `Calle 5 # 38-25`, `Cra. 122 No. 6-65, Pance`, `Vereda La Esperanza, Finca El Roble`, `Km 3 vía Cali/Jamundí`, `1600 Amphitheatre Pkwy`, `Apartado postal 123`, `Edificio Central, oficina 402`, `Finca El Roble, zona rural de Pance`. También se prueban `The Old Rectory, High Street`, referencias separadas por barra y texto japonés con número.

«Hola como estas», una palabra repetida sin referencia, texto vacío, solo símbolos, HTML y longitudes fuera de rango se rechazan. El mensaje pide un número o referencias separadas; permite corregir sin exigir nomenclatura urbana.

**Tensión y límite explícitos:** una frase con un número o coma puede superar esta comprobación; no se puede distinguir universalmente una dirección real de texto arbitrario sin una fuente fiable. A la inversa, un lugar identificable por su nombre solo (p. ej. «Campus universitario») necesita una localidad o referencia adicional («Campus universitario, Pance») para superar la política. Esto es una condición de estructura/completitud, no prueba de inexistencia. QA/negocio deben validar este equilibrio con direcciones institucionales reales. No se consulta un geocodificador, no se exige dirección colombiana ni se promete un cumplimiento geográfico perfecto de CA-04/RN-07/RN-08.

## Operaciones, errores y transacciones

| Operación | Validación y persistencia |
|---|---|
| POST `/api/solicitudes` | Permite borrador parcial; valida campos enviados antes de agregar la solicitud. Los datos precargados del perfil conservan su carácter de snapshot histórico. |
| PATCH `/api/solicitudes/{id}` | Solo propietario y BORRADOR/DEVUELTA. Valida los cambios y dependencias de identificación antes de asignarlos; un campo inválido evita guardar los otros cambios del mismo PATCH. |
| POST `/api/solicitudes/{id}/radicar` | Revalida todos los campos persistidos, incluso históricos; exige campos y representación legal. Con errores devuelve 422 antes de modificar estado/fechas, crear versión o emitir efectos de radicación. |
| DEVUELTA | Mismas reglas en guardar y volver a radicar. Conserva observaciones y versiones anteriores; solo la corrección válida permite crear la nueva versión radicada. |
| Consultar/historial | Lectura de snapshots y datos previos sin modificaciones automáticas. |

El formulario conserva su flujo de HU-11: al radicar primero puede guardar un PATCH válido y luego solicitar la radicación. Son dos operaciones HTTP; un 422 de radicación no revierte un guardado previo exitoso. La garantía transaccional se refiere a cada operación, no a una transacción conjunta ficticia entre ambos endpoints.

Los errores del servicio usan `422` con `detail.message` y `detail.errors[campo]`. Tipos, campos desconocidos, tamaños y correo inválido pueden devolver la lista estándar de FastAPI/Pydantic con `loc`; el formulario acepta ambos contratos. Los mensajes no contienen SQL, credenciales ni detalles internos. No se reemplaza el 422 por 500 para un DV parcial inválido.

El control visible mantiene `aria-invalid`, `aria-describedby` y el ID del mensaje correspondiente, incluidos selects. Se conservan valores y errores de otros campos al corregir uno. Campos vacíos no activan validadores de formato; la obligatoriedad se exige al radicar. No se bloquea el guardado por omitir obligatorios. El frontend no sustituye la validación de API directa.

## Seguridad, HU-11, HU-38 y HU-39 — H-04

No se alteran roles ni permisos. Continúan autenticación, visibilidad/propiedad y permisos existentes de crear, editar, radicar y gestionar recibidas. Un usuario no puede PATCH/radicar una solicitud ajena. La suite de regresión incluye HU-11, devoluciones HU-07, versiones HT-02, auditoría y notificaciones.

Se conserva `AyudaRadicacion`, la apertura exclusivamente manual de `GUIA_RADICACION`, el motor compartido, los ocho `data-tour`, estados independientes de `ONBOARDING_INICIAL`, caché `['guias', usuarioId, guia]`, reintentos y protecciones de sesión/respuestas tardías. `guias.ts` sigue eliminado. No hay cambios en `OnboardingSolicitantes`, `TourProvider`, `recorrido`, `estadoGuias`, `AyudaRadicacion`, navegación HT-04 o permisos.

Solo se actualiza la configuración textual de la guía: tipo/base/DV separado, país del catálogo, ciudad sin validación geográfica, estructura de dirección, teléfonos internacionales/extensiones, errores por campo y borradores parciales con formatos válidos. Se conserva la explicación de guardar/radicar, corrección de DEVUELTA y ausencia de escritura automática al recorrer la ayuda.

Las pruebas usan componentes/motor reales en JSDOM, con ambos roles, cierre X/Escape/Omitir, campos parciales o con errores, aislamiento de usuarios/logout, desktop/menú colapsado y retorno HT-12. Son evidencia de eventos y decisiones; no certifican WCAG 2.1 AA, layout móvil ni contraste real.

## Migraciones y contingencia — H-03

Cadena lineal, una sola cabeza:

`a109c8f2b10b` → `417e8d1cf636` → `0b2fb1bed5b2 (head)`.

`417e8d1cf636` agrega campos nulos de tipo de documento, DV y país por FK; conserva el país histórico en texto. No realiza backfill ni modifica automáticamente solicitudes/aliados/versiones. Su archivo y SQL permanecen sin cambios en esta corrección.

**Cambio explícito de mantenimiento de `0b2fb1bed5b2`:** se reemplaza únicamente su downgrade destructivo por una operación sin cambios de datos. Su `upgrade()`, catálogo, ID y predecesora no cambian. No había trazabilidad que identificara qué países insertó HT-14; coincidir por ISO o estar sin referencias no demuestra procedencia. Se conservan todos los países, incluidos los insertados por HT-14, al retroceder a `417e8d1cf636`. Reaplicar el upgrade no los duplica. No se añade una nueva revisión porque no existe un cambio de esquema/datos de avance que deba aplicarse a entornos ya en esa revisión; una revisión posterior tampoco repararía por sí sola el código de downgrade anterior.

La modificación no se presenta como si jamás se hubiera aplicado la migración: cualquier instalación que ya esté en `0b2fb1bed5b2` debe recibir el artefacto corregido antes de considerar un rollback. Alembic registra el ID, no la procedencia de filas ni un checksum del script. Un artefacto viejo conserva el DELETE peligroso y no debe utilizarse para la contingencia.

Evidencia remota de solo lectura: `develop=3b5700dc517b6b82c1363bcfbddc4066ecaebc01` y [ejecución de CI/deploy 41370524386](https://github.com/ORI-USB-CALI/ori-manager/actions/runs/41370524386); su job Staging DB Migrations terminó en `a109c8f2b10b`. Esto demuestra que ese despliegue no aplicó HT-14, pero no descarta intervenciones manuales ni certifica el estado actual de Producción. No se consultaron conexiones ni se ejecutaron migraciones sobre bases remotas.

Plan de reversión:

1. Preferir reversión del código de aplicación conservando columnas nullable y catálogo; revisar compatibilidad y preservar los snapshots.
2. Respaldar y verificar restauración antes de cualquier decisión de rollback de esquema. Asegurar que el artefacto incluya el downgrade conservador.
3. Si solo se retrocede `0b2fb1bed5b2` → `417e8d1cf636`, el catálogo y sus referencias permanecen completos.
4. **No es una reversión sin pérdida bajar `417e8d1cf636` → `a109c8f2b10b`:** se eliminan columnas nuevas (DV, tipo, país por ID). Requiere plan aprobado de exportación/restauración o recuperación hacia adelante. No hacerlo en Staging/Producción por esta auditoría.
5. Un país creado por HT-14 no se elimina por deducción. Cualquier depuración futura necesita trazabilidad y aprobación específica.

`test_ht14_migraciones.py` crea un nombre aleatorio `ori_ht14_migracion_<uuid>` en PostgreSQL local y solo elimina esa base creada por la prueba. Rechaza hosts remotos. Ejecuta Alembic real por subproceso: upgrade a HU-38, carga sintética preexistente, upgrade head, downgrade del catálogo, reaplicación, downgrade de columnas y nueva reaplicación. Conserva IDs/alias de cuatro países previos (incluido CO sin referencias y un país institucional), aliado y solicitud DEVUELTA históricos. Comprueba inserción de faltantes, unicidad, FK de aliado y solicitud, tipo/DV inválidos, campos nulos, historial sin backfill y retorno a una sola revisión. La reversión de columnas se ensaya exclusivamente con datos sintéticos.

## Diagnóstico de Vitest

`package.json` ejecuta `vitest run`; CI llama `npm test`. El `include` anterior era `src/**/*.test.tsx`, por lo que `validacionesSolicitud.test.ts` no se descubría. La comparación de `vitest list --filesOnly --json` contra archivos existentes identificó una omisión real, no un efecto de filtros manuales.

El cambio mínimo es `src/**/*.test.{ts,tsx}`. No se renombra, duplica ni omite ninguna suite; no cambian `exclude`, aislamiento, assertions ni el workflow.

| Muestra ejecutada | Archivos | Pruebas | Resultado |
|---|---:|---:|---|
| Código inicial y patrón original | 46 | 536 | 536 aprobadas, 0 fallidas/omitidas. |
| Mismas pruebas iniciales; solo patrón corregido en copia temporal | 47 | 587 | 587 aprobadas, 0 fallidas/omitidas; +51 validadores. |
| Validadores nuevos contra implementación original | 1 | 79 | 71 aprobadas y 8 fallidas; reproduce H-01/H-02. |
| Candidato corregido, suite predeterminada con dos workers | 47 | 624 | 624 aprobadas, 0 fallidas/omitidas. |
| Selección explícita HT-14/guía (5 archivos) | 5 | 118 | 118 aprobadas; incluye 81 casos unitarios de formatos. |

## Validaciones ejecutadas y reproducibilidad de H-01 a H-05

Base principal de esta auditoría: **`ori_manager_ht14_audit_g4ib7nrf`**, creada expresamente en `ori-manager-db-1`, PostgreSQL **18.6** local; Python **3.13.17**. Se conserva localmente para inspección del auditor. Las pruebas de migración crean y retiran únicamente sus bases aleatorias propias. No se reutiliza ni elimina una base institucional/local ajena.

| Comando/alcance | Resultado comprobado |
|---|---|
| `uv sync --frozen` en `/workspace/backend` | Correcto; lock y dependencias sin cambios. |
| Reproducción backend H-01/H-02/H-03 antes de corregir | 20 fallidas, 25 aprobadas y 190 no seleccionadas por el filtro intencional. No se presenta como corrida completa. |
| Reproducción de DV parcial/identificación solo de signos | 7 fallidas y 102 no seleccionadas antes de corregir. |
| Selección backend HT-14/core/API/migración/HU-39 | 297 aprobadas, 0 fallidas, 2 avisos de deprecación. |
| `uv run ruff check .` directamente en montaje | Salida 1: 80 EXE002 por modos del montaje, único código de error encontrado. |
| `uv run --no-sync ruff check .` en copia temporal con modos Git | Aprobado, sin reglas ignoradas. |
| `uv run alembic heads` / `uv run alembic history` | Correctos; única cabeza `0b2fb1bed5b2`, cadena lineal. |
| `uv run alembic upgrade head` desde base local vacía | Correcto, hasta `0b2fb1bed5b2`. |
| `uv run pytest --junitxml=/tmp/ori-ht14-audit-g4ib7nrf/backend-final.xml --tb=short` completo | 2509 aprobadas, 0 fallidas/omitidas, 20 avisos de deprecación, 300.76 s; incluye HT-14, HU-11, HU-38/HU-39, HT-02, seguridad y trazabilidad. |
| `npm run typecheck` | Aprobado. |
| `npm test -- --pool=threads --maxWorkers=2` (reporte JSON) | 624 aprobadas en 47 archivos, 0 omitidas/fallidas. |
| `npm run lint` | Aprobado. |
| `npm run build` | Aprobado, 230 módulos; aviso de chunk JS de aproximadamente 1108 kB (>500 kB). |
| Inventario final de Vitest frente a archivos existentes | 47/47 archivos descubiertos, incluido `validacionesSolicitud.test.ts`; sin omisiones. |
| Cotejo de frontend/backend con la copia validada | Sin diferencias de contenido, incluidos archivos nuevos y modificaciones sin commit. |
| `git diff --check`, archivos sin fusionar y búsqueda de marcadores | Correctos, sin conflictos ni marcadores. |

Dentro de las 2509 pruebas completas hay 308 de HT-14 (seis archivos), 30 de HU-11, 50 de HU-38 y 54 de HU-39, además de HU-07, HT-02 y demás regresiones. Son subconjuntos de la misma corrida, no ejecuciones adicionales sumadas al total. Las bases aleatorias de las pruebas de migración quedaron retiradas; se verificó que no quedan nombres `ori_ht14_migracion_%`.

Estado Git final comprobado: rama original, HEAD `47c74fc1a9b72f156117359e274e4a83954f5962`, comparación `origin/develop...HEAD = 0 15`, 17 archivos existentes modificados y dos nuevos, sin eliminaciones, sin cambios staged y sin nuevo commit/push/merge. La referencia de develop se contrastó mediante lectura de GitHub. Se preservan los mecanismos de HU-38/HU-39, `417e8d1cf636`, permisos y lockfiles.

Las comprobaciones frontend se ejecutaron en `/tmp/ori-ht14-audit-g4ib7nrf/frontend`, copia del contenido real (incluidos cambios sin commit y pruebas nuevas). Se reutilizó `node_modules` Linux ya instalado tras comprobar que `package-lock.json` coincide byte a byte; `npm ci` no era necesario. No se cambió el lock. Dos workers `threads` controlan recursos sin excluir suites. Se conserva aislamiento por archivo. Los avisos JSDOM de navegación de documentos son preexistentes y no equivalen a pruebas visuales.

Para Ruff se utilizó `/tmp/ori-ht14-audit-g4ib7nrf/backend`, con los modos de `git ls-files --stage` para archivos versionados y 0644 para nuevos; no se cambian permisos del repositorio. Esta aprobación corresponde a la copia temporal, no al montaje directo. Antes de entregar se compara otra vez su contenido con el candidato.

Comandos de referencia (crear previamente una base local nueva y sustituir su nombre):

```sh
cd /workspace/backend
uv sync --frozen
DATABASE_NAME=<base_local_nueva> uv run alembic upgrade head
DATABASE_NAME=<base_local_nueva> PUBLIC_FRONTEND_URL=http://localhost:5173 uv run pytest
uv run ruff check .
uv run alembic heads
uv run alembic history

cd /workspace/frontend
npm run typecheck
npm test -- --pool=threads --maxWorkers=2
npm test -- --pool=threads --maxWorkers=2 src/pages/validacionesSolicitud.test.ts src/pages/SolicitudPage.validaciones.test.tsx src/pages/SolicitudPage.guia-validaciones.test.tsx
npm run lint
npm run build
```

## Riesgos residuales y QA pendiente

- Validar con negocio el equilibrio de H-02 y direcciones rurales/internacionales reales. Una referencia sin número/localidad adicional puede requerir completar la dirección; una frase estructurada puede superar el filtro sin ser una ubicación real.
- Ciudad y dirección solo tienen validación sintáctica. El catálogo no aporta una fuente de localidades ni garantiza correspondencia país/ciudad o existencia física.
- Los históricos no se modifican por upgrade ni consulta. PATCH valida lo enviado; radicar revalida todo. Solicitudes antiguas pueden necesitar país por ID, tipo/DV y corrección explícita de formatos antes de su siguiente radicación.
- Confirmar cobertura de documentos internacionales y límites nacionales con QA; no se autentican identificaciones ni se consultan autoridades emisoras.
- La idempotencia depende de conservar la sintaxis canónica y la misma biblioteca/metadata. Una actualización futura de `phonenumbers` debe volver a probar datos históricos.
- Comprobar Chrome/Firefox/Safari, móvil físico, teclado/lector de pantalla, zoom, foco, contraste y menús HT-04. El inventario de herramientas de esta sesión no ofreció navegadores ni aplicaciones; no se certifica validación visual real ni WCAG completa.
- Una intención de guía no sincronizada sigue siendo local, con reintento explícito, sin garantía offline. No se cambia HU-38/HU-39 para esta corrección.
- Antes de Staging/Producción, revisar artefacto de migración, backup y recuperación; confirmar revisión actual de cada entorno por el procedimiento aprobado. No se autoriza su despliegue ni un downgrade remoto.
- Advertencia de bundle y deprecaciones backend son riesgos de mantenimiento; no se actualizan dependencias ajenas a HT-14.
- Resultado técnico pendiente de auditoría independiente, CI del candidato y aceptación QA. Esta ficha no declara HT-14 terminada.

## Microcorrección H-06 — Unicode y límites canónicos

Continuación local sobre `47c74fc`, sin repetir el merge ni reimplementar H-01 a H-05. Los resultados anteriores corresponden a aquella auditoría; este apartado registra el candidato posterior de H-06.

### Causas reproducidas

- `SolicitudCamposEditables` limitaba ciudad/dirección a 120/200 sobre el texto recibido, antes del NFC y colapso de espacios que realizaban servicio y frontend. Por ejemplo, 120 secuencias `e + U+0301` tienen 240 puntos de código recibidos, pero 120 tras NFC.
- Python `re` con `\w` no incluye todas las marcas Unicode; el frontend permitía `\p{M}`. Una letra con punto inferior sin composición, como `q + U+0323`, y nombres como `मुंबई` podían aceptarse en cliente y rechazarse en servidor. El frontend también admitía marcas sueltas tras separadores.
- Python y JavaScript no tienen exactamente el mismo conjunto de `\s`/`trim`. Algunos controles se colapsaban en Python; el BOM se borraba en JavaScript. Además, el formulario ejecutaba `trim()` antes de llamar al validador, ocultando el carácter que debía examinarse.
- El límite HTTP original de 40 para identificaciones se aplicaba antes de retirar separadores o colapsar espacios. En un PATCH que envía solo el número, el esquema no dispone del tipo guardado para calcular su forma canónica.

### Corrección limitada y política compartida

`SolicitudEntrada`, base exclusiva de POST/PATCH, normaliza ciudad/dirección **antes** del `max_length` heredado. Se conserva el modelo de lectura, las columnas y los límites 120/200. `normalizar_texto_ubicacion` aplica la misma operación en esquema y servicio; el cliente usa su equivalente `normalizarUbicacion` para validar y serializar. El formulario conserva lo escrito en pantalla.

La operación colapsa separadores de presentación a espacio ASCII y aplica NFC; no aplica NFKC, no elimina diacríticos ni cambia mayúsculas. Se cuentan **puntos de código**, como Python `len` y JavaScript `[...texto].length`, después de normalizar. No se cuentan bytes, unidades UTF-16 ni grafemas visuales. Una marca que no se compone sigue contando para el máximo.

La política de ubicación en ambas capas admite:

- Letras de categorías Unicode `L` y marcas `M` únicamente después de una base de letra, incluyendo secuencias de varias marcas.
- Los números y signos de dirección ya admitidos. La regla estructural de H-02 (número o referencias separadas) permanece igual; las marcas no crean una referencia nueva.
- Espacios Unicode de presentación y TAB/LF/VT/FF/CR convertidos en un espacio simple. Se conserva la compatibilidad del tabulador documentada en H-02; esos controles no se persisten como tales.

Se rechazan marcas iniciales o tras espacio/signo/número, NUL, separadores C0 no admitidos, NEL, BOM, ancho cero, controles bidireccionales, HTML y símbolos ajenos. No se borran silenciosamente para convertirlos en otra entrada válida. La clasificación de letras usa `unicodedata`, sin añadir dependencias.

En las dos identificaciones de entrada se difiere la comprobación de tamaño al servicio existente: allí se normaliza según el tipo efectivo, incluso si procede de la fila almacenada. **No se amplían sus longitudes canónicas**: NIT/CC 5–10, CE 3–15, pasaporte 5–20 y fiscal/OTRO 3–40. Las columnas y el modelo de lectura conservan 40; el esquema HTTP de entrada deja de anunciar 40 como límite del texto sin normalizar. Las validaciones por tipo, caracteres y DV no cambian. Se cubren ambos grupos de identificación y los seis tipos, incluyendo rechazo atómico al exceder el límite canónico.

Los históricos no se normalizan al leer, editar otro campo ni radicar: esta última operación los revalida sin aplicar automáticamente los ajustes. Solo un cambio explícito del campo guarda su canónico. Se prueban tanto históricos válidos con espacios/NFD como valores Unicode inválidos que deben conservarse y bloquear la radicación sin efectos parciales.

### Archivos y evidencia H-06

Cambios de esta microcorrección: `backend/src/backend/core/validaciones.py`, `backend/src/backend/schemas/solicitud.py`, `backend/tests/test_ht14_pruebas_validacion.py`, nuevo `backend/tests/test_ht14_unicode.py`, `frontend/src/pages/validacionesSolicitud.ts`, `frontend/src/pages/validacionesSolicitud.test.ts`, `frontend/src/pages/SolicitudPage.tsx`, `frontend/src/pages/SolicitudPage.validaciones.test.tsx` y esta ficha.

No cambia la normalización telefónica, la cadena ni los scripts de migración, las reglas de DV, los permisos, los estados ni los mecanismos de HU-38/HU-39. No se actualizan dependencias. Los cambios previos de H-01 a H-05 y la intención de añadido de los dos archivos anteriores se conservan.

| Comprobación | Resultado realmente ejecutado |
|---|---|
| Reproducción backend anterior a H-06 | 37 fallidas, 22 aprobadas; 109 casos no seleccionados por filtro. |
| Validadores frontend originales frente a casos nuevos | 120 casos: 114 aprobados y 6 fallidos. |
| Formulario con `trim()` previo | 14 casos: 10 aprobados y 4 fallidos. |
| `pytest -q tests/test_ht14_unicode.py tests/test_ht14_pruebas_validacion.py -k h06` corregido | 63 aprobadas; 109 no seleccionadas, 0 omitidas/fallidas. |
| Selección explícita de validadores/formulario frontend | 134 aprobadas en 2 archivos, 0 omitidas/fallidas. |
| Suite frontend completa, dos workers `threads` | 667 aprobadas en 47 archivos, 0 omitidas/fallidas. |
| TypeScript, ESLint y build | Aprobados; persiste el aviso de tamaño de bundle. |
| Ruff final directamente en el montaje Windows | 81 EXE002, sin otros códigos de error. No se presenta como aprobación directa. |
| Ruff en copia con modos de Git, sin reglas ignoradas | Aprobado tras corregir dos imports. |
| `uv run pytest --junitxml=/tmp/ori-ht14-h06-rj4nql09/backend-final.xml --tb=short` completo | 2572 aprobadas, 0 fallidas/omitidas, 20 avisos de deprecación; 292.85 s. |
| Cotejo del código final con la copia validada | Sin diferencias de contenido frontend/backend. |
| Preservación de H-01 a H-05 | Migraciones y mecanismos de guía idénticos al inicio de H-06; funciones de teléfono/identificación y modelos de lectura con AST sin cambios. |
| Git | HEAD `47c74fc`, comparación con `origin/develop` `0 15`, `git diff --check` correcto y sin conflictos; sin commit, push, ramas nuevas ni modificaciones del índice. |

Entorno local exclusivo: PostgreSQL `ori_manager_ht14_h06_rj4nql09`; copia reproducible `/tmp/ori-ht14-h06-rj4nql09`, con dependencias Linux existentes y lockfile comprobado. Las pruebas nuevas abarcan NFC, espacios antes de longitud, máximos exactos/excedidos, letras internacionales y marcas sin composición, controles inválidos, POST/PATCH/radicación, errores por campo, ausencia de efectos parciales y preservación de históricos. El test de identificación expira la caché de la Session compartida de la fixture antes de simular una nueva petición; producción abre una Session por petición. No se cambia el servicio de documentos.

Riesgos residuales de H-06: se conserva la validación sintáctica, sin verificar geografía. Unicode depende de las tablas de los runtimes; futuras actualizaciones deben repetir estos casos. Los límites se refieren a puntos de código normalizados, no a caracteres visuales. La aceptación de QA y la validación visual/assistiva siguen pendientes; H-06 no certifica el cierre de HT-14.

## Corrección puntual H-07 — Separadores de identificación, DV y teléfono

Continuación sobre `HEAD=47c74fc`, conservando las correcciones locales H-01 a H-06. No hay nuevo merge, commit, push, cambios de dependencias ni modificaciones de migraciones.

### Causa y reproducciones

Python `\s`, `str.split()` y `strip()` no tienen el mismo repertorio que JavaScript `\s`, `split()` y `trim()`. En NIT/CC, `900\u0085123456` y `900\u001c123456` podían convertirse en una base válida en Python, mientras `900\ufeff123456` podía hacerlo en JavaScript. CE/pasaporte y fiscal/OTRO presentaban el mismo problema al eliminar o colapsar espacios. El DV podía perder controles de sus bordes antes de comprobar el dígito o antes de `max_length=1`.

Se demostró también la discrepancia en teléfonos: el frontend original falló seis comprobaciones con BOM/TAB, y el backend aceptaba controles que su sintaxis preliminar debía rechazar. Por esta evidencia se corrigen sus separadores y preprocesamiento; no se cambia `phonenumbers`, E.164, extensiones ni reglas nacionales/internacionales.

Pydantic y el formulario tenían otra oportunidad de ocultar caracteres mediante `strip()`/`trim()` antes del validador. Esto afectaba tanto a la entrada como a la serialización de una lectura histórica: una respuesta podía presentar una identificación aparentemente limpia aunque el registro conservara un control. H-07 preserva el carácter indebido para que se rechace o se señale, sin reescribir la fila.

### Conjunto explícito aprobado

Se usan exactamente los **17 espacios horizontales Unicode Zs** en ambas capas:

`U+0020`, `U+00A0`, `U+1680`, `U+2000–U+200A`, `U+202F`, `U+205F`, `U+3000`.

No se usa `\s` como contrato implícito. Se mantienen espacio normal, NBSP, espacio de cifra, espacio fino/estrecho y otros separadores horizontales ya admitidos. **No son separadores de identificación** TAB, LF, CR, VT, FF, los separadores de línea/párrafo U+2028/U+2029, NEL U+0085, FS U+001C, BOM U+FEFF ni caracteres de formato como ancho cero o control bidireccional. Aunque algunas funciones de biblioteca los traten como whitespace, no se eliminan ni convierten en espacios válidos.

| Campo/tipo | Tratamiento de separadores legítimos |
|---|---|
| NIT / cédula de ciudadanía | Retirar puntos y los espacios horizontales enumerados. Mantener la base ASCII y longitudes aprobadas. |
| Cédula de extranjería / pasaporte | Retirar solo los espacios enumerados, y conservar la conversión a mayúsculas existente. El punto sigue sin ser separador permitido para estos tipos. |
| Fiscal extranjera / OTRO | Recortar bordes y colapsar únicamente los espacios enumerados a un espacio ASCII, conservando NFC, repertorio y longitud. |
| DV | Recortar únicamente esos espacios en bordes. Dentro debe quedar un único dígito válido; no se eliminan espacios interiores para unir dígitos. |
| Teléfonos | Recortar/foldar esos espacios a espacio ASCII antes de revisar sintaxis y plan telefónico. La representación `+...;ext=...` y sus ceros de extensión permanecen idempotentes. |

Se conservan `900.123.456`, `1.144 123.456` y los formatos internacionales del contrato. Los límites de H-06 siguen aplicándose al valor canónico según el tipo; los cuerpos inválidos no se vuelven válidos porque un preprocesador oculte su carácter indebido.

### Integración y alcance

- `core/validaciones.py` declara el repertorio, el recorte explícito y su uso por los seis tipos, DV y teléfonos. La búsqueda de identificaciones utiliza el mismo recorte y ya no elimina controles del término recibido.
- `schemas/solicitud.py` protege los dos números de identificación, ambos DV y los cuatro teléfonos antes de los límites/validadores. El modelo de lectura también conserva los caracteres indebidos; no se normalizan automáticamente datos históricos. Los otros campos conservan su comportamiento.
- `validacionesSolicitud.ts` comparte el repertorio explícito con el servidor. El formulario aplica el recorte seguro al validar/enviar esos ocho campos y al leer la base para comprobar el DV; conserva lo escrito y el vínculo accesible del error.
- La política de espacios, NFC, marcas, longitud y estructura de **ciudad/dirección permanece exactamente en H-06**. Sus tabuladores de presentación siguen normalizándose según aquel contrato; son campos con una política distinta de identificaciones/teléfonos, no una ampliación de H-07.
- No cambian permisos, transacciones, estados, versiones, documentos ni motores/estados de HU-38/HU-39. Una corrección explícita válida de DEVUELTA permite volver a radicar; una operación inválida no crea efectos parciales.

Archivos H-07: `backend/src/backend/core/validaciones.py`, `backend/src/backend/schemas/solicitud.py`, nuevo `backend/tests/test_ht14_separadores.py`, `backend/tests/test_ht14_pruebas_validacion.py`, `frontend/src/pages/validacionesSolicitud.ts`, nuevo `frontend/src/pages/validacionesSolicitud.separadores.test.ts`, `frontend/src/pages/SolicitudPage.tsx`, `frontend/src/pages/SolicitudPage.validaciones.test.tsx` y esta ficha. No se generan ni incluyen archivos `.patch`.

### Pruebas y resultados H-07

Los casos cubren los seis tipos, los 17 espacios admitidos, controles al inicio/interior/final, NEL/FS/BOM, ancho cero/bidi/TAB, terminadores finales, DV y ambos grupos de identificación, los cuatro teléfonos, POST/PATCH, lectura histórica sin limpieza silenciosa, radicación fallida sin cambios de estado/versiones/auditorías/notificaciones y corrección de DEVUELTA. Las comprobaciones de terminadores finales no encontraron otra discrepancia y se conservaron como regresión; no motivaron cambios adicionales de implementación.

| Ejecución | Resultado real |
|---|---|
| Backend anterior, nuevos casos unitarios | 102 fallidas y 98 aprobadas: reproducción del defecto. |
| API anterior, nuevos escenarios | 30 fallidas y 14 aprobadas; 132 no seleccionadas por filtro. |
| Frontend anterior, nuevos validadores | 48 fallidas y 104 aprobadas; seis fallos de teléfono demostrados. |
| Formulario anterior | 8 fallidas y 30 aprobadas, por ocultación del BOM. |
| `pytest ... -k h07` final | 251 aprobadas, 0 fallidas/omitidas; 132 no seleccionadas. |
| Selección explícita frontend H-07/formulario | 197 aprobadas en dos archivos, 0 fallidas/omitidas. |
| Suite frontend completa, dos workers `threads` | 850 aprobadas en 48 archivos, 0 fallidas/omitidas. |
| TypeScript, ESLint y build | Aprobados; persiste el aviso de bundle >500 kB. |
| Ruff directamente en el montaje | 82 EXE002, ningún otro código de error. |
| Ruff en copia con modos de Git, sin ignorar reglas | Aprobado. |
| `uv run pytest --junitxml=/tmp/ori-ht14-h07-ggn8tnrz/backend-final.xml --tb=short` completo | 2823 aprobadas, 0 fallidas/omitidas, 20 avisos de deprecación; 654.29 s en el entorno local. |
| Cotejo final con la copia de código validada | Sin diferencias frontend/backend; nueve archivos en el alcance específico H-07. |
| Preservación H-01 a H-06 | Migraciones, servicio transaccional, validadores de ciudad/dirección H-06, algoritmo de DV y mecanismos HU-38/HU-39 conservados; mismas reglas de plan telefónico y salida canónica. |
| Git | HEAD `47c74fc`, comparación con `origin/develop` `0 15`; `git diff --check` correcto, sin conflictos ni `.patch`, sin commit/push/merge ni modificaciones del índice. |

Entorno exclusivo: base PostgreSQL local `ori_manager_ht14_h07_ggn8tnrz`; copia de validación `/tmp/ori-ht14-h07-ggn8tnrz`, con modos de Git y dependencias Linux existentes tras cotejar el lockfile. No se ejecutan migraciones remotas ni se modifica una base compartida.

Riesgos residuales: una identificación o teléfono histórico con controles ahora necesita corrección explícita para su siguiente escritura/radicación, conservando el registro original hasta entonces. Los espacios permitidos son una lista explícita, no una clasificación cambiante de `\s`; cualquier ampliación exige revisar ambas capas y estas pruebas. Se mantiene la autoridad del backend sobre los planes telefónicos y todas las limitaciones/QA pendientes de H-01 a H-06. No se declara aceptación QA ni cierre de HT-14.
