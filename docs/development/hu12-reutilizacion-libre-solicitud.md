# HU-12: reutilización libre de solicitud

Base: `origin/develop` (`6d2184d`). Rama: `fix/hu12-reutilizacion-libre-solicitud`.
Es independiente del PR de navegación contextual; ambos apuntan a `develop`.

La API de Elaboración ya incluye los cuatro campos narrativos de la solicitud
original. La nueva acción prepara con ellos un documento local editable, usando
solo secciones con texto. No requiere un endpoint, plantilla ni guardado nuevo.
El Gestor puede retirar títulos, suprimir secciones o sustituir todo el documento.
Antes de reemplazar texto escrito se solicita confirmación; cancelar no cambia
documento ni metadatos. El contenido anterior queda consultable hasta salir.

La acción no asigna propuestas de tipo, vigencia o duración al formulario. Sus
valores definitivos se gestionan en Datos clave. No cambia la inicialización
existente de convenios y queda excluida de manuales, renovaciones, consulta y
sesiones sin permiso de edición. Se deshabilita durante guardado o conflicto.
La reutilización no escribe en la solicitud: solo el guardado vigente persiste
los cambios locales con `expected_revision` y genera versiones según HT-13/HT-15.

## Verificación local

Antes de cambiar lógica se probaron las reglas HT-13/HT-15, HU-13 y HT-05:
avance sin versión, primer envío V1, guardado idéntico en revisión, nueva versión
ante cambios reales, reenvíos permitidos y rechazados, aval de versión exacta e
inmutabilidad histórica. No se modifica ninguna implementación de versionamiento.

`backend/tests/fixtures/hu12_base_solicitud.json` se comparte entre la prueba del
generador frontend y las pruebas API/exportación. Así se comprueba el documento
real generado: sin placeholders, sin estructura de precarga OBS-S3-003, admitido
por el validador documental y exportable como PDF/Excel oficial con la fuente
aprobada del fixture local. Exportar no modifica contenido ni snapshot.

Las pruebas API conservan todas las columnas de la solicitud, los datos
contractuales definitivos y el enlace de revisión a V1. Prueban guardar sin crear
versión, el 409 con revisión obsoleta y finalizar la base, su versión sin títulos o
un documento completamente sustituido. Las regresiones existentes conservan la
protección de los antecedentes históricos, avales, firmas y exportación oficial.

Las pruebas frontend cubren los cuatro campos, texto multilínea y especial,
secciones ausentes, confirmación/cancelación, sustitución libre, guardado actual,
conflicto conservando texto y metadatos, permisos, etapas, manuales y renovaciones.

Resultados: 558 pruebas backend aprobadas (HU-12, HU-10, HU-15, HT-13, HT-15,
HU-24, OBS-S3-003, integración de solicitud, exportación API y acciones HU-31),
sobre PostgreSQL local `ori_contractual_test`. Suite frontend completa: 1029
aprobadas; tras añadir el caso de retirada del aviso de precarga, 71 dirigidas
aprobadas (Elaboración, generador, confirmación y vigencia). TypeScript, ESLint,
Ruff, build y `git diff --check` aprobados. Se mantienen los avisos de tamaño del
bundle y deprecaciones de dependencias (20 en backend).

No se agregan/aplican migraciones ni se accede a datos de staging/producción.

## Escenarios manuales pendientes de staging tras despliegue

1. Iniciar convenio desde solicitud aprobada. Consultar el original íntegro y usar
   su información como base: comprobar objeto, justificación, actividades y metas.
   Tipo, duración y fechas del convenio deben conservar sus valores previos.
2. Cambiar títulos, quitar una sección, reorganizar y sustituir texto. Guardar y
   reabrir: se recupera el documento libre sin nueva versión. Volver a la solicitud
   y comprobar que sus datos originales permanecen intactos.
3. Con contenido escrito y cambios sin guardar, pulsar la acción y cancelar:
   nada se reemplaza. Repetir y confirmar: se reemplaza el documento local y se
   puede consultar/copiar el anterior. No debe aparecer la plantilla de 23 bloques.
4. Guardar desde otra sesión y guardar/finalizar desde la primera: debe responder
   409 conservando su texto y metadatos; cargar la revisión reciente debe ser
   explícito. Tras finalizar normalmente debe existir V1 vinculada a Jurídica.
5. Completar revisiones y firmas habituales; comparar PDF/Excel oficial con la
   versión aprobada. Una estructura histórica ambigua sigue protegida. Borrar todo
   el documento sigue impidiendo finalizar, sin exigir encabezados específicos.
6. Abrir manual, renovación y convenio en revisión; comprobar ausencia de la acción.
   Repetir con una sesión sin permiso de edición. Comprobar solicitud con narrativas
   opcionales vacías: no deben insertarse títulos vacíos ni textos pendientes.

Esta guía no acredita ejecución ni aceptación manual en staging.
