# HT-15 — Reglas de versionamiento formal y reenvíos

## Objetivo y alcance

Registrar las decisiones del PO sobre la versión inicial del convenio y el reenvío a
revisión jurídica (CA-01), para que la numeración y los reenvíos se ajusten a ellas.
Incidencias: [QA #173](https://github.com/ORI-USB-CALI/ori-manager/issues/173) y
[QA #174](https://github.com/ORI-USB-CALI/ori-manager/issues/174). Relacionada con
[HT-13 — Borrador y versionamiento](ht-13-borrador-versionamiento.md) y HU-10.

Esta ficha registra reglas aprobadas. No acredita su implementación, aceptación QA,
merge ni despliegue.

## Decisiones

Comunicadas al equipo el 08/11/2026.

| Tema | Situación anterior | Decisión |
|---|---|---|
| Versión inicial (#173) | Todo convenio nacía con V1, vacía en el origen manual, y lo primero enviado a revisión quedaba como V2. | Al crear no hay versión formal. El contenido inicial queda como borrador y el primer envío a revisión genera V1. |
| Reenvío sin cambios (#174) | Tras una devolución siempre se exigía una versión nueva. | El Revisor ORI indica si cada observación obliga a corregir el documento. Si ninguna obliga y todas están atendidas, se reutiliza la versión. |

## Reglas de la versión inicial

| Regla | Aplicación |
|---|---|
| RN-01 | Un convenio nuevo se crea sin versión formal: `version_actual = 0` y sin registros en `version_convenio`. |
| RN-02 | El contenido inicial se guarda como borrador, según el origen: documento vacío en creación manual, plantilla precargada en solicitud y copia de la última versión formal del convenio origen en renovación. |
| RN-03 | El primer envío a revisión jurídica genera V1 con el contenido y los datos del borrador, sujeto a las validaciones de completitud vigentes. Un documento vacío no se puede enviar. |
| RN-04 | Guardar avances sigue sin crear versiones, también antes de que exista V1. |
| RN-05 | Mientras no exista versión formal, la interfaz y los documentos de trabajo lo indican sin mostrar un número de versión. |

## Reglas del reenvío

| Regla | Aplicación |
|---|---|
| RN-06 | Si el contenido o los datos cambiaron respecto a la última versión formal, el reenvío genera una versión nueva. |
| RN-07 | Si son idénticos, ninguna observación de la última devolución obliga a corregir y todas están atendidas, el reenvío asocia la versión existente a la nueva revisión sin duplicarla. |
| RN-08 | Si son idénticos y alguna observación obliga a corregir, el sistema impide el reenvío e informa que deben atenderse las observaciones obligatorias. |
| RN-09 | Las observaciones de contraparte y las registradas antes de esta regla cuentan como obligatorias. |
| RN-10 | Un cambio sustancial que cancela un proceso de firmas siempre exige una versión nueva. |
| RN-11 | Todo reenvío abre una ronda nueva con RJ1 y RJ2. Los avales de rondas anteriores no se reutilizan, aunque se reutilice la versión. |

## Compatibilidad histórica

- Las versiones existentes conservan sus números, contenidos y referencias. No se renumeran ni se eliminan.
- Un convenio que ya tiene V1 al desplegar el cambio, incluso si sigue en Elaboración, continúa con su numeración: su siguiente versión formal es la que corresponda después de la actual.
- Las reglas de la versión inicial no requieren migración de datos.
- Las reglas del reenvío agregan una migración de esquema: la columna `requiere_correccion` en `observacion_revision`. Las observaciones existentes quedan marcadas como obligatorias (RN-09).

## Pendiente de confirmar

- Observaciones de revisión final: las decisiones no las mencionan. Mientras no se defina otra cosa, se tratan como obligatorias, igual que las de contraparte.
- Valor por defecto de la marca: la casilla del Revisor ORI viene marcada como "obliga a corregir", y las observaciones enviadas al devolver sin marca también cuentan como obligatorias. Así un olvido del Revisor no permite reenviar sin corregir.
- `expected_revision` de `finalizar_elaboracion` sigue siendo opcional "por compatibilidad" (Tarea 6). Falta decidir con Jesús si se vuelve obligatorio para completar el control de concurrencia; si cambia, hay que ajustar las pruebas que envían sin body.

## Regresión

### Issues de QA que esta HT debía resolver

| Issue | Síntoma reportado | Regla que lo resuelve | Evidencia |
|---|---|---|---|
| [#173](https://github.com/ORI-USB-CALI/ori-manager/issues/173) | El documento nacía como V1 vacía; la primera elaboración real enviada a revisión quedaba como V2. | RN-01/RN-02/RN-03: no hay versión formal al crear; el contenido inicial es borrador; el primer envío genera V1 con contenido real. | `test_ht15_numeracion_versiones.py` (`test_convenio_manual_nace_sin_version_y_con_documento_vacio_como_borrador`, `test_el_primer_envio_del_convenio_manual_genera_la_v1_con_lo_elaborado`, para los 3 orígenes). |
| [#174](https://github.com/ORI-USB-CALI/ori-manager/issues/174) | No se podía reenviar a revisión un convenio sin cambios reutilizando la versión existente; siempre exigía una versión nueva. | RN-07/RN-08: si el contenido y los datos no cambiaron y ninguna observación obliga a corregir, el reenvío reutiliza la versión. | `test_ht15_reenvios.py` (`test_reenvio_sin_cambios_reutiliza_la_version_si_ninguna_observacion_obliga`) y `test_ht15_revisiones_juridicas.py` (reutilización parametrizada por origen). |
| [#144](https://github.com/ORI-USB-CALI/ori-manager/issues/144) | Cada "Guardar avance" incrementaba la versión, generando varias versiones dentro de un mismo ciclo de elaboración. | RN-04/RN-06: guardar avances nunca crea versiones (antes y después de que exista V1); solo el envío a revisión versiona, y solo si hay cambios reales. | `test_ht13_guardar_avance.py` (ya existente) + `test_ht15_atomicidad_concurrencia.py` (confirma también con convenios nuevos en revisión 1). |

Los tres issues quedan resueltos por las reglas ya implementadas y cubiertos por pruebas automatizadas. No se modificó manualmente nada en GitHub (cerrarlos es decisión de QA/PO, no de esta rama).

### Cobertura automatizada (tareas 5 y 6)

- **Tarea 5** — `test_ht15_revisiones_juridicas.py`: integridad de RJ1/RJ2 (CA-05) parametrizada por los tres orígenes (manual, solicitud, renovación): reutilizar la versión abre una ronda nueva sin heredar avales (RN-11), y un aval de RJ1 no sirve para una versión distinta.
- **Tarea 6** — `test_ht15_atomicidad_concurrencia.py`: tres fallos simulados en `finalizar_elaboracion` (CA-06: al crear la versión, al crear la revisión, al cambiar la etapa) sin dejar nada a medias; concurrencia real con hilos (dos envíos simultáneos, dos guardados simultáneos con `expected_revision=1`); histórico (V1 vacía + V2 conservan número/contenido tras un ciclo nuevo).
- Suite completa al cierre de las tareas 5-7: backend **2859 passed**, frontend **859 passed** (sin regresiones sobre los `2847`/`854` reportados al subir la tarea 4).

### Pendiente de QA (no ejecutable desde esta rama)

- **Casos de QA solicitados y aún no entregados**: HT13-TC04, HT13-TC05, HT13-TC10 y HU10-TC13. No están en el repositorio; hay que pedírselos a QA y ejecutarlos cuando los entregue, registrando el resultado en esta sección.
- **Prueba manual en navegador** de los 3 orígenes (crear sin versión → guardar → primer envío V1 → devolución y corrección V2 → reenvío sin cambios con observaciones que no obligan [reutiliza] y con observaciones que sí obligan [bloquea]): el flujo está cubierto por las pruebas automatizadas de extremo a extremo citadas arriba, pero falta la verificación manual en un navegador real, que requiere a una persona con la rama desplegada.
