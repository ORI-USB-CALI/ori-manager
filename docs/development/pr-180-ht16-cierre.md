## Resumen

HT-16 corrige [QA #172](https://github.com/ORI-USB-CALI/ori-manager/issues/172): completar la contraparte «Por definir» permite continuar el trámite manual con validaciones claras. Esta entrega conserva la auditoría correctiva y cierra la identidad jurídica mutable con el mismo ID y la idempotencia del reenvío.

Rama: `feature/ht-16DesbloquearRevsDeContraprPorDefnr`; base: `develop`; [PR #180](https://github.com/ORI-USB-CALI/ori-manager/pull/180). El inventario oficial versionado no contiene HT-16: no se inventa sprint ni se cambia el estado del backlog. QA/UAT y merge quedan pendientes de aprobación del líder técnico.

## Cambios funcionales

- Catálogo con el contrato real `{items,total}`, filtro `activo=true` y todas las páginas; carga, error con reintento, vacío y contraparte actual visible.
- Snapshots de versión/RJ1/RJ2 con `aliado_identidad`: nombre o razón social, tipo, tipo de identificación, número y DV. Cambiar cualquiera de ellos conserva los avales históricos y exige nuevos avales, aunque el ID sea el mismo. Los datos de contacto permanecen editables.
- Asignación inicial desde Por definir: los tres snapshots deben tener ID e identidad nulos y existir una única asignación auditada. Una huella SHA-256 en la bitácora congela la identidad elegida; modificarla posteriormente no puede reutilizar esa excepción.
- Rectificar contraparte vuelve a Elaboración. Ante un cambio de identidad se ofrece reapertura explícita, también para convenios de solicitud: `POST /api/convenios/{id}/revision-juridica/reabrir-por-identidad`, con `expected_version`. Sin cambiar solicitud ni aliado, se obtiene una nueva versión y ronda RJ1/RJ2.
- `expected_invitacion_id` es obligatorio en el cuerpo de reenvío y en el servicio. Sin cuerpo/campo o con valor inválido: 422. ID obsoleto o repetido: 409 sin correo ni invitación adicional. No se mantiene compatibilidad opcional: el proyecto no tiene clientes productivos.
- Correo obligatorio en manuales, rollback ante rechazo del proveedor (502) y conciliación del historial ante commit no confirmado (503), con trazas sin tokens.
- Corrección residual de `b46b4d9`: el enlace público vuelve a validar identidad contra versión/RJ1/RJ2 o la asignación inicial auditada antes de permitir acceso, aprobación o devolución. Comparte la lectura bloqueada y la huella existentes; las discrepancias devuelven únicamente el error público genérico `ENLACE_NO_DISPONIBLE`.
- Recuperación administrativa explícita de invitaciones manuales ya enviadas: `POST /api/convenios/{id}/revision-contraparte/{revision_id}/invalidar-por-identidad`, con versión e invitación esperadas. Solo Gestor/Admin y solo si la identidad no está autorizada. Revoca enlaces y resuelve la revisión como devolución administrativa, con actor y auditoría, antes de volver a Elaboración para nuevos RJ1/RJ2. No crea una decisión externa ni altera avales históricos. La UI exige confirmación.

## Criterios de aceptación y seguridad

| Criterio | Evidencia |
|---|---|
| CA-01 | Impide envío Por definir, con aliado inactivo, inexistente o sin correo válido |
| CA-02 | Asignación/rectificación auditada; Gestor/Admin autorizados; Revisor/solicitantes sin permiso |
| CA-03 | Estados UI y errores API claros; fallo de correo sin revisión fantasma; invitación previa preservada al fallar un reenvío |
| CA-04 | Identidad congelada en versión y avales; bloqueo en RJ1/RJ2 y envío; excepción inicial limitada y nueva ronda tras cambios |
| CA-05 | ID obligatorio, reintentos y duplicados sin efectos adicionales; cinco pruebas de concurrencia PostgreSQL |
| CA-06 | Regresiones pertinentes de HU-10/12/13/14 y HT-18; catálogo y contratos API/frontend |

Se conserva la matriz central de permisos. 401 sin sesión; 403 sin permiso; 404 por recurso inexistente; 409 por etapa, versión, revisión pendiente o identidad incompatible; 422 por contrato inválido; 502 por proveedor; 503 por correo sin configurar o persistencia no confirmada. La identidad incompatible devuelve `detail.codigo=IDENTIDAD_ALIADO_CAMBIADA` y `message`.

Convenio y revisión usan bloqueo transaccional; la identidad se relee del aliado persistido y mantiene `FOR SHARE` hasta commit. La edición concurrente espera durante esa operación, sin prohibición global de editar aliados compartidos. Las aprobaciones históricas no se reescriben y una revisión de contraparte pendiente impide cambiar la contraparte o reabrir el convenio.

La nueva recuperación es una acción separada de esa reapertura ordinaria: exige una revisión manual pendiente y una identidad incompatible, invalida/resuelve primero el ciclo y registra su autoría administrativa. El acceso público mantiene bloqueos compartidos; las decisiones y la recuperación toman los bloqueos exclusivos en el mismo orden. Cambiar solo contactos no invalida los avales ni cambia el destinatario de una invitación ya emitida.

## Validación local — 14/11/2026

- **287 pruebas backend aprobadas** en 11 archivos de HT-16 y HU-10/12/13/14, incluidos **67 casos HT-16 y cinco de concurrencia PostgreSQL**.
- **199 pruebas frontend aprobadas** en 11 archivos, incluidas 21 del detalle, 18 de versiones y regresiones HT-18 de navegación por rol, visor PDF, soportes, bitácora y responsive.
- Ruff completo sin nuevas supresiones; TypeScript, ESLint, build y `git diff --check` pasan.
- PostgreSQL local aislado `ori_manager_ht16_audit_20261114`, migrado a `0b2fb1bed5b2`. Sin migraciones nuevas, dependencias ni cambios de staging/producción.
- Se usó `--pool=threads --maxWorkers=2` para el montaje Windows. Ruff se comprobó sobre copia Linux del contenido final con modos 100644, sin ignorar EXE002.

La auditoría anterior ejecutó el backend completo: **2806 aprobadas y 47 errores de fixture de HU-31**. Esos mismos 47 errores se reprodujeron sobre el HEAD original limpio `9c802e7` (49 aprobadas en HU-31). La fecha fija de su fixture produce un vencimiento anterior al reloj real de creación. No se modificó HU-31 ni se presenta la suite global como verde. El CI remoto final y QA/UAT deben comprobarse en el PR; esta evidencia local no los sustituye.

En el cierre se volvió a ejecutar HU-31: **49 aprobadas y los mismos 47 errores** (45,37 s). HT-16 se reverificó después de endurecer la condición inicial: **67 aprobadas** (23,96 s). La edición de la descripción remota volvió a recibir 403; este texto queda versionado para actualización manual, sin bloquear el commit/push autorizado.

Comandos, archivos, resultados y recuperación: [documentación de HT-16](../hu/ht-16-contraparte-por-definir.md). Logs/JUnit locales en `backend/var/ht16-audit/`, excluidos del commit.

Corrección residual posterior a `b46b4d9`, verificada localmente el 14/11/2026:
**361 pruebas backend aprobadas** (once archivos de HT-16/HU-10/12/13/14), incluidas
**141 de HT-16 y 15 de concurrencia PostgreSQL**, y **134 frontend aprobadas**
(cinco archivos, incluidas 23 del detalle). Pasan Ruff, TypeScript, ESLint, build y
`git diff --check`. Se prueban los cinco cambios de identidad tras invitar, ambos
tipos de asignación, acceso/aprobación/devolución, cada snapshot, contactos
permitidos, recuperación con permisos y precondiciones, rollback, trazabilidad y
nuevos RJ1/RJ2. Las carreras cubren ambos órdenes de edición frente al uso público,
dos recuperaciones y recuperación frente a las tres operaciones públicas.
No se modifica HU-31 ni se atribuyen resultados nuevos a su suite global.

## Riesgos y recuperación

Integración posterior a `2a179e5`: las evidencias explícitas de huella inicial y
revocaciones se centralizan en `services/bitacora.py`, reutilizando su constructor
de filas y la misma transacción. Se conservan todos los metadatos y el rollback;
no se serializan invitaciones ni se incorporan a los hooks generales. El test
arquitectónico de HU-18 permanece intacto. No cambian los flujos de HT-16 ni HU-31.
Validación de esta integración: **209 pruebas aprobadas** de HU-18, HT-16,
concurrencia y HU-14 público (69,55 s); Ruff completo y `git diff --check` pasan.
HU-31 se comprobó por separado: 49 aprobadas y los mismos 47 errores de fechas
del baseline (55,88 s), sin modificar esa historia ni el test arquitectónico de HU-18.

- Correo y PostgreSQL no comparten transacción: ante aceptación seguida de commit fallido o timeout ambiguo, puede llegar un enlace inválido o un correo adicional. Tras 503, consultar historial y usar el ID vigente antes de reintentar. No se promete una única entrega física ante fallos distribuidos. Outbox y conciliación del proveedor quedan como evolución separada del MVP.
- Un snapshot antiguo sin identidad no se completa artificialmente: exige nueva versión y avales. Sin datos productivos, se elimina la compatibilidad del reenvío sin ID.
- El bloqueo compartido dura hasta commit, incluido el envío síncrono del correo. Retener logs y habilitar INFO del servicio para correlacionar intentos y éxitos; no se registran tokens ni mensajes.
- No hay downgrade de esquema. Si se revierte el código, conservar auditorías, invitaciones, versiones y rondas ya generadas. No reescribir aprobaciones para desbloquear el flujo.

## Checklist

- [x] Código, pruebas y documentación de HT-16 incluidos; nuevos archivos identificados.
- [x] Revisada la política documental; sin logs, bases de datos, temporales ni secretos en el commit.
- [x] Sin funcionalidades nuevas ajenas a HT-16; cambios preexistentes de HT-18 conservados y verificados.
- [x] Riesgos y recuperación documentados.
- [ ] CI remoto final y aceptación QA/UAT pendientes de verificar.
- [ ] Merge a `develop`: reservado al líder técnico.
