# HU-05 — Perfil del aliado

**Sprint:** Sprint 1 - Inicio · **Estado HU en el backlog:** Terminado · **Épica:** EP-02-Gestión de aliados

## Necesidad de negocio (fuente: backlog exportado)

Como usuario autorizado de la ORI, quiero consultar el perfil detallado de un aliado y sus convenios asociados, para obtener una vista consolidada de la relación institucional con dicho aliado.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Consultar información del aliado
- CA-02 — Visualizar convenios asociados
- CA-03 — Mostrar convenios independientemente de su estado
- CA-04 — Aliado sin convenios
- CA-05 — Aliado inexistente
- CA-06 — Usuario sin permisos
- CA-07 — Consistencia entre aliado y convenios
- CA-08 — Información histórica del aliado

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/api/routers/aliados.py`
- `frontend/src/pages/AliadoDetallePage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-05 — Perfil del aliado 3d369ca9cb408084a204d4ab95c754aa.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
