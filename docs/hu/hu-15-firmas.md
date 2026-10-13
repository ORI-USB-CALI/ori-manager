# HU-15 — Gestionar revisión final y proceso de firmas

**Sprint:** Sprint 2 - Operatividad · **Estado HU en el backlog:** Terminado · **Épica:** EP-03-Gestión de convenios

## Necesidad de negocio (fuente: backlog exportado)

Como Gestor ORI, quiero gestionar la revisión final y el proceso de firmas de un convenio aprobado por la contraparte, para verificar que la versión definitiva cumpla las condiciones requeridas, registrar las siete firmas obligatorias y completar su formalización antes del archivo y seguimiento.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Iniciar revisión final
- CA-02 — Impedir firmas con revisiones pendientes
- CA-03 — Devolver el convenio desde la revisión final
- CA-04 — Aprobar el convenio para iniciar firmas
- CA-05 — Registrar los siete firmantes
- CA-06 — Registrar firma electrónica
- CA-07 — Registrar proceso de firma física
- CA-08 — Consultar estado de las firmas
- CA-09 — Proteger la versión aprobada para firma

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/services/firmas.py`
- `backend/tests/test_hu15_revision_final_firmas.py`
- `frontend/src/components/RevisionFinalConvenio.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-15 — Gestionar revisión final y proceso de firm 3d369ca9cb408079b58cdd99789125b1.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
