# HU-04 — Gestión de aliados

**Sprint:** Sprint 1 - Inicio · **Estado HU en el backlog:** Terminado · **Épica:** EP-02-Gestión de aliados

## Necesidad de negocio (fuente: backlog exportado)

Como Administrador ORI o Gestor ORI, quiero gestionar los aliados y asociarlos con los convenios correspondientes, para mantener una única identidad institucional por entidad y evitar registros duplicados.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Mantener solicitante mientras el convenio no esté activo
- CA-02 — Identificar aliado mediante NIT o documento
- CA-03 — Crear automáticamente un aliado por primera vez
- CA-04 — Reutilizar un aliado existente
- CA-05 — Manejar cambio de correo sin duplicar aliado
- CA-06 — Consultar aliado
- CA-07 — Editar información de un aliado
- CA-08 — Inactivar aliado sin convenios vigentes
- CA-09 — Impedir inactivación con convenios vigentes
- CA-10 — Reactivar un aliado
- CA-11 — Impedir duplicidad de aliados
- CA-12 — Restricción de gestión de aliados

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/api/routers/aliados.py`
- `backend/tests/test_epica02_aliados_convenios.py`
- `frontend/src/pages/AliadosPage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-04 — Gestión de aliados 3d869ca9cb4080d6a96de4fbaf56739e.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
