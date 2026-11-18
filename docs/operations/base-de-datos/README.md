# Script de base de datos — ORI Manager

**Revisión Alembic:** `0b2fb1bed5b2` (head de `main` al 12/11/2026, commit `e94e97b`)
**Motor:** PostgreSQL 18

> **Alcance temporal (17/11/2026):** este archivo SQL representa únicamente el esquema de `main` en la revisión `0b2fb1bed5b2`. La rama `develop` ya contiene las migraciones `c17a20261115` y `3816fbbdff1a`, que **no están incluidas** en el volcado. No debe presentarse como el esquema final de Sprint 5 ni como una exportación actualizada de Staging. Se deberá regenerar desde una base desechable, con el `head` efectivamente liberado, para la entrega definitiva.

| Archivo | Qué contiene |
|---|---|
| [`ori_manager_schema.sql`](ori_manager_schema.sql) | **Estructura sin datos.** Esquemas, tablas, índices, restricciones, funciones y triggers. Todas las tablas quedan vacías. |

El archivo es una **foto** del resultado de aplicar todas las migraciones. **Alembic sigue siendo la fuente de verdad** del esquema (ver [Supabase](../supabase.md#alembic)): cualquier cambio se hace con una migración nueva, nunca editando este archivo.

## Contenido

| Elemento | Detalle |
|---|---|
| Esquema `public` | 34 tablas de la aplicación + `alembic_version` |
| Esquema `ori_internal` | Función `conciliar_estados_ht10` (ver [Conciliación de convenios](../conciliacion-convenios.md) y [HT-10 cron](../ht10-supabase-cron.md)) |
| Triggers | `auditoria_completar_rol` y `auditoria_no_sobrescribible` sobre `auditoria` (ver [HT-09](../../hu/ht-09-auditoria-ampliada.md)) |

**No trae ninguna fila**, ni siquiera catálogos (roles, etapas, tipos de convenio, países, plantilla). Tampoco trae dueños (`OWNER`) ni permisos (`GRANT`): los roles y privilegios de cada entorno se configuran aparte, como se explica en [Supabase — Database roles](../supabase.md#database-roles).

## Uso

Requiere `psql` 18 (el script usa `\restrict`, que solo reconocen las versiones recientes del cliente) y una base **vacía**.

```bash
createdb ori_manager
psql -d ori_manager -v ON_ERROR_STOP=1 \
  -f docs/operations/base-de-datos/ori_manager_schema.sql
```

La conexión se configura con las variables estándar de `psql` (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGSSLMODE`). Los valores salen de la configuración de cada entorno y nunca se escriben en la documentación.

### Este script sirve para revisar el modelo, no para poner la aplicación en marcha

Como el script no incluye datos, la base resultante **no es utilizable por la aplicación**: faltan los roles, las etapas y los demás catálogos, y la tabla `alembic_version` queda vacía. Sin eso no se puede crear el primer administrador ni ningún convenio, y `alembic upgrade head` intentaría crear otra vez las tablas y fallaría.

**Para instalar la aplicación se usa Alembic** sobre una base vacía. Crea la misma estructura y además los catálogos que la aplicación necesita:

```bash
cd backend
uv run alembic upgrade head
uv run alembic current        # debe mostrar 0b2fb1bed5b2 (head)
```

Es el camino que usan CI, Staging y Producción. Ver el [manual técnico](../manual-tecnico-instalacion.md#44-crear-la-base-de-datos).

> No cargar este script sobre una base que ya tenga tablas, ni sobre Staging o Producción. Esos entornos se actualizan solo por el flujo de migraciones descrito en [Production Release Runbook](../production-release.md).

## Regenerar el script

Hay que regenerarlo cuando entren migraciones nuevas a `main`. Se hace **solo contra el PostgreSQL local** del devcontainer (servicio `db` de [`compose.yaml`](../../../compose.yaml)), en una base desechable:

```bash
createdb ori_script_bd
cd backend && DATABASE_NAME=ori_script_bd uv run alembic upgrade head && cd ..
pg_dump -d ori_script_bd --no-owner --no-privileges --no-comments \
  --restrict-key=orimanager --schema-only \
  > docs/operations/base-de-datos/ori_manager_schema.sql
dropdb ori_script_bd
```

`pg_dump` tiene que ser versión 18 o mayor (`postgresql-client-18`). Después de regenerarlo, actualizar la revisión y los conteos de este README.

**Por qué no se usa `alembic upgrade head --sql` (modo offline):** varias migraciones consultan datos mientras corren, por ejemplo `d9e1f3a5b7c2_hu14_hardening_revision_externa`, y `7f2a4c9d1e30_hu12_editor_versiones` inserta un JSONB que el modo offline no puede escribir. Por eso el script se saca de una base real ya migrada.

## Verificación realizada (12/11/2026)

1. Base desechable en el PostgreSQL local, `alembic upgrade head` hasta `0b2fb1bed5b2`: sin errores.
2. Volcado con `pg_dump` 18.7.
3. `ori_manager_schema.sql` en una base limpia con `ON_ERROR_STOP=1`: sin errores, 35 tablas y 0 filas.
4. Búsqueda de contraseñas, correos y credenciales en el archivo: no hay ninguna.
