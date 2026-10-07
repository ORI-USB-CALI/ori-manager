# Production Release Runbook — ORI Manager

## Purpose

This document defines the controlled process for promoting ORI Manager from
Staging to Production.

Production releases are explicitly authorized through a Pull Request from
`develop` to `main`.

After an approved release is merged into `main`, validation, Production
database migration and application deployment are automated through GitHub
Actions and Render.

The release pipeline is designed so that a failed validation or failed database
migration prevents the new application revision from being deployed.

The current Production release flow is:

```text
develop
   |
   | Pull Request
   v
main
   |
   +--------------------+
   |                    |
   v                    v
GitHub Actions CI     CodeQL
   |
   +--> Backend CI
   |
   +--> Frontend CI
   |
   v
Production DB Migrations
   |
   +--> Supabase Production
   |
   v
GitHub checks successful
   |
   v
Render Production
   |
   +--> Backend
   |
   +--> Frontend
   |
   v
Production smoke tests
```

At runtime, the Production backend connects to Supabase PostgreSQL using a
restricted application role.

Staging and Production use independent Supabase projects, credentials,
document-storage roots and application configuration.

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

A Production release follows:

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

The merge of an approved `develop -> main` Pull Request represents the explicit
authorization to begin a Production release.

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

Staging is used to validate application behavior, database migrations and
integrations before a Production release.

Staging Render services use:

```text
Backend Auto-Deploy: After CI Checks Pass
Frontend Auto-Deploy: After CI Checks Pass
```

Staging database migrations are executed by GitHub Actions after Backend CI and
Frontend CI succeed on a push to `develop`.

### Production

Source branch:

```text
main
```

Render configuration:

```text
render.production.yaml
```

Production uses controlled CI-gated deployment settings:

```text
Blueprint Auto Sync: OFF
Backend Auto-Deploy: After CI Checks Pass
Frontend Auto-Deploy: After CI Checks Pass
```

A Production release still requires explicit authorization from the technical
team through the `develop -> main` Pull Request.

After that Pull Request is approved and merged, the normal application
deployment is automated.

Render deploys the `main` revision only after its associated GitHub checks
complete successfully.

---

## Production release prerequisites

Before promoting `develop` to `main`, confirm:

- Staging is operational.
- The intended Sprint or release increment has been validated in Staging.
- Backend CI passes.
- Frontend CI passes.
- CodeQL passes.
- Required code-owner review is complete.
- All database migrations included in the release have been reviewed.
- The GitHub Environment `production` exists.
- Production migration secrets are configured in the `production` Environment.
- Production database connectivity is available.
- Production Render services use `After CI Checks Pass`.
- Production Render runtime secrets are configured.
- Brevo transactional email configuration is available.
- Microsoft Graph document-storage configuration is available.
- Production uses `MICROSOFT_STORAGE_ROOT=production`.
- Staging and Production do not share document-storage roots.
- Production runtime database credentials remain separate from migration
  credentials.

Do not release while any required validation is failing.

The Production database migration Environment requires:

```text
PRODUCTION_MIGRATION_DATABASE_HOST
PRODUCTION_MIGRATION_DATABASE_USER
PRODUCTION_MIGRATION_DATABASE_PASSWORD
```

The migration credential must be an administrative/migration credential.

It must not be the restricted FastAPI runtime role.

Production backend runtime configuration includes, at minimum:

```text
APP_ENV=production

DATABASE_HOST
DATABASE_PORT=5432
DATABASE_NAME=postgres
DATABASE_USER
DATABASE_PASSWORD
DATABASE_SSLMODE=require

DOCUMENT_STORAGE_PROVIDER=microsoft_graph
MICROSOFT_CLIENT_ID
MICROSOFT_CLIENT_SECRET
MICROSOFT_REFRESH_TOKEN
MICROSOFT_STORAGE_ROOT=production

EMAIL_PROVIDER=brevo
BREVO_API_KEY
EMAIL_FROM_ADDRESS
EMAIL_FROM_NAME
PUBLIC_FRONTEND_URL
```

Secret values must remain outside the repository.

---

## Step 1 — Promote develop to main

Create a Pull Request:

```text
base: main
compare: develop
```

Review the complete release scope.

Confirm that the PR represents only the intended Production increment.

Wait for the required checks and approvals.

Merge using:

```text
Create a merge commit
```

Do not use `Squash and merge` for the `develop -> main` Production promotion.

Merging the Pull Request is the explicit authorization to begin the Production
release pipeline.

No separate manual application deployment from Render is required during the
normal release process.

After the merge, record the resulting `main` commit SHA.

---

## Step 2 — Automated CI validation

After the merge creates a new commit on `main`, GitHub Actions validates the
Production revision.

The following application checks execute before the Production database
migration:

```text
Backend CI
Frontend CI
```

Backend CI validates:

```text
dependency installation
dependency lock
Ruff
Alembic migrations against an isolated PostgreSQL instance
backend tests
```

Frontend CI validates:

```text
dependency installation
TypeScript
ESLint
production build
```

CodeQL also analyzes the Production revision through its independent security
workflow.

A release must not be considered successful while any required validation is
failing.

---

## Step 3 — Automated Production database migration

After Backend CI and Frontend CI succeed on the `main` push, GitHub Actions
runs:

```text
Production DB Migrations
```

The job uses the GitHub Environment:

```text
production
```

and its Production administrative migration credentials.

The FastAPI runtime credential `ori_app_runtime` is not used for migrations.

Production cloud database connections use:

```text
Supabase Shared Session Pooler
Port: 5432
Database: postgres
SSL mode: require
```

Before changing the schema, the job verifies the target and current Alembic
revisions.

The migration sequence is:

```bash
uv run --no-sync alembic heads
uv run --no-sync alembic current
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
```

The final Production revision must match the current Alembic head.

If the migration fails:

```text
STOP THE RELEASE
```

The migration failure must be understood and corrected before the new
Production application revision is deployed.

Do not perform manual schema modifications through the Supabase Table Editor as
a substitute for an Alembic migration.

Do not mark migrations as applied manually unless a specifically reviewed
recovery procedure requires it.

---

## Step 4 — Automatic Render deployment

Production Render services track:

```text
main
```

and use:

```text
Auto Deploy: After CI Checks Pass
```

The Production services are:

```text
ori-manager-backend-production
ori-manager-frontend-production
```

Render deploys the approved `main` revision only after the associated GitHub
checks complete successfully.

The backend deployment uses:

```text
rootDir: backend
buildCommand: uv sync --frozen --no-dev
startCommand: uv run --no-sync uvicorn backend.main:app --host 0.0.0.0 --port $PORT
healthCheckPath: /health
```

The frontend deployment uses:

```text
rootDir: frontend
buildCommand: npm ci && npm run build
staticPublishPath: dist
```

A manual Render deployment is not part of the normal release process.

Manual deploy, redeploy or rollback actions are reserved for exceptional
operational recovery.

---

## Step 5 — Synchronize Render infrastructure when required

The Production Blueprint is:

```text
render.production.yaml
```

Blueprint Auto Sync is disabled.

A Blueprint sync is only necessary when Production infrastructure
configuration has changed.

Examples include changes to:

```text
environment-variable declarations
runtime configuration
build commands
start commands
routing rules
health-check configuration
Auto-Deploy policy
service configuration
```

Before synchronizing the Blueprint, review the Render change plan.

Existing Production resources must be associated rather than duplicated:

```text
ori-manager-backend-production
ori-manager-frontend-production
```

Do not create duplicate Production services.

Infrastructure synchronization is not required for ordinary application-code
releases when the existing Render service configuration already matches the
versioned Blueprint.

When new `sync: false` environment variables are introduced in the Blueprint,
their secret values must be configured in Render before the application depends
on them.

---

## Step 6 — Production smoke tests

After Render reports the Production deployments as successful, verify the
runtime.

At minimum:

```text
Backend /health                HTTP 200
Backend /ready                 HTTP 200
Frontend /                     HTTP 200
Frontend SPA fallback          HTTP 200
```

### Backend health

Run:

```bash
curl -i https://ori-manager-backend-production.onrender.com/health
```

Expected:

```json
{"status":"ok"}
```

The endpoint must return HTTP 200.

### Backend database readiness

Run:

```bash
curl -i https://ori-manager-backend-production.onrender.com/ready
```

Expected:

```json
{"status":"ok","database":"reachable"}
```

The endpoint must return HTTP 200.

A successful `/health` with a failed `/ready` means the application process is
alive but its database dependency is not ready.

### Frontend root

Run:

```bash
curl -I https://ori-manager-frontend-production.onrender.com/
```

Expected:

```text
HTTP 200
```

### Frontend SPA fallback

Run:

```bash
curl -I https://ori-manager-frontend-production.onrender.com/non-existent-route
```

Expected:

```text
HTTP 200
```

### Functional smoke test

At least one critical business flow affected by the release must also be
validated when applicable.

The functional smoke test should be intentionally smaller than the complete CI
or E2E suite and should verify that the deployed application, Production
database and external integrations work together.

For a release that changes authentication, transactional email, document
storage or the agreement workflow, the smoke test should include the affected
integration when it can be performed safely without corrupting Production
data.

A release is not considered complete until its smoke tests pass.

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

Destructive or non-backward-compatible migrations require an explicit
backup/export and recovery strategy before execution.

The Production runtime role must never receive DDL privileges to simplify a
rollback.

If a database migration succeeds but the application deployment later fails,
first determine whether the migrated schema remains compatible with the
previous application revision.

Do not automatically downgrade the database merely because an application
deployment failed.

---

## Application rollback policy

If an application deployment fails but the Production schema remains backward
compatible, restore or redeploy the previous known-good Render deployment when
safe.

After rollback, validate again:

```text
/health
/ready
frontend /
frontend SPA fallback
critical application flows
```

If a database migration has already introduced a non-backward-compatible
schema, do not independently roll back the application to a revision that
cannot operate safely against the new schema.

In that situation, evaluate either:

```text
forward fix
```

or a specifically reviewed database rollback/recovery procedure.

---

## Failure scenarios

### CI validation fails

Do not consider the Production release authorized for deployment.

Correct the failure through the normal Git workflow.

Do not bypass failed validation by manually deploying the affected revision.

### Production migration configuration is missing

The `Production DB Migrations` job must fail before attempting the schema
change.

Verify the GitHub Environment:

```text
production
```

and the required migration secrets.

Do not replace the missing migration credential with the FastAPI runtime
credential.

### Migration fails before application deployment

Treat the Production release as failed.

Investigate the database migration and leave the previous known-good
application deployment running.

Determine the actual Production schema state before retrying.

Do not manually alter the schema merely to make the CI job appear successful.

### Backend deployment fails

Treat the Production release as failed.

Do not consider the release complete even if the frontend deployment succeeds.

Investigate the failed backend deployment and restore the previous known-good
backend deployment when safe.

After recovery, validate:

```text
/health
/ready
critical application flows
```

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
Production database state
```

Do not consider the release successful while `/ready` fails.

### Frontend deployment fails

Treat the Production release as failed.

Keep or restore the previously successful frontend deployment and investigate
the failed build or deployment independently.

Do not consider the release complete until the frontend smoke tests pass.

### Transactional email fails

Check:

```text
EMAIL_PROVIDER
BREVO_API_KEY
EMAIL_FROM_ADDRESS
EMAIL_FROM_NAME
PUBLIC_FRONTEND_URL
Brevo availability
```

Do not expose API keys or temporary credential tokens in logs or incident
records.

### Document storage fails

Check:

```text
DOCUMENT_STORAGE_PROVIDER
MICROSOFT_CLIENT_ID
MICROSOFT_CLIENT_SECRET
MICROSOFT_REFRESH_TOKEN
MICROSOFT_STORAGE_ROOT
Microsoft Graph availability
```

Production must use:

```text
MICROSOFT_STORAGE_ROOT=production
```

Do not switch Production to local filesystem storage as an operational
workaround.

---

## Post-release branch synchronization

A `develop -> main` release creates a merge commit that exists only in `main`.

To keep branch ancestry aligned for future releases, synchronize `main` back
into `develop` after a successful Production release through the normal
protected-branch workflow.

The synchronization must not introduce functional changes.

The intended result is:

```text
main release merge commit
        |
        v
synchronization PR
        |
        v
develop
```

Do not manually rewrite branch history to align `main` and `develop`.

---

## Release record

For each Production release, record at minimum:

```text
Release date
Sprint or release identifier
main commit SHA
Alembic revision
Backend CI result
Frontend CI result
CodeQL result
Production DB Migrations result
Backend Render deploy
Frontend Render deploy
/health result
/ready result
Frontend root result
Frontend SPA fallback result
Critical functional smoke-test result
Operator
Relevant incidents
Rollback or recovery actions, if any
```

Do not record:

```text
database passwords
API keys
OAuth secrets
refresh tokens
complete credential-bearing connection strings
temporary authentication tokens
```

---

## Security rules

Production database administrative credentials are used only for migrations
and administrative operations.

Normal FastAPI execution uses the restricted Production runtime role:

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

The migration credential and runtime credential must remain separate.

Cloud PostgreSQL connections require TLS:

```text
DATABASE_SSLMODE=require
```

Secrets are managed outside Git.

Render secrets must not be copied into:

```text
render.yaml
render.production.yaml
backend/.env.example
application source code
documentation
```

GitHub Production migration secrets must be stored in the:

```text
production
```

Environment rather than committed to the repository.

Microsoft Graph credentials and Brevo credentials must be treated as secrets.

The Production document-storage root must remain isolated from Staging.

---

## Production release completion criteria

A Production release is complete only when:

```text
main contains the approved release
Backend CI is green
Frontend CI is green
CodeQL is green
Production DB Migrations is green
Production database is at Alembic head
Backend Render deployment is successful
Frontend Render deployment is successful
/health returns HTTP 200
/ready returns HTTP 200
Frontend root returns HTTP 200
Frontend SPA fallback returns HTTP 200
Critical release smoke test passes
No unexpected Production errors are observed
```

If any required condition is not satisfied, the release remains incomplete.