# Navegación contextual desde Solicitudes

Base: `origin/develop` (`6d2184d`). Rama: `fix/qa-navegacion-contextual-convenios`.

La tabla y el detalle comparten la elección de ruta por `convenio_etapa.codigo`
y permisos de sesión. Elaboración conserva su editor para quien puede editar;
Jurídica, Contraparte, Revisión final y Firmas abren el detalle existente. Quien
solo puede consultar recibe enlaces de consulta; sin `convenios.ver` no se ofrece
acceso al convenio. La creación desde la tabla abre la solicitud para iniciar allí.
No se duplican acciones de revisión, envío ni firmas.

La advertencia posterior a finalizar provenía de comparar la edición local con
la versión formal recién creada y la revisión de borrador reiniciada a cero.
Solo después del POST exitoso se descarta esa edición ya enviada, se cancela una
lectura anterior y se invalidan elaboración, versiones, detalle, tablero y bandeja.
Un 409 al guardar o finalizar conserva documento y metadatos y muestra el conflicto.
Durante la confirmación se impide editar; durante el envío tampoco se puede cerrar
el diálogo. Las etapas posteriores muestran consulta y acceso al trámite.

Los estilos se limitan a las tarjetas de solicitud, Elaboración e Información base
del detalle: etiquetas, valores, campos y adaptación a pantallas pequeñas.

## Verificación local

- Antes de cambiar lógica: 81 pruebas de HT-13/HT-15, HU-13 y HT-05 aprobadas;
  se agregó y pasó el caso explícito de contenido idéntico en revisión. Quedan
  comprobados avance sin versión, primer envío V1, cambios reales de documento o
  datos, reenvíos permitidos, aval de versión exacta e inmutabilidad histórica.
- Regresión backend: 122 aprobadas en esos archivos más integración de solicitud
  y revisión HU-07, contra PostgreSQL local `ori_contractual_test`.
- Frontend: suite completa 1038 aprobadas; tras ampliar los casos de las etapas
  reales de firmas, 109 dirigidas aprobadas en las cinco suites de navegación,
  solicitud, detalle, Elaboración y confirmación. Cubre permisos, solo lectura,
  finalización exitosa, conflictos reales y retorno a la vista de origen.
- TypeScript, ESLint, Ruff, build y `git diff --check` aprobados. El build mantiene
  el aviso de tamaño del bundle; backend informa dos deprecaciones de dependencias.

No se modifica el servicio de versiones, snapshots ni las reglas de seguridad.
No se agregan/aplican migraciones ni se accede a datos de staging o producción.

## Escenarios manuales pendientes en staging tras despliegue

1. Con Gestor/Admin, abrir tabla y detalle de solicitudes en cada etapa. Verificar
   editor solo en Elaboración, consulta jurídica y continuación en Contraparte,
   Revisión final y Firmas. Sin convenio, iniciar desde el detalle de solicitud.
2. Abrir directamente un editor de una etapa posterior: título de consulta,
   campos deshabilitados, sin invitación a editar y enlace al detalle operativo.
3. Editar y finalizar: éxito, documento enviado visible en solo lectura y sin
   advertencia de conflicto. Volver a Solicitudes y comprobar etapa y enlace nuevos.
4. Con dos sesiones, guardar desde B y guardar/finalizar desde A: 409 real, texto y
   metadatos de A conservados; cargar el borrador reciente solo bajo acción expresa.
5. Verificar ausencia de acciones operativas sin sus permisos; comprobar tarjetas
   con texto multilínea y correo largo en escritorio y móvil.

Estos escenarios son una guía de QA; no acreditan ejecución ni aceptación en staging.
