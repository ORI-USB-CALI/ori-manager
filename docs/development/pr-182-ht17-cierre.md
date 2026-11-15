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
