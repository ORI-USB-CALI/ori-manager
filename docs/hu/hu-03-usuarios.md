# HU-03 — CRUD de usuarios

**Sprint:** Sprint 1 - Inicio · **Estado HU en el backlog:** Terminado · **Épica:** EP-01-Gestión de usuarios y acceso

## Necesidad de negocio (fuente: backlog exportado)

Como Administrador ORI, quiero crear, consultar, editar, activar y desactivar usuarios internos, para controlar quiénes tienen acceso al sistema y qué rol tienen asignado.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Listar usuarios internos
- CA-02 — Crear un usuario interno
- CA-03 — Validar información obligatoria
- CA-04 — Evitar usuarios duplicados
- CA-05 — Asignar únicamente roles internos permitidos
- CA-06 — Editar un usuario existente
- CA-07 — Cambiar el rol de un usuario
- CA-08 — Desactivar un usuario
- CA-09 — Usuario inactivo intenta acceder
- CA-10 — Conservar trazabilidad del usuario
- CA-11 — Evitar desactivar nuevamente un usuario inactivo
- CA-12 — Usuario ORI intenta administrar usuarios
- CA-13 — Invitado intenta acceder al módulo administrativo

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/api/routers/usuarios.py`
- `backend/tests/test_usuarios_api.py`
- `frontend/src/pages/UsuariosRolesPage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-03 — CRUD de usuarios 3d369ca9cb4080a6a4a1df909392d39e.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
