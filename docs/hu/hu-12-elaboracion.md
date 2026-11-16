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

### Corrección bloqueante: antecedentes separados del documento contractual

Esta corrección sustituye la prevención estructural del PR #186 y el ajuste de
mensaje del PR #190 descrito abajo. La solicitud es referencia; sus antecedentes
no se convierten automáticamente en cláusulas. Al iniciar un convenio nuevo desde
solicitud se crea un documento vacío válido, o se copia la única plantilla activa
si es válida, no contiene variables de solicitud ni la estructura de antecedentes.
Los datos clave siguen disponibles y la solicitud conserva su relación y acceso.
Los convenios manuales y las renovaciones mantienen su inicialización anterior.

La lectura de Elaboración añade `contiene_antecedentes_iniciales`, calculado sin
escrituras. En un borrador antiguo habilita «Empezar documento contractual limpio».
La confirmación advierte que reemplaza todo el contenido local y permite cancelar.
Antes de confirmar se puede revisar/copiar el editor; después se conserva una copia
consultable en pantalla hasta salir. El reemplazo remonta el editor y se guarda
solo mediante las acciones existentes y su `expected_revision`. Un 409 conserva
los cambios locales. No se reescriben versiones ni se sustituye contenido al abrir.

Finalizar valida datos obligatorios, texto válido no vacío, etapa, permisos,
observaciones y concurrencia. Los títulos o la estructura de antecedentes no son
una regla semántica de aceptación jurídica. La revisión jurídica existente decide
el contenido. La exportación oficial sigue rechazando la estructura histórica
ambigua, incluso si llegó a revisión: para emitirla se requiere una nueva versión
contractual revisada; nunca se corrige una versión aprobada en el sitio.

QA en staging, después de desplegar el PR: abrir #97, comprobar que conserva todo
el texto y sus párrafos adicionales; copiar lo que deba conservarse; iniciar la
acción, cancelar y verificar que nada cambió. Repetir y confirmar, redactar el
contrato, guardar avance y finalizar. Debe pasar a Jurídica. En otra sesión,
guardar antes de la primera debe producir conflicto, sin sobrescribir ese avance.
Para un convenio nuevo, iniciar desde una solicitud aceptada: editor vacío,
antecedentes accesibles por «Consultar solicitud original», datos clave separados.
Completar el contrato, recorrer las revisiones y firmas habituales y verificar
PDF/Excel contra los datos aprobados. Un documento vacío debe seguir rechazándose.

No se agregan migraciones ni se cambian solicitudes, contenido firmado o históricos.
Las pruebas de recuperación y concurrencia están en
`test_obs003_prevencion_elaboracion.py` y `ConvenioElaboracionPage.test.tsx`;
HU-15 cubre formalización y exportación del contrato limpio.

Verificación local de esta corrección: 553 pruebas backend aprobadas (HU-12,
HU-10, HU-15, HT-13, HT-15, HU-24, OBS-S3-003, integración de solicitud,
exportación API y acciones de renovación HU-31); 57 frontend aprobadas
(Elaboración, confirmación y vigencia). Ruff, TypeScript, ESLint y
`git diff --check` aprobados. La base local anterior carecía de la columna de
observaciones obligatorias: se creó `ori_contractual_test` en Docker y se aplicaron
las migraciones ya existentes exclusivamente allí. No se crearon migraciones ni
se accedió a staging/producción. Las advertencias restantes son deprecaciones de
dependencias (20 backend), sin pruebas omitidas ni xfail en esta selección.

### Corrección del mensaje de contenido inicial en Elaboración

Al finalizar con información inicial de la solicitud sin sustituir, se conserva
HTTP 422 y el contrato `detail.faltantes` con `campo=contenido`. El motivo ahora
indica: «El documento todavía contiene información inicial de la solicitud.
Debes reemplazarla por el texto definitivo del convenio antes de enviarlo a
revisión jurídica». El resumen en pantalla se titula «Revisa lo siguiente antes
de finalizar», y conserva los mensajes de otros campos y sus errores junto a
cada control.

Se mantienen los permisos de edición y las reglas contractuales. El rechazo no
modifica documento, metadatos, borrador, versiones, revisiones, historial,
auditoría ni solicitud; un texto contractual válido permite finalizar. No hay
cambios de plantillas, estructura documental, snapshots o versiones históricas,
ni se requieren migraciones.

Regresión: `backend/tests/test_obs003_prevencion_elaboracion.py` cubre rechazo
desde borrador, formulario y versión histórica, con o sin texto añadido,
ausencia de efectos y aceptación de texto contractual.
`frontend/src/pages/ConvenioElaboracionPage.test.tsx` comprueba el mensaje,
el encabezado, la ausencia de referencias técnicas en pantalla y notificaciones,
la conservación de lo escrito y los errores simultáneos de otros campos.

Verificación local (15/11/2026): 51 pruebas backend aprobadas entre la regresión
anterior, `test_hu12_elaboracion.py` y `test_integracion_solicitud_elaboracion.py`,
contra PostgreSQL local en Docker, sin ejecutar migraciones; 54 pruebas frontend
aprobadas entre la página, `FinalizarElaboracionModal.test.tsx` y
`vigencia.test.tsx`. Ruff, TypeScript, ESLint y `git diff --check` aprobados.

La revisión se limita a la página de Elaboración, su confirmación y las
validaciones que consumen. Se detectaron además mensajes técnicos en los errores
de estructura documental inválida (`contenido_convenio.py`) y de configuración
de etapas; se registran sin alterarlos para preservar el contrato API y el
alcance de esta corrección. No se atribuye esta revisión a una aceptación en
staging ni se modifica el estado histórico de la HU.

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
