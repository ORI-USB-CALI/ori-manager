# HU-08 — Gestión de credenciales

**Sprint:** Sprint 2 - Operatividad · **Estado HU en el backlog:** Terminado · **Épica:** EP-01-Gestión de usuarios y acceso

## Necesidad de negocio (fuente: backlog exportado)

Como usuario interno registrado, quiero solicitar la recuperación y establecer una nueva contraseña, para restablecer mi acceso al sistema en caso de olvido.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Solicitar recuperación de contraseña
- CA-02 — Enviar instrucciones a un usuario registrado
- CA-03 — Solicitud con correo no registrado
- CA-04 — Establecer una nueva contraseña
- CA-05 — Las contraseñas no coinciden
- CA-06 — Contraseña que no cumple la política
- CA-07 — Solicitud expirada
- CA-08 — Evitar reutilización
- CA-09 — Usuario inactivo

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/services/recuperacion_contrasena.py`
- `backend/tests/test_hu08_recuperacion_contrasena.py`
- `frontend/src/pages/RecuperarContrasenaPage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-08 — Gestión de credenciales 3d369ca9cb40802da002e187ba45350c.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
