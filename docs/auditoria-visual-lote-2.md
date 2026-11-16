# Lote 2 — Auditoría de navegación secundaria y tablas

Inventario previo a implementación, base `origin/develop` `5bd399b` (incluye PR #196). Se inspeccionaron router, AppLayout, todos los usos de DataTable y tablas nativas, contenedores, estilos de columnas y enlaces de retorno. Propuestas limitadas a presentación.

| Archivo / ruta / layout | Problema identificado | Causa técnica | Solución propuesta y aplicada / excepción |
|---|---|---|---|
| RevisionesJuridicasPage — /revisiones-juridicas / normal | Diez columnas en 1132px útiles como máximo; solo objeto tiene mínimo específico; responsable, fechas y acciones heredan mínimos de 7rem | Ruta sin handle wide; mínimos genéricos salvo objeto | Layout wide existente; variante acotada de tabla densa y clases por tipo de columna |
| RevisionesContrapartePage — /revisiones-contraparte / normal | table-wrapper sin definición CSS; table sin clase; encabezado de acción vacío, sin región de scroll | Contenedor sin CSS y table sin clase compartida | Reutilizar DataTable, conservar filas/destinos, encabezado Acciones y columnas dimensionadas |
| ConsultaConveniosPage — /convenios / wide | Nueve columnas con solo mínimos genéricos; objeto recortado a dos líneas sin consulta accesible del texto completo en la tabla | Columnas genéricas y line-clamp de dos líneas | Variante densa, columnas por contenido y objeto completo, sin cambiar filtros o acciones |
| SolicitudesRecibidasPage — /ori/solicitudes / wide | Nueve columnas; nombres/correos y acciones múltiples sin espacio propio | Mínimos genéricos para nombre/correo y varias acciones | Variante densa y mínimos por contenido |
| MisSolicitudesPage — /solicitudes / normal | Seis columnas, acciones consecutivas y fecha comparten mínimo genérico | Mínimo común para fecha y varios enlaces consecutivos | Variante densa con columnas específicas; conservar paginación y filtros |
| AliadosPage — /aliados / normal | Nombre, identificación y acciones sin dimensionamiento específico | Mínimos genéricos en nombre e identificación | Variante densa con espacio para nombre y documentos |
| AliadoDetallePage — /aliados/:aliadoId / normal | Tabla asociada sin nombre accesible, foco o mínimos de objeto/fechas | Mínimo automático de tarjeta grid; región sin tabIndex | Región desplazable con nombre, scope y clases de la variante compartida |
| UsuariosRolesPage — /admin/usuarios / normal | Nombre/correo compiten con columnas de tipo y estado; correo puede fragmentarse en mínimo genérico | Mismo mínimo para persona, correo y tipo | Variante densa con nombre/correo amplios y acciones propias |
| BitacoraPage — /admin/bitacora / wide | HT-18 ya implementa mínimos, wrap y región enfocable | Estilos de HT-18 ya acotados por columna | Sin cambios en tabla ni CSS: solución adecuada; ejecutar regresiones |
| ReporteConveniosActivosPage — /reportes/convenios-activos / wide | Distribución fija propia de nueve columnas con región accesible | Tabla fija y región accesible ya implementadas | Sin cambios: preservar distribución de reporte |
| RenovacionesPage — /renovaciones / wide | Tabla propia de 1120px, acciones 220px, resaltado y foco programático | Mínimo y estilos propios de acciones y resaltado | Sin cambios: preserve estados, acciones y título con texto completo del objeto |
| ReporteEstadisticasConveniosPage — /reportes/estadisticas-convenios / wide | Dos columnas con tabla fija y ancho de conteos definido | Tabla fija de solo dos columnas | Sin cambios: no es tabla densa |
| ActividadesUtilizacionConvenio — detalle de convenio / normal | Cinco columnas, tres de texto largo con mínimos genéricos y sin foco de región | Prosa con mínimo genérico; región sin tabIndex | Variante densa y región etiquetada; no tocar formulario |
| SoportesConvenio — detalle de convenio / normal | Archivo, responsable y acciones compiten con tamaño/fecha; región sin foco | Archivo/responsable/acciones sin espacio propio | Variante densa y región etiquetada; acciones de documentos intactas |
| VersionesSolicitud — historiales propios/recibidos y convenio | Comparación de prosa Antes/Después con mínimos genéricos y región sin foco | Mínimo genérico para dos columnas de prosa | Variante densa con columnas de prosa y región etiquetada; comparación intacta |
| DirectorioConveniosPage — /directorio / público | Ya tiene región enfocada; rediseño excluido | Fuera del alcance de rediseño; región ya accesible | Sin cambios |
| AccionVolver / retornoVolver / HT-12 | Componente y CSS ya adecuados tras Lote 1 | Contrato seguro y apariencia compartida existentes | Sin cambios de código ni CSS; ejecutar regresiones de retorno seguro |
| AliadoDetallePage, SolicitudPage, SolicitudRecibidaPage, SolicitudHistorialPage, RevisionContrapartePage, NotFoundPage, RequierePermiso, BitacoraPage | Retornos fijos con enlaces planos o apariencia primaria/outline distintos | Clases planas, btn-primary o btn-outline en retornos fijos | Añadir solo clases btn/accion-volver existentes a los retornos reales, preservando to/state/texto/handlers y ubicación |
| Registro / recuperación / restablecimiento / verificación de correo | Enlaces dentro de flujos de autenticación | Contexto y finalidad propios de autenticación | Sin cambios: navegación de autenticación, no retorno operativo de bandejas |
| OnboardingSolicitantes | Retorno del tutorial con origen validado y handler propio | Contrato de origen del tutorial distinto de HT-12 | Reutilizar solo clase de apariencia; conservar contrato y handler |
| Continuar elaboración, Cancelar, Volver a radicar, tabs y consultas | Acciones operativas, no retornos equivalentes | Acciones de negocio/consulta, no retornos reales | Sin cambios |

No se altera globalmente `.table`, `.page`, `.card` ni `.btn`. La nueva variante se aplica explícitamente solo a los casos anteriores; DataTable ya ofrece clases de contenedor, tabla y columna suficientes. Los resultados de navegador y pruebas posteriores a implementación se registran a continuación.

## Implementación

Se reutiliza `handle: { layout: 'wide' }` únicamente en Revisiones jurídicas. A 1440px su contenedor pasa de 1130px a 1390px útiles medidos en Chrome, conservando el mismo permiso y las diez columnas. Se priorizan objetos y responsables frente a rondas/versiones; las fechas conservan su lectura íntegra y las acciones tienen mínimo propio. La tabla puede requerir scroll también en escritorio: se preserva la legibilidad de todos los datos.

DataTable no necesitó cambios: `containerClassName`, `tableClassName` y `className` por columna resuelven el problema. La variante optativa `.tabla-densa` usa mínimos en rem por contenido: referencias y fechas 11rem, texto/estado 12rem, personas 17rem, prosa 20rem, números 5.5rem y acciones 9rem. Estos mínimos se comprobaron con objetos multilínea, nombres extensos y correos largos; no se asigna el mismo ancho a cada columna.

El contenedor existente mantiene overflow-x auto, máximo 100% y min-width 0. `.tabla-seccion` permite que las tarjetas grid se contraigan, corrigiendo la expansión de la página del aliado. Las regiones de la variante tienen foco oscuro visible. Se conservan los paddings y separadores de filas compartidos. No se ocultan columnas ni se reemplazan por tarjetas. Las clases se aplican también a celdas nativas con encabezados scope=col, conservando scope=row en las comparaciones.

La tabla de contraparte migra a DataTable manteniendo consulta, filas, referencias, valores, fechas y destino Revisar. Su encabezado de acción ahora tiene nombre. Consulta muestra el objeto completo, conservando saltos de línea; se retiran el line-clamp `.convenio-objeto` y la clase `.table-cell-wide`, ya sin consumidores. No cambian las búsquedas ni la paginación.

Los retornos fijos solo reciben `btn accion-volver`; no se convierten a AccionVolver ni adoptan destinos desde location.state. Se preservan literalmente to, state, textos, handlers y posición. AccionVolver.tsx, retornoVolver.ts y el CSS del Lote 1 permanecen intactos. Los enlaces de cancelar, consulta, radicar y navegación de autenticación conservan su presentación.

## Evidencia antes/después

Capturas de la aplicación real en Chrome **157.0.8103.52**, con HTTP interceptado y datos sintéticos. El antes corresponde a develop 5bd399b, capturado antes de modificar el frontend. No se accedió a staging, producción ni datos personales.

| Comparación | Antes | Después |
|---|---|---|
| Jurídicas escritorio 1440×900 | [Captura](evidencia/lote2/antes-juridicas-1440.png) | [Captura](evidencia/lote2/despues-juridicas-1440.png) |
| Jurídicas móvil 390×844 | [Captura](evidencia/lote2/antes-juridicas-390.png) | [Captura](evidencia/lote2/despues-juridicas-390.png) |
| Tabla de contraparte escritorio | [Captura](evidencia/lote2/antes-contraparte-1440.png) | [Captura](evidencia/lote2/despues-contraparte-1440.png) |
| Retorno al aliado y tabla asociada en móvil | [Captura](evidencia/lote2/antes-aliado-390.png) | [Captura](evidencia/lote2/despues-aliado-390.png) |

También se capturó el extremo derecho de Jurídicas con [acciones visibles en móvil](evidencia/lote2/despues-juridicas-390-acciones.png) y [escritorio](evidencia/lote2/despues-juridicas-1440-acciones.png).

El antes revela overflow de página en contraparte (520px de documento) y aliado (641px de documento) a 390/360/320px. Después no ocurre en las rutas probadas. Jurídicas conserva diez columnas y muestra objeto/responsable sin la fragmentación excesiva anterior. Las capturas se inspeccionaron visualmente; las mediciones se conservan en [antes-medidas.json](evidencia/lote2/antes-medidas.json) y [despues-medidas.json](evidencia/lote2/despues-medidas.json).

## Validación

| Comprobación | Resultado real |
|---|---|
| npm run typecheck | Aprobado |
| npm run lint | Aprobado |
| Suite dirigida inicial (jurídicas, contraparte, responsive, navegación, Volver y HT-18) | 70 pruebas aprobadas en 6 archivos |
| Suite dirigida ampliada de vistas, reportes, permisos de lectura y documentos | 189 pruebas aprobadas en 15 archivos |
| npm test -- --maxWorkers=2 | **1069 pruebas aprobadas en 58 archivos**, 83.33s |
| npm run build | Aprobado; aviso de bundle JS >500kB (1134.71kB) |
| git diff --check | Aprobado |
| Chrome con datos sintéticos | **60 combinaciones**: diez vistas por seis resoluciones; sin overflow de página, columnas finales accesibles, regiones enfocables y desplazamiento con ArrowRight cuando es necesario |
| Retorno jurídico en Chrome | Revisar → detalle → Volver conserva buscar=provisional, tipo y responsable=7 |
| Accesibilidad automatizada/inspección | Tablas semánticas y scope; regiones etiquetadas; pruebas de teclado para retornos fijos; regresiones HT-12 de retorno seguro y contraste intactas |
| Zoom real 200%/400%, lectores de pantalla, Firefox/Safari y roles reales de servidor | **Pendiente QA manual** |

Las seis resoluciones ejecutadas son **1440×900, 1280×800, 768×1024, 390×844, 360×740 y 320×740**. Las diez vistas son Jurídicas, Contraparte, Consulta, perfil del Aliado, Usuarios, Aliados, Solicitudes recibidas, Mis solicitudes, Detalle de convenio (soportes y actividades) y comparación del historial de solicitud. Se inspeccionaron las cuatro comparaciones visuales anteriores; las demás vistas cuentan con medición DOM y verificaciones de scroll/teclado, no con una aceptación visual exhaustiva.

Las nuevas pruebas comprueban integridad de las diez columnas jurídicas, seis columnas de contraparte, texto completo, versiones/rondas, región enfocable, CSS acotado y retorno fijo por teclado en 404/acceso denegado. Las suites anteriores cubren filtros URL, Revisar y retorno contextual, HT-18, documentos, paginación, permisos y estados vacíos. No se relajaron expectativas existentes.

La suite emite dos avisos conocidos de jsdom sobre navegación a otro documento durante exportaciones, sin fallos ni pruebas omitidas. El primer intento de ampliar el navegador a Detalle recibió un mock inválido de revisión pendiente; se corrigió el fixture a 404 para un convenio sin revisión, sin modificar código de negocio. La ejecución final de 60 combinaciones no registra errores de página.

### Reproducción y QA pendiente

El [script de navegador](evidencia/lote2/validar.cjs) usa Playwright instalado **fuera del repositorio**, sin añadir dependencias al frontend. Desde la raíz:

1. Instalar dependencias existentes con npm ci --prefix frontend y ejecutar npm run dev --prefix frontend -- --host 127.0.0.1.
2. Instalar Playwright en una carpeta temporal y definir ORI_PLAYWRIGHT_MODULE con su módulo; ORI_CHROME_PATH admite el ejecutable de Chrome disponible.
3. Definir ORI_QA_BASE_URL con el servidor local (en esta ejecución http://127.0.0.1:5174) y ejecutar node docs/evidencia/lote2/validar.cjs despues. El script intercepta /api con sus fixtures; no necesita backend.
4. Para reproducir el antes, usar el frontend de 5bd399b y el mismo script con argumento antes. ORI_QA_FILTER permite seleccionar nombres de vistas; la ejecución final se hizo sin filtro.

En staging, validar estas rutas con los roles legítimos: /revisiones-juridicas, /revisiones-contraparte, /convenios, /ori/solicitudes, /solicitudes, /aliados, /aliados/{id}, /admin/usuarios, /convenios/{id}, /solicitudes/{id}/historial. Abrir la comparación de versiones cuando corresponda. Comprobar zoom real al 200% y 400%, foco, scroll hasta Acciones y filtros/paginación. En /admin/bitacora, /renovaciones y ambos reportes, confirmar también las distribuciones originales. Los IDs deben obtenerse de los listados de QA; no se afirman pruebas de autorización con servidor a partir de los mocks.

## Control de alcance

Sin cambios en backend, base de datos, migraciones, contratos API, endpoints, permisos, lógica de filtros, búsquedas, ordenación, paginación, reglas de navegación ni flujos jurídicos, firmas, renovaciones o documentos oficiales. RequierePermiso solo cambia una clase visual. No se alteran DetalleCampos/CampoLectura, HT-12, HT-18 ni los estilos específicos de reportes/renovaciones. Sin nuevas dependencias en package.json/lockfile, branding, correos ni rediseño del directorio.

Entrega: una rama y un PR hacia develop; sin merge ni auto-merge, para revisión del líder técnico.
