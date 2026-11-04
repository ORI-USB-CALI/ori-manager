# HT-07 — Maquetación del PDF del reporte de convenios activos

**Relacionada con:** HU-34 · **QA:** [#137](https://github.com/ORI-USB-CALI/ori-manager/issues/137).

## Objetivo y causa

El PDF del reporte de convenios activos (HU-34) debe presentar sus columnas completas y legibles. QA #137 reportó encabezados sobrepuestos («Tipo de convenio» con «Unidad», «Fecha vencimiento» con «Actividades») y fechas partidas en varias líneas.

Los encabezados se dibujaban como texto plano, en una sola línea y sin ajuste, y nueve columnas compartían el ancho de una carta vertical (527pt). Cinco encabezados y las fechas no cabían en sus columnas. Además, un objeto de unos 3000 caracteres o más producía una fila más alta que la página, y el PDF no se generaba (HTTP 500).

## Comportamiento y criterios aprobados

- **CA-01:** los encabezados se ajustan dentro de su columna y ninguno invade la vecina. «Tipo de convenio» y «Fecha vencimiento» ocupan dos líneas.
- **CA-02:** el reporte usa una carta horizontal (707pt útiles, márgenes de 1.5cm). Cada columna tiene un ancho fijo, igual en todas las páginas.
- **CA-03:**
  - El código institucional (`USB-ORI-AAAA-NNNNN`), las fechas y el conteo de actividades caben en una línea.
  - Objeto, aliado, unidad y responsable se ajustan en varias líneas sin perder texto.
  - La letra de las celdas pasa de 7pt a 8pt.
- **CA-04:**
  - La tabla principal y las de actividades repiten su encabezado en cada página, y las tablas se cortan solo entre filas.
  - Un objeto más alto que el máximo de una fila (15cm) continúa en filas rotuladas «‹código› (continuación)», con el fondo de su convenio.
  - El título de cada convenio en «Actividades por convenio» no queda solo al pie de una página.
- **CA-05:** se conservan los datos de HU-34, el permiso `convenios.ver_reportes`, el endpoint y el nombre del archivo. El Excel no cambia.
- **CA-06:** ver «Pruebas y seguimiento».

## Contratos y operaciones

| Operación | Cambio |
| --- | --- |
| `GET /api/convenios/reportes/activos/pdf` | Misma respuesta (`application/pdf`, `convenios-activos.pdf`); solo cambia la maquetación del documento |
| `GET /api/convenios/reportes/activos/excel` | Sin cambios |
| `GET /api/convenios/reportes/activos` | Sin cambios |

El generador es `generar_pdf_convenios_activos`, en `backend/src/backend/services/reportes.py`.

## Seguridad y compatibilidad

- No cambian los permisos, los endpoints, el modelo de datos, las migraciones ni el frontend.
- Los textos se siguen escapando antes de pasarlos a ReportLab, así que el marcado (`<b>`, `&`) se muestra literal.
- **Limitaciones conocidas:**
  - La fuente estándar Helvetica no tiene glifos para emoji ni escrituras no latinas. No impiden generar el PDF, pero se ven como cuadros.
  - Un correo largo en «Registrado por» puede partirse en dos líneas.

## Pruebas y seguimiento

- **Pruebas nuevas:** `backend/tests/test_ht07_pdf_reporte_convenios_activos.py`, sin base de datos. Cubre:
  - encabezados dentro de su columna y área imprimible;
  - campos cortos en una línea;
  - 60 convenios y 80 actividades en varias páginas, con un solo encabezado por página;
  - un objeto de 3000 palabras que llega completo;
  - caracteres especiales, el reporte vacío y los encabezados del Excel.
- **Regresión:** `test_hu34_reporte_convenios_activos.py` y `test_hu35_actividades_utilizacion.py` pasan sin cambios.
- **Revisión visual** de PDFs generados durante el desarrollo: corto, mixto, de varias páginas, con objeto extenso y vacío.
- **Pendiente:** QA en Staging con datos reales. El issue [QA #137](https://github.com/ORI-USB-CALI/ori-manager/issues/137) se cierra solo tras el merge y la verificación. Abrir el PR no significa que HT-07 esté terminada.

## Reversión

Revertir el commit de HT-07 devuelve la plantilla vertical anterior. No hay cambios de base de datos ni de datos.
