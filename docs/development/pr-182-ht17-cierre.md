# PR #182 - Cierre tecnico HT-17

Rama: feature/ht-17-duracion-vigencia. Base integrada con merge normal: origin/develop efcf69d.
Reglas y ejemplos: [ficha HT-17](../hu/ht-17-duracion-vigencia.md).

## Evidencia local

- test_ht17_cierre.py, test_hu12_elaboracion.py y test_hu15_revision_final_firmas.py: 164 aprobadas.
- HT-14 (formatos, integracion, unicode, separadores, modelo, busqueda): 621 aprobadas.
- HT-17, HT-08, HT-10, acciones HU-31, migraciones HT-14 y alertas HU-30: pasaron en el bloque de 219 casos previos a un fallo de conteos globales en ciclo de vida causado por filas existentes en la base local.
- Ciclo de vida y reglas HU-31 se ejecutaron en una base local desechable independiente, creada para esta validacion y migrada desde cero: 77 aprobadas. No se eliminaron datos de la base existente.
- Frontend: vigencia, creacion, elaboracion, revision final y renovacion: 74 aprobadas.
- TypeScript y ESLint: aprobados. Ruff completo: aprobado sobre copia temporal de fuentes con permisos normales 0644 (el volumen Windows presenta archivos Python como ejecutables; no se deshabilito la regla EXE002).
- git diff --check: aprobado antes de publicar.

Una ejecucion anterior fue interrumpida al detenerse los contenedores locales; no se contabiliza como aprobada. Solo se repitieron los bloques pendientes o afectados. La suite completa corresponde a GitHub Actions.

## Revision y operacion

Migracion aditiva c17a20261115: vigencia_ht17=false para filas existentes, sin reescritura de fechas. Nuevos registros/cambios activan la marca transaccionalmente. No se modifica fecha_firma, logica de alertas, umbrales ni workflows.

La aceptacion institucional PO/ORI debe quedar trazada en issue #175; estas son decisiones del lider tecnico para el cierre tecnico, sin afirmar aprobacion del PO. Pendientes Actions y revision del lider tecnico. Sin merge a develop ni despliegue manual.


## Seguimiento: regresiones backend del CI 43678850410

El CI de 291b50c registro 2832 aprobadas, 101 fallidas y 137 errores.
Causas comunes y correccion limitada a pruebas:

- Preparaciones nuevas de HT-16, revision publica, exportacion, HU-20 y E2E avanzaban sin vigencia o utilizaban fechas retroactivas. helpers_vigencia.py proporciona inicio del dominio, duracion valida y vencimiento calculado; los servicios conservan todas sus validaciones.
- crear_convenio y la fixture propia de HU-12 ya no marcan todos los convenios como historicos ni anulan la validacion de los nuevos. historico=True es una carga explicita de datos previos a la migracion. Los datasets antiguos de alertas, reportes, filtros, actividades y renovaciones declaran esa condicion. Los borradores nuevos siguen siendo parciales cuando corresponde.
- Los errores en la preparacion concurrente anterior al yield dejaban registros confirmados, produciendo conteos adicionales en HU-36. Corregir la vigencia permite ejecutar el escenario y su limpieza; no se cambiaron los conteos esperados ni las aserciones de integridad.
- Las pruebas nuevas de consulta usan una referencia temporal controlada o el intervalo real del convenio, conservando las comprobaciones de acceso y paginacion. Se agrega una regresion para impedir volver a tratar convenios nuevos como historicos en la factory compartida.

Validacion focal: 494 pruebas de los 12 archivos fallidos aprobadas; 389 del bloque de fixtures y compatibilidad temporal aprobadas. Ruff completo y git diff --check aprobados. Sin cambios en codigo funcional, migraciones, frontend ni workflows. Sin skip, xfail o desactivaciones nuevas.

Validacion completa local unica, en base nueva migrada desde cero: 3036 aprobadas y 35 fallidas, sin errores de preparacion. Los 35 fallos se concentraron exclusivamente en tres callers historicos adicionales de HU-30 API y consultas/reglas HU-31 que aun no declaraban historico=True. Tras corregir esas fixtures se reejecutaron sus tres archivos: 56 aprobadas. Quedan verificados los 3071 casos unicos (3070 anteriores y una regresion nueva de la factory); no se presenta este resultado como una segunda suite completa verde. La ejecucion completa final corresponde al nuevo CI tras publicar. No se repitio frontend local ni una segunda suite backend completa.
