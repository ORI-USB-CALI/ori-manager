# HU-06 — Registro base de convenio

**Sprint:** Sprint 1 - Inicio · **Estado HU en el backlog:** Terminado · **Épica:** EP-02-Gestión de aliados

## Necesidad de negocio (fuente: backlog exportado)

Como usuario de la ORI, quiero crear y consultar el registro base de un convenio, asociándolo con un aliado y la solicitud que le dio origen, para disponer de una estructura inicial sobre la cual gestionar su ciclo de vida.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Crear registro base de convenio
- CA-02 — Asociar convenio con un aliado
- CA-03 — Convenio sin aliado previamente creado
- CA-04 — Estado inicial del convenio
- CA-05 — Identificador único
- CA-06 — Consultar registro base
- CA-07 — Evitar relaciones inconsistentes
- CA-08 — Control de acceso

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/api/routers/convenios.py`
- `backend/tests/test_epica02_aliados_convenios.py`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-06 — Registro base de convenio 3d869ca9cb4080eabc28d39863163490.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
