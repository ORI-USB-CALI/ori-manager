# HU-07 — Revisar y gestionar solicitud recibida

**Sprint:** Sprint 2 - Operatividad · **Estado HU en el backlog:** Terminado · **Épica:** EP-03-Gestión de convenios

## Necesidad de negocio (fuente: backlog exportado)

Como Gestor ORI, quiero revisar las solicitudes de convenio radicadas y aceptarlas, devolverlas con observaciones o rechazarlas, para determinar cuáles cumplen las condiciones necesarias para iniciar formalmente el trámite de un convenio.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Consultar solicitudes pendientes de revisión
- CA-02 — Aceptar una solicitud
- CA-03 — No crear automáticamente el convenio al aceptar
- CA-04 — Rechazar una solicitud

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/api/routers/solicitudes.py`
- `backend/tests/test_hu07_revision_solicitudes.py`
- `frontend/src/pages/SolicitudesRecibidasPage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-07 — Revisar y gestionar solicitud recibida 3e269ca9cb4080ba9ce6e62392242e90.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
