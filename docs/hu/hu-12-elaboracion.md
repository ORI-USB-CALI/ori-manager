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

### HU-10, bloque 4A: exportación sin solicitud de origen

`GET /api/convenios/{id}/exportar?formato=pdf|excel` admite convenios
`MANUAL_ORI` con `solicitud_id=NULL`. Sus antecedentes exclusivos de solicitud
se muestran como «No aplica (creación directa ORI)». Se conservan los datos
reales del convenio y del aliado; el correo del aliado se utiliza cuando no
existe una solicitud y no se supone el nombre de una persona de contacto.

El borrador exige objeto, entidad y contenido documental válido. La exportación
oficial mantiene además sus requisitos de código, vigencia, tipo y representantes
de la versión contractual. Un manual sin aliado devuelve HTTP 422 con
`CONVENIO_INCOMPLETO` y `entidad_participante`; la ausencia legítima de solicitud
no es un campo pendiente. Para `SOLICITUD` se conservan los antecedentes y la
contraparte propuesta cuando corresponda. Los permisos permanecen sin cambios.

> **Actualizado por HT-06.** El modo de emisión cambió: era borrador solo en la
> etapa de elaboración y ahora lo es en todo convenio no formalizado. En
> consecuencia, un manual sin aliado en revisión jurídica reporta únicamente
> `entidad_participante`, sin los representantes legales que antes exigía por
> emitir en modo oficial. Ver
> [HT-06 — Código institucional del convenio](ht-06-codigo-convenio.md).

Regresión automática: `backend/tests/test_hu10_exportacion.py`, con archivos PDF
y Excel reales, ambos orígenes, borrador/oficial, validación de faltantes y
protección frente a fórmulas en Excel. Reutiliza los fixtures del diagnóstico
`backend/tests/diagnostico_hu10_ciclo_vida.py`, que se conserva como evidencia.

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [Centro de evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).
- Archivo original en export de Historias de Usuario: `HU-12 — Elaborar el proyecto de convenio 3d369ca9cb408024ada5e9584a467c87.md`.

**Estado documental:** reconstrucción referencial (13/10/2026), sin atribuir ejecuciones de prueba inexistentes. Para una modificación funcional posterior, actualizar esta ficha en el mismo commit y adjuntar PR y evidencia correspondiente.
