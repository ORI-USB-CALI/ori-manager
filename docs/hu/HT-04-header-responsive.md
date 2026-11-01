# HT-04 — Header global responsive

## Objetivo y alcance

Adaptar la navegación autenticada del sistema sin desbordamiento horizontal,
sin pérdida de enlaces autorizados por rol y sin ocultar información de sesión.
Los permisos, rutas, notificaciones y cierre de sesión existentes se conservan.
No modifica backend ni base de datos.

## Comportamiento

- En escritorio, los enlaces pueden distribuirse en varias líneas cuando no
  caben en una fila; cada enlace tiene un ancho máximo y permite ajustar texto.
- A 820 px o menos, la navegación se presenta mediante botón de menú, con
  `aria-expanded`, `aria-controls`, cierre por Escape, clic fuera y selección
  de enlace, incluida la ruta actual. El botón conserva foco visible.
- El encabezado usa varias filas en tablet/móvil y conserva siempre el correo,
  rol, campana de notificaciones y acción de cerrar sesión. Correos largos
  se ajustan sin expandir el ancho de la página.
- Los enlaces del menú se forman exclusivamente a partir de `puede(...)`
  en `AppLayout`; la adaptación visual no cambia autorizaciones.

## CA cubiertos y validación

- **CA-01:** comprobar ausencia de scroll horizontal provocado por el header.
- **CA-02:** comprobar todos los enlaces autorizados, apertura/cierre, teclado,
  foco y ruta activa.
- **CA-03:** comprobar correo, rol, notificaciones y cerrar sesión visibles,
  sin recorte en vistas compactas.

Pruebas automatizadas: `npm test -- src/components/HeaderNav.test.tsx`
y suite completa con `npm test` (desde `frontend`).
Estas pruebas jsdom cubren interacciones de navegación, pero **no miden el
layout real** ni ejecutan sesiones de cada rol dentro de un navegador.

## Matriz QA visual obligatoria antes de cerrar HT-04

Validar en navegador real, con sesión de Administrador ORI, Gestor ORI,
Revisor ORI, Solicitante Interno y Solicitante Externo, usando anchos
320, 375, 640, 768, 820, 821, 1024, 1280, 1440 y 1920 px.

1. Reducir y ampliar el viewport. Sin desbordamiento horizontal atribuible al
   header: `document.querySelector('.navbar').scrollWidth <=
   document.querySelector('.navbar').clientWidth`. Comprobar además
   `document.documentElement.scrollWidth <= document.documentElement.clientWidth`
   para descartar desbordamientos del documento completo.
2. Verificar todos los enlaces del rol en la navegación y que cada ruta
   navega correctamente sin perder su control de acceso.
3. En móvil, confirmar correo y rol legibles, campana accesible, menú
   operable por teclado y cierre de sesión funcional.
4. Comprobar que un correo largo y nombres de rol extensos se ajustan sin
   cortar el contenido. Abrir/cerrar la bandeja de notificaciones.

No declarar cierre de QA solo por CI: se requiere evidencia visual y
funcional por rol y viewport en Staging.

## Contingencia

Revertir el commit específico de HT-04 si la navegación presenta regresiones.
No hay migraciones ni cambios de datos para revertir.
