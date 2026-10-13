# HU-02 — Gestión de roles

**Sprint:** Sprint 1 - Inicio · **Estado HU en el backlog:** Terminado · **Épica:** EP-01-Gestión de usuarios y acceso

## Necesidad de negocio (fuente: backlog exportado)

Como administrador ORI, quiero asignar roles diferenciados a los usuarios para controlar las funcionalidades a las que pueden acceder según sus responsabilidades.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Roles internos disponibles
- CA-02 — Asignar rol a un usuario
- CA-03 — Modificar rol
- CA-04 — Impedir selección de rol inválido
- CA-05 — Restricción de operaciones administrativas
- CA-06 — Aplicar cambio de permisos

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/core/roles.py`
- `backend/src/backend/core/permisos.py`
- `backend/tests/test_roles_permisos.py`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-02 — Gestión de roles 3c269ca9cb4080f8a4ead2938ca87314.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
