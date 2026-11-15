# Directorio público de convenios — referencia técnica HU-09 (PR #181)

Objetivo: consultar convenios vigentes sin sesión desde `/directorio`, enlazado
desde `/login`. La referencia HU-09 corresponde a la rama y al
[PR #181](https://github.com/ORI-USB-CALI/ori-manager/pull/181); no acredita el
identificador oficial ni el cierre de la historia en el backlog.

## Trazabilidad pendiente para el líder técnico

El registro compartido indicado en la revisión usa HT-09, pero
[HT-09 ya identifica la bitácora integrada](ht-09-auditoria-ampliada.md).
Las búsquedas de directorio/HU-09 en Drive y directorio/HT-09 en Notion no
recuperaron una ficha vigente del directorio. La lista de refinamiento de
septiembre en Drive usa otra numeración histórica y no resuelve la colisión.
El líder técnico debe confirmar el ID oficial, sprint, estado y enlace a la
ficha vigente y corregir el registro compartido o la referencia del PR según
corresponda. No se renombra HT-09 ni se cambia el estado de ninguna historia.

## Contrato, permisos y vigencia

`GET /api/public/directorio-convenios` es anónimo, sin dependencia de sesión ni
redirección a login. Devuelve `{items, total}`. `limite` es un entero de 1 a 50
(20 por defecto) y `desplazamiento` un entero no negativo (0 por defecto).
Parámetros inválidos devuelven 422. Orden: vencimiento ascendente e ID como
desempate estable. El total aplica los mismos filtros antes de paginar; una
página posterior al último registro tiene items vacíos y conserva el total.

Conforme al DoR solicitado en la revisión, cada registro debe cumplir:

- Formalización según el predicado canónico de HU-27:
  `fecha_firma` definida y estado distinto de `EN_TRAMITE`/`CANCELADO`.
- Estado exactamente `VIGENTE`; `POR_VENCER` queda excluido, sin normalizarlo.
- Inicio y vencimiento definidos y `inicio <= hoy <= vencimiento`.
  Se conserva la fecha de Bogotá y ambos límites inclusivos de HT-10.
- Código persistido no nulo ni vacío y aliado relacionado con nombre no vacío
  (se ignoran espacios exteriores para comprobar vacíos).

Los mismos filtros se aplican a manuales ORI y derivados de solicitudes.
No se infiere identidad del nombre propuesto en la solicitud, no se asignan
códigos en un GET ni se regularizan datos históricos. HT-06 asigna el código
institucional durante la formalización en `services/firmas.py`; los registros
incompletos quedan fuera hasta su corrección por los procesos autorizados.
La consulta pública no altera reglas de creación, firmas ni HU-31.

## Confidencialidad: CA-06 requiere decisión funcional

La respuesta construye explícitamente esta lista blanca:
`codigo`, `aliado` (solo nombre), `tipo_convenio` (solo nombre), `objeto`,
`fecha_inicio`, `fecha_vencimiento`, `estado` (siempre `VIGENTE`). Código, aliado
e inicio son obligatorios en el contrato; tipo y objeto pueden ser nulos.
No se serializan modelos ORM, relaciones completas, IDs internos, documentos,
URLs de descarga, contenido jurídico, revisiones, observaciones, responsables,
contactos, identificaciones, correos, datos financieros ni metadatos
administrativos. La UI solo presenta esos siete campos.

La revisión de modelos y contratos de convenio/aliado no encontró un atributo
de confidencialidad, clasificación o autorización institucional de publicación.
`Aliado.activo` controla su uso operativo, no es autorización para publicar;
la formalización y vigencia tampoco prueban esa autorización. No se añade una
política de publicación por tipo, origen, rol o aliado activo.

**Decisión pendiente del líder técnico/ORI:** establecer si todo convenio que
cumple el DoR puede publicar estos campos o si CA-06 exige clasificación y
aprobación por convenio; definir responsable y tratamiento de datos existentes.
Si exige autorización explícita, falta implementar el mecanismo acordado antes
de aceptar CA-06. Además `objeto` y nombres son texto libre: la lista blanca no
garantiza que su contenido haya sido revisado para publicación. Se conserva el
alcance implementado, sin dar CA-06 ni la HU por aceptados. Este documento y el
reporte del PR elevan la decisión al equipo tech-leads solicitado como revisor.

## Alternos, errores y pruebas

La UI muestra carga, lista vacía y error genérico ante fallos de red/HTTP, sin
mostrar detalles internos ni redirigir ante 401/403. La paginación usa 20 filas,
total del servidor y botones Anterior/Siguiente. Un fallo inesperado del backend
produce 500 genérico; no se presenta como lista vacía. No se agregan manejadores
globales ni nuevas dependencias.

`backend/tests/test_hu09_directorio_publico.py` comprueba la aplicación FastAPI
real con acceso anónimo sin seguir redirecciones, lista blanca exacta, cada
estado excluido, no formalizado, límites inclusivos, futuro/vencido, fechas
nulas, códigos nulos/vacíos, aliado ausente/sin nombre, ambos orígenes, orden,
paginación, total, lista vacía, 422 y ausencia de detalles privados ante 500.

`frontend/src/pages/DirectorioConveniosPage.test.tsx` usa `router.routes` con
`RouterProvider`: acceso sin sesión y sin consulta de autenticación, sin
redirección, campos restringidos ignorados, vacío, paginación, 500, 401/403 y
fallo de red. Regresiones: HT-06 (identificación/formalización), HU-10 (manuales),
HU-27 (filtros), HT-10 (vigencia) y navegación del router; la suite completa
incluye HU-31 integrada desde develop, sin nuevas modificaciones a esa historia.

Resultados del cierre y CI: [reporte del PR #181](../development/pr-181-hu09-cierre.md).
Son validaciones técnicas, no UAT ni aceptación institucional.

## Integración y recuperación

Integración normal de `origin/develop` (`3dc3626`), sin conflictos ni reescritura
de historia. No hay migraciones, variables, dependencias o cambios de despliegue.
Ante una corrección posterior, conservar las exclusiones y la lista blanca.
Volver al comportamiento previo ampliaría los registros visibles; ante un
incidente de publicación debe retirarse la ruta pública en vez de relajar los
filtros. No se ejecuta el merge a develop desde este cierre.
