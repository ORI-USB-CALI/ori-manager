# Backend — ORI Manager

API REST de ORI Manager (gestión y trazabilidad de convenios de la ORI, Universidad de San Buenaventura Cali).

**Stack:** Python 3.13 · FastAPI · SQLAlchemy 2 · Alembic · Psycopg 3 · PostgreSQL · gestor de paquetes `uv`.

> La instalación completa, el despliegue y la lista detallada de variables están en el [Manual técnico e instalación](../docs/operations/manual-tecnico-instalacion.md). Este archivo es solo una guía rápida.

## Estructura

```text
backend/
├── src/backend/
│   ├── main.py        # aplicación FastAPI y endpoints /health y /ready
│   ├── api/routers/   # rutas HTTP
│   ├── services/      # lógica de negocio
│   ├── models/        # modelos SQLAlchemy
│   ├── schemas/       # esquemas Pydantic
│   ├── core/          # configuración, roles y permisos
│   ├── db/            # sesión y base declarativa
│   ├── cli/           # comandos de línea
│   └── scripts/       # utilidades operativas
├── migrations/        # migraciones de Alembic (fuente de verdad del esquema)
├── tests/             # pruebas con pytest
├── .env.example       # plantilla de variables (sin secretos)
└── pyproject.toml / uv.lock
```

Roles y permisos: `src/backend/core/roles.py` y `src/backend/core/permisos.py`.

## Puesta en marcha local

Se recomienda trabajar dentro del DevContainer (ver [guía de instalación del entorno](https://github.com/ORI-USB-CALI/ori-manager/wiki/Instalación-del-entorno-de-desarrollo)). Con PostgreSQL local arriba (`docker compose up -d db` desde la raíz):

```bash
cd backend
uv sync --frozen
cp .env.example .env            # .env no se sube a Git
uv run alembic upgrade head     # crea el esquema y los catálogos
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Dentro del DevContainer `DATABASE_HOST` debe ser `db`; en tu máquina, `localhost`.

Comprobación: `GET /health` (el proceso vive) y `GET /ready` (hay conexión a PostgreSQL).

## Validaciones antes de un PR

```bash
uv sync --frozen
uv lock --check
uv run ruff check .
uv run alembic upgrade head     # solo contra la base local
uv run pytest
```

## Variables de entorno

Solo nombres; los valores van en `.env` (local) o en el panel del proveedor (nube). **Nunca** en Git.

| Grupo | Variables |
|---|---|
| Aplicación | `APP_ENV`, `PUBLIC_FRONTEND_URL` |
| Base de datos | `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD` *(secreto)*, `DATABASE_SSLMODE` |
| Documentos | `DOCUMENT_STORAGE_PROVIDER` (`local` o Microsoft), `DOCUMENT_STORAGE_PATH`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` *(secreto)*, `MICROSOFT_REFRESH_TOKEN` *(secreto)*, `MICROSOFT_STORAGE_ROOT` |
| Correo | `EMAIL_PROVIDER` (`local` o Brevo), `BREVO_API_KEY` *(secreto)*, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME` |

## Cambios de base de datos

El esquema solo cambia mediante **migraciones de Alembic**; no se modifica a mano en Supabase. Ver [Supabase](../docs/operations/supabase.md) y la [política de documentación](../docs/development/documentation-policy.md).
