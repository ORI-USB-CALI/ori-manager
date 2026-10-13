# ORI Manager — Gestión y trazabilidad de convenios

Aplicación desarrollada para la Oficina de Relaciones Internacionales de la Universidad de San Buenaventura Cali.

> **Corte documental:** 13/10/2026. Los Sprints 1 y 2 están cerrados según el backlog de historias de usuario; el Sprint 3 está en curso. La presencia de funcionalidades en `develop` no significa que hayan sido aprobadas ni liberadas en producción.

## Documentación

- [Centro documental](docs/README.md), [arquitectura](docs/architecture/overview.md) y [política de documentación por commit](docs/development/documentation-policy.md).
- [Estado de las historias de usuario](docs/product/estado-hu-2026-10-13.md), [Sprint 1](docs/sprints/sprint-01.md), [Sprint 2](docs/sprints/sprint-02.md) y [Sprint 3](docs/sprints/sprint-03.md).
- [Manuales operativos](docs/operations/README.md), [runbook de producción](docs/operations/production-release.md) y [base de datos Supabase](docs/operations/supabase.md).
- [Inicio propuesto para GitHub Wiki](docs/wiki/Home.md); [Gestión de Releases en Drive](https://drive.google.com/drive/folders/1TwlYItxGI0bYmJ6nxw6Ggk0Sbc08cRdb); [evidencias QA](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j).

## Tecnologías

- Frontend: React, Vite y TypeScript.
- Backend: FastAPI, Python 3.13, uv, SQLAlchemy, Psycopg y Alembic.
- PostgreSQL 18 para desarrollo/CI; Supabase PostgreSQL para staging y producción.
- Render y GitHub Actions para despliegue; Microsoft Graph para documentos y Brevo para correo transaccional en cloud.

## Roles

Los códigos de rol autenticado en `backend/src/backend/core/roles.py` son `ADMINISTRADOR_ORI`, `GESTOR_ORI`, `REVISOR_ORI`, `SOLICITANTE_INTERNO` y `SOLICITANTE_EXTERNO`. Los permisos efectivos están definidos en `backend/src/backend/core/permisos.py`.

La anterior descripción de «tres roles» en este README era un alcance inicial desactualizado. La historia **HU-08 — Directorio público** está marcada `Sin iniciar` en el backlog; no debe confundirse con **HU-08 — Gestión de credenciales**, marcada `Terminado`.

## Trabajo y validación

- Desarrollo local con DevContainer y `compose.yaml`; valores sensibles en `.env` privado, nunca en Git.
- Pruebas backend y frontend, lint y build según `.github/workflows/ci.yml`.
- Cambios funcionales mediante ramas `feature/*`, `fix/*` o `chore/*` hacia `develop`; documentación mediante `docs/*` también hacia `develop`.
- Promoción `develop` → `main` exclusivamente mediante PR de release. Consultar el [runbook](docs/operations/production-release.md).

**Cada commit funcional nuevo debe actualizar en el mismo commit la documentación impactada**, o justificar expresamente por qué no aplica. [Política](docs/development/documentation-policy.md).

La fuente de estados y prioridades es el backlog validado por los PO; el código y las pruebas describen la implementación, pero no sustituyen la aceptación de las HU.
