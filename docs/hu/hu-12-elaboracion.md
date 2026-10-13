# HU-12 — Elaborar el proyecto de convenio

**Sprint:** Sprint 2 - Operatividad · **Estado HU en el backlog:** Terminado · **Épica:** EP-03-Gestión de convenios

## Necesidad de negocio (fuente: backlog exportado)

Como Gestor ORI, quiero completar y estructurar la información contractual y administrativa de un convenio previamente generado a partir de una solicitud aceptada, para preparar el proyecto de convenio que será sometido a revisión jurídica.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Acceder a un convenio base para su elaboración
- CA-02 — Reutilizar la información disponible
- CA-03 — Completar información contractual y administrativa
- CA-04 — Mantener diferenciada la solicitud original
- CA-05 — Guardar avances de elaboración
- CA-06 — Validar información antes de finalizar
- CA-07 — Registrar trazabilidad de los cambios
- CA-08 — Finalizar elaboración y preparar revisión jurídica

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/services/convenios.py`
- `backend/tests/test_hu12_elaboracion.py`
- `frontend/src/pages/ConvenioElaboracionPage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-12 — Elaborar el proyecto de convenio 3d369ca9cb408024ada5e9584a467c87.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
