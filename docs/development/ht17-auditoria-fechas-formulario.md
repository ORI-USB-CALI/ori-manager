# HT-17: auditoría focalizada de fechas del formulario

## Diagnóstico

Base revisada: `origin/develop`, commit `0a90eef`. No se reprodujo la pérdida de
fecha en las comprobaciones automatizadas. No se identificó una causa raíz
demostrada para la incidencia de staging; este PR incorpora pruebas y diagnóstico,
sin cambios funcionales.

Se revisaron `ConvenioElaboracionPage.tsx`, `ConvenioNuevoPage.tsx`, `vigencia.ts`
y `backend/services/vigencia.py`. Los campos `date` están controlados por React
y actualizan el estado mediante `onChange`. En Elaboración, `cambiarVigencia`
recalcula el vencimiento al cambiar inicio o duración; guardado y finalización
serializan esos mismos metadatos. En creación, el vencimiento deriva del estado
de inicio y duración. No hay una lectura separada del texto visible al enviar.

Las pruebas nuevas despachan eventos DOM `input` y `change`, en ambos órdenes
(fecha/duración y duración/fecha), sin una segunda corrección de fecha. Comprueban
el valor visible, el cálculo derivado del estado React y el payload HTTP.
En Elaboración verifican el primer intento de finalizar, guardado y un montaje
nuevo desde la respuesta del servidor. El rechazo simulado al finalizar corresponde
a otro dato pendiente: permite comprobar que la fecha enviada no se pierde.

La prueba backend adicional verifica guardado, consulta después de expirar la
sesión ORM, finalización, devolución jurídica y nueva consulta de las fechas.
Las suites HT-08/HT-17 cubren mínimo de cuatro meses, inicio no retroactivo,
fin de mes, febrero bisiesto, cambio de año, rechazo de valores incoherentes y
compatibilidad de datos históricos. No se altera la fórmula ni las reglas vigentes.

## Límite de la reproducción

No había navegadores conectados al control de UI. El intento de abrir el navegador
integrado devolvió `Browser is not available: iab`. jsdom no implementa el selector
nativo: los eventos sintéticos no equivalen a seleccionar un día en ese calendario
ni a escribir segmentos de fecha mediante teclado en un navegador real.
Por ello, esas dos comprobaciones de UI siguen pendientes. No se afirma que el
defecto de staging esté descartado ni corregido. No se incorpora Playwright.

## Resultados automatizados

- Frontend: 81 pruebas aprobadas en `ConvenioNuevoPage.test.tsx`,
  `ConvenioElaboracionPage.test.tsx` y `vigencia.test.tsx`.
- Backend: 80 pruebas aprobadas en `test_ht08_validacion_vigencia.py`,
  `test_ht17_duracion_vigencia.py` y `test_ht17_cierre.py`, ejecutadas contra una
  base PostgreSQL local aislada. Dos avisos de deprecación de Starlette/AnyIO.
- `npm run typecheck`, `npm run lint`, `uv run ruff check .` y
  `git diff --check`: correctos.

Se modifican únicamente este informe, los dos archivos de pruebas de formularios
y `backend/tests/test_ht17_cierre.py`. No se modifica código de producción,
migraciones, dependencias ni datos históricos.

## Verificación manual pendiente en staging

Usar convenios de prueba nuevos y registrar navegador, versión, sistema, idioma y
fecha/hora. Mantener abierta la pestaña Network con preservación del registro.

1. En creación manual y en Elaboración, establecer duración de 4 meses y elegir
   el inicio mediante el calendario nativo. Sin tocar la fecha con el teclado,
   crear o finalizar inmediatamente. Verificar que el primer POST contiene el
   mismo `fecha_inicio` visible y el `fecha_vencimiento` calculado.
2. Repetir escribiendo los segmentos de la fecha con teclado y confirmar el año
   completo. Repetir ambos métodos introduciendo primero fecha y después duración.
3. Guardar avance y recargar completamente. Verificar mediante GET y formulario
   las mismas fechas y duración. Finalizar, devolver desde Jurídica y consultar
   Elaboración nuevamente: las fechas deben permanecer.
4. Probar hoy y ayer según America/Bogota, duración 3 y 4, 31 de enero,
   31 de octubre, febrero bisiesto y cambio de año, usando fechas futuras.
   Para el 29/02/2028 más 12 meses se espera 28/02/2029; para el
   31/10/2099 más 4 meses se espera 28/02/2100. No modificar datos históricos.
5. Si reaparece la incidencia, capturar el valor DOM `input.value`, los eventos
   `input`/`change`/`blur`, el estado del componente con React DevTools y el payload
   del primer intento. Comparar con el segundo intento y anotar si había guardado
   o refetch en curso. Evitar incluir datos personales o credenciales en evidencias.

El diagnóstico necesita esa evidencia del navegador afectado para atribuir una
causa a eventos del control nativo, edición incompleta u otra condición de carrera.
Son hipótesis de investigación, no causas confirmadas.
