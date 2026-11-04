# HU-13 — Realizar revisión y aval jurídico del convenio

**Sprint:** Sprint 2 - Operatividad · **Estado HU en el backlog:** Terminado · **Épica:** EP-03-Gestión de convenios

## Necesidad de negocio (fuente: backlog exportado)

Como Revisor ORI, quiero revisar la información y documentación del proyecto de convenio y registrar su aprobación o devolverlo con observaciones, para verificar el cumplimiento jurídico e institucional antes de continuar con la revisión de la contraparte.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Acceder al convenio preparado para revisión jurídica
- CA-02 — Revisar sin modificar directamente el convenio
- CA-03 — Aprobar la revisión jurídica
- CA-04 — Devolver un convenio con observaciones
- CA-05 — Exigir observaciones al devolver
- CA-06 — Gestionar corrección y nueva revisión
- CA-07 — Mantener trazabilidad de cada revisión
- CA-08 — Restringir las acciones según el rol y resultado de la revisión

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/services/convenios.py`
- `backend/tests/test_hu13_revision.py`
- `frontend/src/pages/RevisionesJuridicasPage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-13 — Realizar revisión y aval jurídico del conv 3d369ca9cb4080b38e3bef7b332890de.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
