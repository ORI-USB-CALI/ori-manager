# Supabase PostgreSQL — ORI Manager

## Purpose

Supabase is used by ORI Manager as the managed PostgreSQL provider for cloud environments.

The application does not access Supabase directly from the React frontend.

The intended architecture is:

```text
React
  |
  | HTTPS
  v
FastAPI
  |
  | SQLAlchemy + Psycopg
  | PostgreSQL over TLS
  v
Supabase PostgreSQL
```

## Data API

The Supabase Data API is disabled.

ORI Manager does not currently use:

- Supabase REST API
- Supabase GraphQL API
- Supabase client libraries in the frontend
- Supabase Auth
- Supabase Storage

Database access is performed exclusively by the FastAPI backend through PostgreSQL.

## Connection strategy

Cloud connections use the Supabase Shared Session Pooler.

```text
Connection mode: Session pooler
Port:            5432
Database:        postgres
SSL mode:        require
```

The host and project reference are environment-specific and must not be hardcoded in application source code.

### Runtime connection

FastAPI uses the restricted PostgreSQL role:

```text
ori_app_runtime.<project-ref>
```

### Administrative and migration connection

Database migrations and administrative operations use:

```text
postgres.<project-ref>
```

The administrative credential must never be used as the normal FastAPI runtime credential.

## Environment configuration

### Local development

Local PostgreSQL runs inside Docker Compose.

```env
DATABASE_HOST=db
DATABASE_PORT=5432
DATABASE_NAME=ori_manager
DATABASE_USER=ori_user
DATABASE_PASSWORD=<local-development-password>
DATABASE_SSLMODE=disable
```

### CI

GitHub Actions uses the PostgreSQL service container and:

```env
DATABASE_SSLMODE=disable
```

### Supabase / cloud runtime

The backend must receive its credentials through the deployment platform's secret or environment configuration.

```env
DATABASE_HOST=<session-pooler-host>
DATABASE_PORT=5432
DATABASE_NAME=postgres
DATABASE_USER=ori_app_runtime.<project-ref>
DATABASE_PASSWORD=<runtime-secret>
DATABASE_SSLMODE=require
```

Secrets must never be committed to Git.

## Database roles

### `postgres`

Responsibilities:

- Database administration.
- Alembic migrations.
- Schema creation and modification.
- Ownership of application tables.

It must not be used by the normal application runtime.

### `ori_app_runtime`

The application role is intentionally restricted.

Allowed:

```text
LOGIN
CONNECT
USAGE on schema public
SELECT
INSERT
UPDATE
DELETE
USAGE/SELECT on required sequences
```

Not allowed:

```text
SUPERUSER
CREATEDB
CREATEROLE
REPLICATION
CREATE on schema public
ALTER application schema
DROP application objects
TRUNCATE
ownership of application tables
access to alembic_version
```

A functional permission test verified that this role can perform application CRUD operations but cannot drop application tables.

## Default privileges

Objects created by the migration role `postgres` in schema `public` automatically grant the runtime role the required DML privileges.

Current policy:

```sql
ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES
TO ori_app_runtime;

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES
TO ori_app_runtime;
```

Automatic Data API privileges for the Supabase roles are removed:

```sql
ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA public
REVOKE ALL PRIVILEGES ON TABLES
FROM anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA public
REVOKE ALL PRIVILEGES ON SEQUENCES
FROM anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA public
REVOKE ALL PRIVILEGES ON FUNCTIONS
FROM anon, authenticated, service_role;
```

The existing `public.alembic_version` table also has its privileges revoked from:

```text
anon
authenticated
service_role
ori_app_runtime
```

If Alembic is later migrated from `postgres` to a dedicated migration role such as `ori_migrator`, equivalent default privileges must be configured for that role.

## Alembic

Alembic is the source of truth for application schema changes.

The initial cloud baseline is:

```text
56626120dc9a
```

The Supabase database contains:

```text
public.alembic_version
```

The baseline revision has been validated with:

```bash
uv run alembic current
```

Expected result:

```text
56626120dc9a (head)
```

Schema changes must be performed through versioned Alembic migrations rather than manual changes in the Supabase Table Editor.

## TLS

Cloud database connections require:

```env
DATABASE_SSLMODE=require
```

Local Docker PostgreSQL and the CI PostgreSQL service use:

```env
DATABASE_SSLMODE=disable
```

The application default is `require`, so remote database connections fail closed unless another mode is explicitly configured.

## Health checks

FastAPI exposes:

```text
GET /health
GET /ready
```

`/health` verifies that the application process is alive.

`/ready` verifies that the application can reach PostgreSQL.

The complete runtime path has been validated using the restricted `ori_app_runtime` role:

```text
FastAPI
  -> SQLAlchemy
  -> Psycopg
  -> TLS
  -> Supabase Session Pooler
  -> PostgreSQL
```

Both endpoints returned HTTP 200 during the cloud integration validation.

Example successful readiness response:

```json
{
  "status": "ok",
  "database": "reachable"
}
```

## Security baseline

The initial Supabase hardening includes:

- Data API disabled.
- Separate administrative and runtime database roles.
- Least-privilege runtime access.
- Runtime DDL denied.
- Data API roles removed from application table default privileges.
- TLS required for cloud database connections.
- Database secrets kept outside the repository.

A functional permission test confirmed that `ori_app_runtime` can perform:

```text
SELECT
INSERT
UPDATE
DELETE
```

and cannot perform destructive schema operations such as:

```text
DROP TABLE
```

At the end of the initial setup:

```text
Security Advisor:    0 errors, 0 warnings
Performance Advisor: 0 errors, 0 warnings
```

Advisors should be reviewed again after significant schema changes.

## Operational notes

Do not:

- Commit database passwords.
- Commit complete connection strings containing credentials.
- Use the `postgres` credential for FastAPI runtime.
- Modify production schema manually through the Supabase Table Editor.
- Enable the Data API without reviewing RLS and database grants first.
- Give the runtime role ownership of application objects.

When deploying a new environment:

1. Configure its secrets independently.
2. Use `ori_app_runtime` for normal backend execution.
3. Use the migration role only for Alembic operations.
4. Require TLS for cloud PostgreSQL connections.
5. Run Alembic migrations before exposing the application.
6. Validate `/health` and `/ready`.
7. Review Supabase Security Advisor.
8. Review Supabase Performance Advisor.
