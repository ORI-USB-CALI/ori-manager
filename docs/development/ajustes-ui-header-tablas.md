# Ajustes UI/UX — Navegación y tablas

## Objetivo

Mejorar la navegación global, la jerarquía visual de Inicio
y la legibilidad de las tablas en ORI Manager.

## Cambios implementados

- Inicio: Accesos rápidos aparece antes de Próximos vencimientos.
- Header: marca compacta ORI Manager y navegación centrada.
- Menús desplegables para Solicitudes, Convenios y Administración.
- Crear convenio manual se encuentra dentro de Convenios.
- Selección de ruta activa sin resaltar opciones incorrectas.
- Navegación filtrada mediante los permisos existentes.
- Layout de ancho ampliado para las vistas de datos.
- Tablas con mejor aprovechamiento del espacio horizontal.
- Scroll horizontal contenido y accesible cuando es necesario.
- Estilo visual consistente en tablas y reportes.

## Compatibilidad

- Se conservan rutas, permisos y contratos API.
- No existen modificaciones de backend ni migraciones.
- Se conserva la navegación responsive y por teclado.
- Se mantienen notificaciones, información de sesión y logout.

## Validaciones

- 308 pruebas frontend aprobadas.
- TypeScript, ESLint y build aprobados.
- Revisión local de Chromium en múltiples resoluciones.
- Validación visual local aprobada por el líder técnico.
- Pendiente: verificación final con datos reales de Staging.

## Pendientes para R1

- Incorporar el logo institucional oficial en el header.

## Reversión

Revertir el commit o PR de estos ajustes si se detectan
regresiones visuales o funcionales en Staging.
