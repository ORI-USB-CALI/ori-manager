# HT-06 — Código institucional del convenio para su exportación

Referencia técnica: rama `feature/ht-06-generar-codigo-convenio`, base `develop`
(`2d635ce`, posterior a HT-13 y HT-09). Incidencias de origen:
[QA #145](https://github.com/ORI-USB-CALI/ori-manager/issues/145) (bloqueante) y
[QA #136](https://github.com/ORI-USB-CALI/ori-manager/issues/136).
Esta ficha describe el contrato técnico; no acredita aceptación QA, despliegue
ni cierre de issues.

## Problema de origen

`convenio.codigo` existía desde `e20406a1b2c3` pero **nunca se asignaba**: no
había generador ni secuencia, y el campo solo entraba por el payload de
creación. En la práctica quedaba nulo, con dos consecuencias:

- La consulta de convenios mostraba «Sin código» (QA #145).
- Un convenio fuera de la etapa de elaboración emitía en modo oficial, el
  documento oficial exige código y el código no existía: esos convenios **no
  podían exportarse nunca** (QA #136). Era un callejón sin salida estructural,
  no un dato faltante.

**Nomenclatura aprobada por el PO:** `USB-ORI-AAAA-NNNNN`.

## Criterios de aceptación CA-01 a CA-09

| Criterio | Contrato y evidencia |
|---|---|
| CA-01 — Identificación previa | Un convenio en trámite conserva su identificador interno y se muestra como `Convenio provisional #<id>`, distinguible del código oficial. No se asigna código anticipadamente. |
| CA-02 — Generación al formalizar | `ServicioFirmas.formalizar()` asigna `USB-ORI-AAAA-NNNNN` con el año calendario de `America/Bogota`, dentro de la misma transacción que confirma la formalización. |
| CA-03 — Consecutivo anual y unicidad | Consecutivo único por año, compartido por todos los convenios sin importar tipo, alcance u origen. Reinicia al cambiar de año. La unicidad se garantiza con un candado de fila, no con `MAX(codigo) + 1`. |
| CA-04 — Persistencia e inmutabilidad | Un convenio con código no se reasigna nunca: ni al cambiar de estado, ni al consultarlo, ni al exportarlo. Cada renovación es un convenio distinto con código propio. |
| CA-05 — Sin edición manual | `codigo` salió de `ConvenioCrear` y `ConvenioCrearManual`; con `extra="forbid"` un payload que lo envíe recibe 422. La actualización de elaboración ya no lo aceptaba. |
| CA-06 — Exportación oficial | El documento oficial usa el código persistido y no produce ninguna asignación. |
| CA-07 — Documentos previos | Un convenio en trámite emite documento de trabajo marcado `BORRADOR — NO FORMALIZADO`, en cualquier etapa, sin exigirle un código inexistente. |
| CA-08 — Regularización histórica | Procedimiento autorizado, idempotente y auditado, que asigna código solo a los convenios formalizados que no lo tienen, conserva los existentes e identifica para revisión los casos sin fecha verificable. |
| CA-09 — Integridad y auditoría | La asignación se audita como efecto automático de la formalización humana. Un error revierte formalización y código. No se reescriben snapshots aprobados ni documentos firmados. |

## Reglas de negocio RN-01 a RN-16

| Regla | Aplicación |
|---|---|
| RN-01 | El código se asigna únicamente al formalizar. |
| RN-02 | La generación y la persistencia son del backend. |
| RN-03 | Nomenclatura `USB-ORI-AAAA-NNNNN`. |
| RN-04 | `USB-ORI` es prefijo fijo (`PREFIJO_INSTITUCIONAL`). |
| RN-05 | `AAAA` es el año de formalización en `America/Bogota`, vía `fecha_actual_dominio()`. **No** se deriva de `datetime.now(UTC)`: a las 23:00 del 31 de diciembre en Bogotá, UTC ya cambió de año. |
| RN-06 | `NNNNN` es consecutivo anual, mínimo cinco dígitos con ceros a la izquierda. |
| RN-07 | El consecutivo se reinicia cada año y es compartido por convenios marco, específicos, nacionales, internacionales, manuales y derivados de solicitudes. |
| RN-08 | El código es único (restricción en PostgreSQL), persistente e inmodificable por operaciones ordinarias. |
| RN-09 | Cada renovación formalizada recibe código propio y conserva `convenio_origen_id`. No requiere lógica aparte: la renovación es una fila `Convenio` nueva que atraviesa `formalizar()`. |
| RN-10 | Los convenios no formalizados usan su identificador interno, que no equivale al código institucional. |
| RN-11 | La asignación es segura ante concurrencia y reintentos. |
| RN-12 | Pasado 99999 el consecutivo amplía su longitud sin truncarse ni repetirse: los cinco dígitos son un ancho mínimo, no un máximo. |
| RN-13 | Los códigos existentes no se sobrescriben ni se reasignan. |
| RN-14 | La exportación usa el código persistido y nunca lo genera como efecto secundario. |
| RN-15 | Asignación y formalización comparten integridad transaccional. |
| RN-16 | La asignación no altera documentos ni snapshots previamente firmados. |

## Modelo y contador

La migración `2fa11b85762d`, posterior a `9d53cf1dcef3` de HT-09, crea
únicamente `contador_codigo_convenio`. **No asigna códigos a los convenios
existentes**: eso es trabajo del procedimiento de CA-08.

| Columna | Tipo y restricciones |
|---|---|
| `anio` | Entero, clave primaria, no autoincremental: se recibe, no se genera. |
| `ultimo_consecutivo` | Entero, no nulo, `server_default 0`, `CHECK >= 0`. |

`convenio.codigo` no se migra: ya era `VARCHAR(40) UNIQUE NULL`, y
`USB-ORI-2026-00001` mide 18 caracteres. Ese `UNIQUE` es la red de seguridad de
RN-11.

**Por qué una tabla contador y no una secuencia:**

- CA-03 prohíbe apoyarse en `MAX(codigo) + 1` concurrente.
- Una secuencia de PostgreSQL por año exigiría `CREATE SEQUENCE` en tiempo de
  ejecución, y por tanto privilegios DDL para el usuario de la aplicación, que
  el estándar del proyecto prohíbe.
- La tabla con `SELECT ... FOR UPDATE` es coherente con el resto del código,
  **bloquea en vez de fallar** y no deja huecos: si la transacción se revierte,
  el consecutivo vuelve a quedar libre.

Las filas de cada año se crean solas al entregar su primer consecutivo, con
`INSERT ... ON CONFLICT (anio) DO NOTHING` para el caso en que dos
transacciones estrenen el mismo año a la vez. La migración no siembra ninguna y
no depende de la fecha en que se ejecute.

**Orden de bloqueo:** convenio → … → contador, siempre, y el contador lo más
tarde posible. Fija un orden único y descarta interbloqueos con la conciliación
de estados, que también bloquea convenios por id.

## Modo de emisión: cambio de contrato

`modo_emision()` pasó a decidirse por la formalización y no por la etapa:

```
OFICIAL   ⟺ convenio_esta_formalizado(convenio)
BORRADOR  ⟺ cualquier otro caso
```

Reutiliza el predicado de dominio que ya usaban la consulta global y los
filtros por fecha, de modo que «documento oficial» y «tiene código» coinciden
por construcción y el estado imposible de QA #136 desaparece.

| Etapa / estado | Antes | Ahora |
|---|---|---|
| ELABORACION, en trámite | BORRADOR | BORRADOR |
| Revisión jurídica, contraparte, revisión final, firmas (en trámite) | OFICIAL, sin poder exportar | BORRADOR |
| Formalizado (fuera de trámite y con fecha de firma) | OFICIAL | OFICIAL |
| Cancelado | OFICIAL | BORRADOR |

El cambio altera **cómo se emite** lo que cada etapa ya permitía exportar; no
habilita exportaciones que el flujo de negocio prohíba. `_faltantes_oficial()`
conserva la exigencia de código como red de seguridad para los convenios
heredados que aún no pasaron por la regularización.

En el documento, la identificación distingue los dos casos:

| Modo | Etiqueta | Valor |
|---|---|---|
| OFICIAL | `Código oficial` | `USB-ORI-2026-00001` |
| BORRADOR | `Identificación provisional` | `Convenio provisional #41` |

La decide `ConvenioPdfDTO.identificacion()`, para que el PDF y el Excel digan
lo mismo. No se agregaron campos al DTO ni a los schemas de lectura: la
referencia se deriva del identificador interno (RN-10).

## Contratos HTTP

HT-06 no agrega endpoints. Cambia dos contratos existentes:

| Endpoint | Cambio |
|---|---|
| `POST /api/convenios` | Ya no acepta `codigo`. Enviarlo responde **422** (CA-05). |
| `POST /api/convenios/manual` | Igual que el anterior. |
| `POST /api/convenios/{id}/firmas/formalizar` | Asigna el código en la misma transacción. La respuesta no cambia de forma; el código se lee en el detalle del convenio. |
| `GET /api/convenios/{id}/exportar` | Un convenio en trámite ya no responde 422 por falta de código: emite documento de trabajo. |

## Auditoría

La formalización declara su acción de negocio, que antes no tenía: era el único
paso del ciclo de vida sin evento, hueco que HT-09 dejó abierto.

| Campo | Valor |
|---|---|
| `evento` | `CONVENIO_FORMALIZADO` |
| `contexto` | «Formalizó el convenio tras completar las siete firmas obligatorias» |
| `etapa`, `version`, `responsable_id` | De `contexto_auditoria(convenio)` |
| `ejecucion` de la acción | `HUMANA` |
| `ejecucion` de la fila del campo `codigo` | `AUTOMATICA`, con el mismo originador e instante |

Se usa `describir_cambios_automaticos(db, convenio, "codigo")`: la
formalización la decide una persona y la asignación del código es su efecto
automático. Es el patrón que HT-09 previó en su CA-03, y respeta su RN-02
(ejecutarse en el backend no vuelve automática la operación entera) y su RN-07
(no se inventan usuarios).

`CAMPOS_SNAPSHOT` incluye `codigo` desde HU-12, así que las versiones creadas
antes de formalizar quedaron congeladas con `"codigo": null`. **No se
completan retroactivamente** (CA-09, RN-16).

## Regularización de convenios históricos

Procedimiento aparte, documentado en
[regularización de códigos](../operations/regularizacion-codigos-convenio.md).
Su ejecución sobre datos reales **no está autorizada**: la política de año es
una definición técnica provisional pendiente de validación del PO.

## Pruebas

| Archivo | Qué cubre |
|---|---|
| `backend/tests/test_ht06_generador_codigo.py` | Nomenclatura, consecutivo anual, RN-12, no reasignación, y los 422 de CA-05. |
| `backend/tests/test_ht06_formalizacion_codigo.py` | Asignación al formalizar, año de Bogotá, inmutabilidad, atomicidad y auditoría. |
| `backend/tests/test_ht06_concurrencia_codigo.py` | Reservas simultáneas y estreno de año. |
| `backend/tests/test_ht06_regularizacion_codigos.py` | Política de año, idempotencia, simulación y trazabilidad. |
| `backend/tests/test_cli_regularizar_codigos.py` | Argumentos, guarda de entorno, autorización y reintentos sin filtrar secretos. |
| `backend/tests/test_ht06_exportacion_codigo.py` | Regresión de QA #136, identificación provisional, RN-14 y el punto de contacto con HT-13. |
| `frontend/src/pages/referenciaConvenio.test.tsx` | Helper de referencia y lo que el menú de exportación anuncia. |

Las pruebas que tocan el contador usan **años propios** (2094–2099). El
consecutivo es estado global por año y hay pruebas de la suite que confirman de
verdad sobre `db_engine`, así que usar el año en curso ataría las aserciones al
orden de ejecución.

Regresión actualizada en HU-24 y HT-13 por el cambio de modo de emisión:
`test_hu24_borradores.py`, `test_hu24_validador_exportacion.py`,
`test_hu24_exportacion_segura.py`, `test_hu24_excel_convenio.py`,
`test_hu10_exportacion.py` y la fixture compartida `convenio_exportable`, que
ahora deja el convenio formalizado porque eso es lo que habilita el documento
oficial.

## Pendientes

1. La política de año de CA-08 es provisional; la valida el PO.
2. La ejecución de la regularización sobre Staging o Producción no está
   autorizada.
3. El MER debe recoger `contador_codigo_convenio`: coordinar con el DBA.

- [Inventario de estados de HU](../product/estado-hu-2026-10-13.md).
- [HT-09 — Auditoría ampliada](ht-09-auditoria-ampliada.md).
- [HT-13 — Borrador y versionamiento](ht-13-borrador-versionamiento.md).
