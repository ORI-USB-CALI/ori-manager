# Production Release Runbook — ORI Manager

## Purpose

This document defines the controlled process for promoting ORI Manager from
Staging to Production.

Production deployments are intentionally manual.

The current deployment architecture is:

```text
develop
  |
  v
Render Staging
  |
  v
Supabase Staging


main
  |
  v
Render Production
  |
  v
Supabase Production
```

Staging and Production use independent Supabase projects and independent
database credentials.

---

## Branch strategy

Normal development follows:

```text
feature/*
fix/*
chore/*
docs/*
    |
    v
develop
```

Pull requests into `develop` normally use:

```text
Squash and merge
```

A production release follows:

```text
develop
    |
    | Pull Request
    v
main
```

Pull requests from `develop` to `main` use:

```text
Create a merge commit
```

Direct pushes to `develop` and `main` are not part of the normal workflow.

---

## Environment policy

### Staging

Source branch:

```text
develop
```

Render configuration:

```text
render.yaml
```

Staging is used to validate changes before a production release.

### Production

Source branch:

```text
main
```

Render configuration:

```text
render.production.yaml
```

Production uses controlled deployment settings:

```text
Blueprint Auto Sync: OFF
Backend Auto-Deploy: OFF
Frontend Auto-Deploy: OFF
```

Production deployments therefore require an explicit action from an authorized
technical lead.

---

## Production release prerequisites

Before promoting `develop` to `main`, confirm:

- Staging is operational.
- The intended changes have been validated.
- Backend CI passes.
- Frontend CI passes.
- CodeQL passes.
- Required code-owner review is complete.
- Production secrets are configured.
- Production database connectivity is available.
- Production Auto-Deploy remains disabled.
- Any database migration has been reviewed before execution.

Do not release while any required validation is failing.

---

## Step 1 — Promote develop to main

Create a Pull Request:

```text
base: main
compare: develop
```

Review the complete release scope.

Wait for the required checks and approvals.

Merge using:

```text
Create a merge commit
```

Do not use Squash and merge for the `develop -> main` production promotion.

After the merge, record the resulting `main` commit SHA.

---

## Step 2 — Synchronize the local release workspace

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git status
```

The working tree must be clean before continuing.

---

## Step 3 — Verify the Production database revision

Database migrations are executed using the Production administrative/migration
credential.

The FastAPI runtime credential `ori_app_runtime` must never perform migrations.

Production cloud connections use:

```text
Supabase Session Pooler
Port: 5432
SSL mode: require
```

Configure the Production database environment temporarily in the operator
shell without storing passwords in the repository.

Verify:

```bash
uv run alembic current
uv run alembic heads
```

Review the current revision and target revision before applying changes.

---

## Step 4 — Apply Production migrations

Only after reviewing the migration target:

```bash
uv run alembic upgrade head
```

Then verify:

```bash
uv run alembic current
```

The final revision must match:

```bash
uv run alembic heads
```

If a migration fails:

```text
STOP THE RELEASE
```

Do not deploy the new backend until the database state has been understood and
corrected.

Do not perform manual schema modifications through the Supabase Table Editor as
a substitute for an Alembic migration.

---

## Step 5 — Synchronize Render infrastructure when required

The Production Blueprint is:

```text
render.production.yaml
```

Blueprint Auto Sync is disabled.

A Blueprint sync is only necessary when production infrastructure configuration
has changed.

Before synchronizing, review the Render change plan.

Existing Production resources must be associated rather than duplicated:

```text
ori-manager-backend-production
ori-manager-frontend-production
```

Do not create duplicate Production services.

---

## Step 6 — Deploy Backend Production

Deploy the backend manually from Render.

The deployed revision must correspond to the intended `main` release.

Wait until the service reaches a successful deployed state.

Validate:

```bash
curl -i https://ori-manager-backend-production.onrender.com/health
```

Expected:

```json
{"status":"ok"}
```

Then validate database readiness:

```bash
curl -i https://ori-manager-backend-production.onrender.com/ready
```

Expected:

```json
{"status":"ok","database":"reachable"}
```

Both endpoints must return HTTP 200.

If `/health` or `/ready` fails, stop the release and investigate before
deploying the frontend.

---

## Step 7 — Deploy Frontend Production

After Backend Production is healthy, deploy the frontend manually from Render.

Validate the root:

```bash
curl -I https://ori-manager-frontend-production.onrender.com/
```

Expected:

```text
HTTP 200
```

Validate SPA fallback routing:

```bash
curl -I https://ori-manager-frontend-production.onrender.com/non-existent-route
```

Expected:

```text
HTTP 200
```

---

## Step 8 — Production smoke tests

At minimum, verify:

```text
Backend /health                HTTP 200
Backend /ready                 HTTP 200
Frontend /                     HTTP 200
Frontend SPA fallback          HTTP 200
```

As functional modules are introduced, this section must also include critical
business-flow smoke tests.

A release is not considered complete until the smoke tests pass.

---

## Database rollback policy

Database rollback must not be performed automatically.

The default strategy is:

```text
forward fix
```

Do not blindly execute:

```bash
alembic downgrade
```

A downgrade is allowed only when the migration has an explicitly reviewed,
safe downgrade path and its impact on Production data is understood.

Destructive migrations require an explicit backup/export strategy before they
are executed.

The Production runtime role must never receive DDL privileges to simplify a
rollback.

---

## Application rollback policy

If the application deployment fails but the Production schema remains backward
compatible, redeploy the previous known-good Render deployment.

After rollback, validate again:

```text
/health
/ready
frontend /
critical application flows
```

If a database migration has already introduced a non-backward-compatible
schema, do not independently roll back the application.

In that situation, evaluate either:

```text
forward fix
```

or a specifically reviewed database rollback.

---

## Failure scenarios

### Migration fails before application deployment

Do not deploy the new application.

Investigate the database migration and leave the existing Production deployment
running.

### Backend deployment fails

Do not deploy the frontend release.

Restore the previous known-good backend deployment when safe.

### Backend health succeeds but readiness fails

The process is alive but database connectivity is not healthy.

Check:

```text
DATABASE_HOST
DATABASE_PORT
DATABASE_NAME
DATABASE_USER
DATABASE_PASSWORD
DATABASE_SSLMODE
Supabase availability
runtime-role permissions
```

### Frontend deployment fails

Keep the previously successful frontend deployment active and investigate the
new build independently.

---

## Post-release branch synchronization

A `develop -> main` release creates a merge commit that exists only in `main`.

To keep branch ancestry aligned for future releases, synchronize `main` back
into `develop` after a successful production release through the normal
protected-branch workflow.

The synchronization must not introduce functional changes.

---

## Release record

For each Production release, record at minimum:

```text
Release date
main commit SHA
Alembic revision
CI result
CodeQL result
Backend Render deploy
Frontend Render deploy
/health result
/ready result
Frontend smoke-test result
Operator
Relevant incidents or rollback actions
```

Do not record passwords, tokens, complete connection strings, or other secrets.

---

## Security rules

Production database administration credentials are only used for migrations
and administrative operations.

Normal FastAPI execution uses:

```text
ori_app_runtime.<production-project-ref>
```

The runtime role follows least privilege and must not receive:

```text
SUPERUSER
CREATEDB
CREATEROLE
REPLICATION
schema CREATE
DDL ownership
access to alembic_version
```

Cloud PostgreSQL connections require TLS.

Secrets are managed outside Git.

---

## Production release completion criteria

A Production release is complete only when:

```text
main contains the approved release
CI is green
CodeQL is green
Production database is at Alembic head
Backend is deployed
/health returns HTTP 200
/ready returns HTTP 200
Frontend is deployed
Frontend smoke tests return HTTP 200
No unexpected Production errors are observed
```
