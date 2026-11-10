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

## Pendiente de confirmar

- Observaciones de revisión final: las decisiones no las mencionan. Mientras no se defina otra cosa, se tratan como obligatorias, igual que las de contraparte.
