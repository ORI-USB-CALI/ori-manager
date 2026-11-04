# HU-17 — Visualizar tablero operativo de convenios

**Sprint:** Sprint 2 - Operatividad · **Estado HU en el backlog:** Terminado · **Épica:** EP-03-Gestión de convenios

## Necesidad de negocio (fuente: backlog exportado)

Como usuario interno autorizado de la ORI, quiero visualizar un tablero operativo con los convenios en trámite, su etapa actual, estado y responsable, para supervisar el flujo de trabajo y localizar rápidamente los procesos que requieren seguimiento.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Consultar el tablero de convenios
- CA-02 — Visualizar la etapa actual del convenio
- CA-03 — Mostrar información operativa básica
- CA-04 — Reflejar el estado real del proceso
- CA-05 — Respetar permisos según el rol
- CA-06 — Acceder al detalle del convenio
- CA-07 — No permitir cambios arbitrarios de etapa
- CA-08 — Tablero sin convenios en trámite

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/api/routers/convenios.py`
- `backend/tests/test_hu17_tablero.py`
- `frontend/src/pages/TableroConveniosPage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-17 — Visualizar tablero operativo de convenios 3d369ca9cb4080efbf5ae77bbd2cc0e0.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
