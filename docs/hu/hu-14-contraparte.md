# HU-14 — Gestionar revisión de la contraparte

**Sprint:** Sprint 2 - Operatividad · **Estado HU en el backlog:** Terminado · **Épica:** EP-03-Gestión de convenios

## Necesidad de negocio (fuente: backlog exportado)

Como Gestor ORI, quiero registrar el envío del convenio a la contraparte y gestionar el resultado de su revisión, incluyendo aprobaciones u observaciones, para mantener actualizado y trazable el trámite hasta obtener la aprobación externa requerida.

## Criterios de aceptación identificados

Los siguientes títulos se extraen del archivo Markdown de la HU en el export adjunto. Para el texto Given/When/Then completo y sus aclaraciones debe consultarse la historia original. **No se sustituyen ni se reescriben sus CA**.

- CA-01 — Enviar el convenio a la contraparte dentro de la plataforma
- CA-02 — Impedir envío sin aval jurídico
- CA-03 — Aprobar el convenio por parte de la contraparte
- CA-04 — Devolver el convenio con observaciones
- CA-05 — Exigir observaciones cuando la contraparte no apruebe
- CA-06 — Atender observaciones y realizar correcciones
- CA-07 — Reenviar el convenio después de las correcciones
- CA-08 — Mantener trazabilidad de la revisión de contraparte

## Puntos técnicos de mantenimiento

Componentes o pruebas de referencia observados en la rama `develop` (su presencia no constituye por sí sola un resultado nuevo de QA ni reproduce el estado histórico exacto del cierre):

- `backend/src/backend/services/contraparte_externa.py`
- `backend/tests/test_hu14_revision_contraparte.py`
- `frontend/src/pages/RevisionContrapartePage.tsx`

Los permisos, transiciones y excepciones se verifican contra las implementaciones actuales y los CA de la HU. No se deben inventar endpoints ni asumir acceso por pertenecer a un rol; usar la matriz central de permisos.

## Evidencia y cambios posteriores

- HU-10 (PR #126): el router público se habilita para convenios `MANUAL_ORI`,
  que carecen de solicitud y de Solicitante. Se conserva el flujo autenticado
  del FIX de HU-14 (#102) para convenios `SOLICITUD`; incluso sus enlaces
  históricos se rechazan en el servicio público. El enlace manual reutiliza
  tokens aleatorios de 48 bytes, almacenados como SHA-256, con vigencia de una
  hora, revocación y consumo al decidir. Solo sirve mientras la revisión de
  contraparte está pendiente y su versión sigue vigente. Las decisiones
  conservan los bloqueos transaccionales existentes y no omiten los dos avales
  jurídicos. Cobertura: `backend/tests/test_hu14_revision_contraparte_publica.py`.
- Snapshots de HU-12: `origen` integra el contrato de catorce campos de las
  nuevas revisiones y versiones. Los JSONB históricos sin esa clave se leen
  sin completarlos ni reescribirlos; la regresión de compatibilidad está en
  `backend/tests/test_hu12_editor_versiones.py`.

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-14 — Gestionar revisión de la contraparte 3d369ca9cb4080948727f36a8f1679cb.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
