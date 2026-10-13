# HU-21 — Historial de observaciones Juridicas

**Sprint:** Sprint 3 - Documentación · **Estado HU en el backlog:** Terminado · **Épica:** EP-04-Trazabilidad y seguimiento

## Necesidad de negocio (fuente: backlog exportado)

Como usuario de la ORI, quiero consultar las observaciones dejadas por los revisores jurídicos para conocer el trasfondo de los ajustes realizados.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Consultar el historial desde el convenio
- CA-02 — Identificar quién realizó la observación
- CA-03 — Mostrar el contenido de la observación
- CA-04 — Identificar la revisión jurídica correspondiente
- CA-05 — Conservar los diferentes ciclos de revisión
- CA-06 — Mostrar la atención de la observación

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/tests/test_bloque_b_trazabilidad.py`
- `frontend/src/pages/ConvenioHistorialPage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-21 — Historial de observaciones Juridicas 3d369ca9cb4080bea737fc60f1a4852c.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
