# Regularización del código institucional de convenios

> **No autorizada sobre datos reales.** Este procedimiento está implementado y
> probado, pero su ejecución en Staging o Producción requiere dos cosas que
> todavía no existen: la validación institucional de la política de año por
> parte del Product Owner y una autorización explícita del Líder Técnico. El
> script lo impide por sí mismo: la ejecución real está restringida a
> `development` y `test`.

Alcance: asignar el código `USB-ORI-AAAA-NNNNN` a los convenios **ya
formalizados** que quedaron sin él, de antes de que la formalización lo
generara sola (HT-06, CA-08). No se agregó un programador automático, no se
modificaron los Blueprints de Render y no se tocó la configuración de Staging.

Contexto funcional en
[HT-06 — Código institucional del convenio](../hu/ht-06-codigo-convenio.md).

## Comportamiento

| Aspecto | Decisión |
|---|---|
| Candidatos | Convenios con `codigo` nulo **y** formalizados, usando el mismo predicado SQL que la consulta global (`filtro_convenio_formalizado()`: `fecha_firma` no nula y estado distinto de `EN_TRAMITE`/`CANCELADO`). |
| Códigos existentes | Nunca se sobrescriben ni se reasignan (RN-13). Un convenio con código no entra siquiera como candidato. |
| Códigos en blanco | Una cadena vacía o de solo espacios **no es un código**: no identifica nada y el validador de exportación la trata como faltante, así que el convenio quedaría sin poder emitir documento oficial y sin ser candidato a recibir uno. Se normaliza asignándole un código real. Un código con espacios alrededor sigue siendo un código y no se toca. |
| Idempotencia | Repetir el procedimiento no asigna nada ni consume consecutivos, porque solo mira `codigo IS NULL`. |
| Orden | Se bloquea por `id` (igual que la conciliación de estados, para fijar un orden único de candados) y se **asigna** en orden cronológico de formalización, de modo que el consecutivo de cada año siga la historia real. El resultado es el mismo en cada ejecución. |
| Transacción | Es una sola. Confirma todo o revierte todo; un error no deja asignaciones parciales. |
| Candados y tiempos | `SET LOCAL lock_timeout = '5s'` y `statement_timeout = '120s'`. |
| Reintentos | Hasta tres, con espera de 2 y 4 segundos, solo ante errores transitorios (`40001`, `40P01`, `55P03`, `57P03`, clase `08`, conexión invalidada). Un error permanente no se reintenta. |
| Logs | Sin conexiones, contraseñas ni parámetros SQL. Solo el nombre del tipo de excepción y el `sqlstate`. |
| Contención | Mientras corre, retiene el candado del contador de cada año que toca hasta confirmar. Una formalización del mismo año espera a que termine. Con `statement_timeout = '120s'` la espera está acotada, pero conviene ejecutarlo en una ventana de baja actividad. |

## Política de año

El año del código debe ser el de la formalización real. Solo se aceptan marcas
que escribe `formalizar()`, porque son las únicas que la evidencian:

1. **`convenio.activado_en`** — marca directa del convenio, convertida a
   `America/Bogota`.
2. **`completado_en` del proceso de firmas COMPLETADO** — respaldo para los
   convenios formalizados antes de que HU-20 agregara `activado_en`. Es también
   la respuesta a cuál firma representa la culminación del proceso: no una de
   las siete, sino el cierre del proceso que las reúne.
3. **Sin ninguna de las dos** → el convenio **no recibe código** y se reporta
   para revisión manual.

`fecha_firma` queda deliberadamente fuera como fuente de año: durante la
elaboración se puede diligenciar a mano, así que su presencia no distingue una
formalización real de un dato tecleado. Sí se usa como condición de candidatura,
porque es lo que el predicado de formalizado exige.

`--anio-politica AAAA` fuerza el año de todos los códigos, para cuando el PO
decida una política distinta. Con él, los convenios sin marca verificable
**sí** reciben código, porque el año lo decide la política y no un dato dudoso.

## Registro auditable

La operación se audita con la bitácora de HT-09, sin tabla nueva:

| Campo de `auditoria` | Valor |
|---|---|
| `evento` | `CODIGO_REGULARIZADO` |
| `contexto` | «Regularizó el código institucional de convenios formalizados» |
| `ejecucion` | `AUTOMATICA` |
| `usuario_id`, `rol` | El del usuario que autorizó la ejecución, si se indicó `--autorizado-por`; nulos si no. No se usa una cuenta ficticia (HT-09, RN-07). |
| `campo`, `valor_anterior`, `valor_nuevo` | `codigo`, nulo, el código asignado. |

`--autorizado-por` exige que el usuario exista y tenga rol
`ADMINISTRADOR_ORI`; cualquier otro id hace fallar el procedimiento antes de
abrir sesión de base de datos.

Consulta de revisión, con las horas en la zona del dominio:

```sql
SELECT a.fecha_hora AT TIME ZONE 'America/Bogota' AS momento_bogota,
       a.registro_id AS convenio_id,
       a.valor_nuevo AS codigo_asignado,
       a.ejecucion,
       a.usuario_id AS autorizado_por
  FROM auditoria a
 WHERE a.entidad = 'convenio'
   AND a.campo = 'codigo'
   AND a.evento = 'CODIGO_REGULARIZADO'
 ORDER BY a.fecha_hora, a.id;
```

Los convenios identificados para revisión no quedan en la base: se reportan en
el log con `anomalia=SIN_FECHA_DE_FORMALIZACION_VERIFICABLE` y
`accion=revisar_manualmente`.

El procedimiento diagnostica además, sin escribir nada, los convenios con
evidencia de formalización (`activado_en` o proceso de firmas completado) pero
sin `fecha_firma`, que el predicado de formalizado excluye. Se reportan como
`anomalia=FORMALIZADO_SIN_FECHA_DE_FIRMA`. **Ese estado no es alcanzable** por
la aplicación ni por las migraciones: `fecha_firma` solo la escribe
`formalizar()`, ningún schema de actualización la expone y el backfill de
`activado_en` en `e77280c6486a` la exige. Solo una manipulación directa de la
base podría producirlo, y entonces el convenio quedaría invisible para la
regularización; se reporta en lugar de ampliar el predicado de formalizado,
que cambiaría el significado de «formalizado» para todo el sistema.

## Invocación

```bash
python -m backend.cli.regularizar_codigos_convenio --simular
```

| Argumento | Efecto |
|---|---|
| `--simular` | Calcula los códigos que asignaría, bajo los mismos candados, y revierte. No deja códigos, ni consecutivos consumidos, ni auditoría. Sin restricciones. |
| `--anio-politica AAAA` | Fuerza el año de todos los códigos. Cuatro dígitos entre 1900 y 2999. |
| `--autorizado-por ID` | Id del `ADMINISTRADOR_ORI` que autoriza; queda como originador de la ejecución automática. **Obligatorio en ejecuciones reales.** |
| `--intentos N` | Entre 1 y 3; por omisión 3. |

### Condiciones de una ejecución real

Son tres, independientes, y ninguna sustituye a las otras. Una simulación no
necesita ninguna.

1. **Entorno** `development` o `test` (`APP_ENV`). Declara la intención.
2. **Destino local**: el host de la conexión debe ser `localhost`, `127.0.0.1`,
   `::1` o `db`. Comprueba dónde se escribiría de verdad, de modo que un
   `APP_ENV` mal configurado no alcance para modificar una base administrada.
   El mensaje de rechazo nombra solo el host, nunca la URL ni la contraseña.
3. **Identidad**: `--autorizado-por` con un `ADMINISTRADOR_ORI` existente, que
   queda como originador humano de una ejecución declarada automática.

Códigos de salida: `0` éxito, `1` fallo tras los reintentos, `2` argumentos o
entorno rechazados.

## Validación manual local

Desde el devcontainer, contra la base local. La simulación se corre dos veces
para evidenciar que no deja rastro:

```bash
cd /workspace/backend
uv run python -m backend.cli.regularizar_codigos_convenio --simular
uv run python -m backend.cli.regularizar_codigos_convenio --simular
```

Una ejecución real solo en desarrollo o pruebas:

```bash
cd /workspace/backend
uv run python -m backend.cli.regularizar_codigos_convenio --autorizado-por <id>
uv run python -m backend.cli.regularizar_codigos_convenio --autorizado-por <id>
```

La segunda debe reportar `asignados=0`: es la evidencia de idempotencia.

En un entorno distinto de `development` o `test`, una ejecución real sale con
código 2 y **no abre sesión de base de datos**.

## Configuración pendiente antes de ejecutarlo sobre datos reales

1. Validación de la política de año por el Product Owner.
2. Autorización explícita del Líder Técnico, con ventana acordada.
3. Respaldo verificable de la base, previo y comprobado.
4. Simulación previa en el entorno destino, con su salida archivada como
   evidencia.
5. Credencial de base de datos con privilegios mínimos: `SELECT` y `UPDATE` de
   `convenio.codigo`, `SELECT`/`INSERT`/`UPDATE` de `contador_codigo_convenio`
   e `INSERT` en `auditoria`. Sin privilegios DDL.
6. Revisión de los convenios reportados para revisión manual, antes de decidir
   si se les aplica una política de año explícita.
7. Actualización del MER con `contador_codigo_convenio`, coordinada con el DBA.

- [Conciliación de convenios](conciliacion-convenios.md), el procedimiento del
  que este toma su estructura.
- [Runbook de producción](production-release.md).
