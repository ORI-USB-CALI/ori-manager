# HU-01 — Inicio de sesión

**Sprint:** Sprint 1 - Inicio · **Estado HU en el backlog:** Terminado · **Épica:** EP-01-Gestión de usuarios y acceso

## Necesidad de negocio (fuente: backlog exportado)

Como usuario autorizado, quiero iniciar sesión de manera segura en el sistema para acceder a las funcionalidades correspondientes a mi rol.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Inicio de sesión exitoso
- CA-02 — Credenciales incorrectas
- CA-03 — Campos obligatorios
- CA-04 — Usuario inactivo
- CA-05 — Aplicar permisos según rol
- CA-06 — Acceso a rutas protegidas sin autenticación
- CA-07 — Sesión inválida o expirada
- CA-08 — Cerrar sesión

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/api/routers/auth.py`
- `backend/tests/test_auth.py`
- `frontend/src/pages/LoginPage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-01 — Inicio de sesión 3c269ca9cb4080799d71edc8ec784ce8.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
