# HT-11 — Legibilidad del reporte web de convenios activos

**Historia relacionada:** HU-34
**Issue QA:** #142
**PR:** #163
**Complementaria:** HT-07, corrección del reporte PDF.

## 1. Objetivo

Mejorar la legibilidad y distribución de las columnas del reporte
web de convenios activos sin modificar los datos, permisos,
exportaciones ni otros módulos.

QA identificó dos problemas:

- Bajo contraste del objeto del convenio.
- Crecimiento excesivo de la columna Convenio con textos largos.

La corrección global del fondo rojo incorrecto en encabezados
de fila ya fue integrada en develop por el líder técnico.

HT-11 complementa esa solución mediante estilos específicos
para controlar las proporciones del reporte.

## 2. Implementación

La tabla utiliza las clases:

- reporte-activos-container
- reporte-activos-tabla

Se implementa:

- table-layout: fixed.
- Ancho mínimo de tabla de 1250 px.
- Distribución proporcional de nueve columnas.
- Primera columna limitada al 16 %.
- Ajuste de texto mediante overflow-wrap: anywhere.
- Scroll horizontal contenido cuando es necesario.
- Ajuste de etiquetas de estado y botones dentro de sus celdas.

El objeto completo permanece en el DOM y se presenta con
ajuste de línea; no se modifica ni se trunca su valor almacenado.

## 3. Criterios de aceptación

### CA-01 — Contraste legible

Se conserva la corrección previa de develop para el fondo
de los encabezados de fila. HT-11 no redefine globalmente
los colores.

QA verificará el contraste final del código y del objeto.

### CA-02 — Limitar ancho

La columna Convenio mantiene una proporción del 16 %
mediante una tabla de distribución fija.

Los textos largos no deben modificar las proporciones
establecidas de las demás columnas.

### CA-03 — Textos extensos

El objeto conserva su contenido completo y permite
ajuste de línea, incluso para palabras extensas.

El atributo title existente permanece como ayuda adicional,
sin ser el único mecanismo de acceso al contenido.

### CA-04 — Funcionalidad existente

Se conservan:

- Las nueve columnas y su orden.
- Enlaces al detalle del convenio.
- Descarga PDF.
- Descarga Excel.
- Actualización del reporte.
- Permiso convenios.ver_reportes.

### CA-05 — Compatibilidad responsive

El contenedor permite desplazamiento horizontal.

El ancho mínimo de 1250 px implica que algunas ventanas
necesitarán scroll interno, comportamiento que QA validará.

### CA-06 — Regresión visual

Los nuevos selectores están limitados al reporte de
convenios activos para evitar efectos sobre otras tablas.

La prueba añadida verifica clases, nueve encabezados,
textos extensos y enlace al detalle.

La revisión visual real queda asignada a QA.

## 4. Contratos y permisos

Página:
- /reportes/convenios-activos

Endpoints conservados:
- GET /api/convenios/reportes/activos
- GET /api/convenios/reportes/activos/pdf
- GET /api/convenios/reportes/activos/excel

Permiso:
- convenios.ver_reportes

No hay modificaciones de backend, base de datos, migraciones,
contratos API ni generadores de exportación.

## 5. Pruebas automatizadas

Archivo:
frontend/src/pages/ReporteConveniosActivosPage.test.tsx

La prueba específica de HT-11 comprueba la estructura
de la tabla, presencia de textos extensos, nueve columnas
y navegación al detalle.

Las pruebas DOM no certifican contraste, proporciones
reales ni ausencia de desbordamiento visual.

Los resultados de CI del PR constituyen la evidencia
de regresión automatizada.

## 6. Validación funcional — QA

QA realizará las pruebas en Render Staging con:

- Objetos cortos.
- Objetos largos.
- Objetos vacíos.
- Palabras extensas sin espacios.
- Resoluciones de 320, 768, 1280 y 1920 px.
- Contraste normal y durante hover.
- Scroll horizontal y acceso a todas las acciones.
- Descargas PDF y Excel.
- Verificación de otras tablas que comparten estilos.

Registrar los resultados y evidencias en el issue #142.

El merge del PR no equivale a aceptación de QA ni
autoriza cerrar automáticamente la incidencia.

## 7. Compatibilidad y reversión

HT-11 complementa los ajustes UI/UX anteriores y HT-07.

Ante una regresión atribuible a HT-11, revertir su cambio
funcional, conservando las correcciones previamente
integradas en develop.

No se requiere restauración de base de datos.
