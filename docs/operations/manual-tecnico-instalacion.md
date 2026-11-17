# Manual técnico e instalación desde cero — ORI Manager

**Versión documentada:** `main` al 16/11/2026, revisión de base de datos Alembic `0b2fb1bed5b2`.
**Público:** persona técnica de la ORI o de TI que va a instalar, configurar y desplegar el sistema sin conocimiento previo del proyecto.

> **Regla de este documento:** las variables de entorno se citan siempre por **nombre**, nunca por valor. Ninguna contraseña, llave ni token va en Git, en capturas, en el chat ni en este manual.

Este manual **no repite** lo que ya está documentado; lo ordena como un recorrido y enlaza al detalle:
[arquitectura](../architecture/overview.md) · [script de base de datos](base-de-datos/README.md) · [Supabase](supabase.md) · [runbook de producción](production-release.md).

---

## 1. Qué es el sistema

| Pieza | Tecnología | Carpeta |
|---|---|---|
| Interfaz web | React + Vite + TypeScript | `frontend/` |
| API | FastAPI, Python 3.13, SQLAlchemy, Alembic | `backend/` |
| Base de datos | PostgreSQL 18 (local) / Supabase PostgreSQL (nube) | — |
| Documentos | Disco local (desarrollo) o Microsoft Graph (nube) | — |
| Correo | Local, solo registro (desarrollo) o Brevo (nube) | — |
| Despliegue | Render (2 servicios) + GitHub Actions | `render.yaml`, `render.production.yaml`, `.github/workflows/` |

```text
Navegador ──► Frontend (sitio estático) ──/api/*──► Backend FastAPI ──► PostgreSQL
                       │                                   ├──► Microsoft Graph (documentos)
                       └── WebSocket directo ──────────────┴──► Brevo (correo)
```

## 2. Requisitos

| Necesita | Versión | Para qué |
|---|---|---|
| Git | cualquiera reciente | clonar el repositorio |
| Docker Desktop (con Compose) | cualquiera reciente | PostgreSQL local y DevContainer |
| VS Code + extensión Dev Containers | opcional, recomendado | entorno de desarrollo ya armado |
| Python | `3.13.17` | backend (lo gestiona `uv`) |
| uv | `0.13.5` | instalar dependencias del backend |
| Node.js | `24.22.1` | frontend |
| `psql` 18 | opcional | cargar el script SQL a mano |

Para la **nube** además: cuenta de GitHub con acceso al repositorio, cuenta de Render, proyecto de Supabase, cuenta de Brevo y una aplicación registrada en Microsoft (ver §6).

## 3. Obtener el código

```bash
git clone https://github.com/ORI-USB-CALI/ori-manager.git
cd ori-manager
```

Ramas: `develop` es Staging, `main` es Producción. Para instalar, usar `main`.

## 4. Instalación local (desarrollo o prueba)

### 4.1 Camino recomendado: DevContainer

1. Abrir Docker Desktop y esperar a que esté en marcha.
2. Abrir la carpeta en VS Code → *Reopen in Container*.
3. El DevContainer levanta PostgreSQL (servicio `db` de [`compose.yaml`](../../compose.yaml)) y ejecuta `.devcontainer/setup.sh`, que instala `uv 0.13.5`, las dependencias del backend (`uv sync --frozen`) y las del frontend (`npm ci`). Python 3.13.17 y Node 24.22.1 los trae el propio contenedor.
4. Continuar en el paso 4.3.

### 4.2 Camino alternativo: sin DevContainer

```bash
docker compose up -d db          # solo PostgreSQL 18, puerto 5432
cd backend && uv sync --frozen   # requiere Python 3.13.17 disponible para uv
cd ../frontend && npm ci
```

### 4.3 Variables de entorno del backend

```bash
cd backend
cp .env.example .env     # .env está ignorado por Git
```

Editar `backend/.env`. Para desarrollo local solo hace falta que `DATABASE_PASSWORD` coincida con `POSTGRES_PASSWORD` del servicio `db` en `compose.yaml`; el resto de valores de `.env.example` ya sirven. Si el backend corre **dentro** del DevContainer, `DATABASE_HOST` debe ser `db`; si corre en tu máquina, `localhost`.

La lista completa de variables está en la [§6](#6-variables-de-entorno-referencia-completa).

### 4.4 Crear la base de datos

Con PostgreSQL arriba y el `.env` listo, la base se crea con Alembic (la usan CI, Staging y Producción). Crea la estructura y los catálogos que la aplicación necesita (roles, etapas, tipos de convenio, países y plantilla base):

```bash
cd backend
uv run alembic upgrade head
uv run alembic current        # debe mostrar: 0b2fb1bed5b2 (head)
```

> El [script SQL de base de datos](base-de-datos/README.md) contiene solo la estructura, sin ningún dato. Sirve para revisar el modelo, **no** para instalar la aplicación: sin catálogos no se puede crear el administrador ni usar Alembic después.

### 4.5 Crear el primer administrador

La base nueva no tiene usuarios. El primer `ADMINISTRADOR_ORI` se crea por línea de comandos; pide la contraseña de forma interactiva (no queda en el historial):

```bash
cd backend
uv run python -m backend.scripts.crear_admin --correo <correo-del-admin> --nombre "<Nombre Apellido>"
```

Responde `Administrador creado: <correo>`. Si el correo ya existe como usuario interno, lo promueve. Los demás usuarios se crean desde la aplicación con ese administrador.

### 4.6 Arrancar

Backend (terminal 1):

```bash
cd backend
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (terminal 2):

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

En desarrollo, Vite reenvía `/api` a `http://localhost:8000` (se cambia con `VITE_API_PROXY_TARGET`).

### 4.7 Verificar

| Comprobación | Esperado |
|---|---|
| `http://localhost:8000/health` | `{"status":"ok"}` |
| `http://localhost:8000/ready` | `{"status":"ok","database":"reachable"}` (hay conexión a PostgreSQL) |
| `http://localhost:5173` | pantalla de inicio de sesión |
| Iniciar sesión con el administrador del paso 4.5 | entra al tablero |

En local, los documentos se guardan en `backend/var/documentos` y los correos **no se envían** (`EMAIL_PROVIDER=local`).

**Verificado el 16/11/2026** en un contenedor limpio (`python:3.13-slim`, `uv 0.13.5`, PostgreSQL 18 de `compose.yaml`): `uv sync --frozen`, `alembic upgrade head` hasta `0b2fb1bed5b2`, arranque de uvicorn con `/health` y `/ready` en `ok`, y creación del administrador con `crear_admin`.

## 5. Pruebas y calidad (opcional)

Lo mismo que ejecuta [`ci.yml`](../../.github/workflows/ci.yml):

```bash
# backend
cd backend && uv run ruff check . && uv run pytest
# frontend
cd frontend && npm run typecheck && npm test && npm run lint && npm run build
```

## 6. Variables de entorno: referencia completa

Se definen en `backend/.env` (local) o en el panel de Render (nube). **Solo se listan nombres.** `sync: false` en los `render*.yaml` significa que el valor se escribe a mano en Render.

### 6.1 Backend

| Variable | Obligatoria | Local | Nube | Descripción |
|---|---|---|---|---|
| `APP_ENV` | no | `development` | `staging` / `production` | Nombre del entorno |
| `DATABASE_HOST` | sí | `localhost` o `db` | host del *session pooler* de Supabase | Servidor PostgreSQL |
| `DATABASE_PORT` | no | `5432` | `5432` | Puerto |
| `DATABASE_NAME` | no | `ori_manager` | `postgres` | Base de datos |
| `DATABASE_USER` | no | `ori_user` | `ori_app_runtime.<project-ref>` | Usuario |
| `DATABASE_PASSWORD` | **sí, sin valor por defecto** | la de `compose.yaml` | secreto del rol de runtime | Contraseña |
| `DATABASE_SSLMODE` | no | `disable` | `require` | TLS. El valor por defecto de la app es `require` |
| `DOCUMENT_STORAGE_PROVIDER` | no | `local` | `microsoft_graph` | Dónde se guardan los documentos |
| `DOCUMENT_STORAGE_PATH` | no | `var/documentos` | — | Carpeta si el proveedor es `local` |
| `MICROSOFT_CLIENT_ID` | solo Graph | vacío | secreto | ID de la aplicación Microsoft |
| `MICROSOFT_CLIENT_SECRET` | solo Graph | vacío | secreto | Secreto de la aplicación |
| `MICROSOFT_REFRESH_TOKEN` | solo Graph | vacío | secreto | Token de renovación de la cuenta que guarda los archivos |
| `MICROSOFT_STORAGE_ROOT` | solo Graph | vacío | `staging` / `production` | Carpeta raíz dentro de la AppFolder |
| `EMAIL_PROVIDER` | no | `local` | `brevo` | `local` o `brevo`; cualquier otro valor da error |
| `BREVO_API_KEY` | solo Brevo | vacío | secreto | Llave de la API de Brevo |
| `EMAIL_FROM_ADDRESS` | solo Brevo | vacío | remitente verificado en Brevo | Correo remitente |
| `EMAIL_FROM_NAME` | no | `ORI USB Cali` | `ORI USB Cali` | Nombre del remitente |
| `PUBLIC_FRONTEND_URL` | recomendada | `http://localhost:5173` | URL pública del frontend | Se usa para armar los enlaces de los correos |

Solo en Render (no son de la aplicación): `PYTHON_VERSION=3.13.17` y `UV_VERSION=0.13.5`.

### 6.2 Frontend

| Variable | Dónde | Descripción |
|---|---|---|
| `VITE_API_URL` | `frontend/.env.development` | URL de la API en desarrollo |
| `VITE_API_PROXY_TARGET` | entorno al arrancar Vite | Destino del proxy `/api` en desarrollo (por defecto `http://localhost:8000`) |
| `VITE_WS_BACKEND_URL` | Render, sitio estático | URL pública del backend. Obligatoria en la nube: el sitio estático no puede reenviar WebSocket, el navegador se conecta directo al backend |
| `NODE_VERSION` | Render | `24.22.1` |

Las variables `VITE_*` se incrustan al **compilar**; si cambian, hay que volver a desplegar el frontend.

### 6.3 Cómo conseguir los valores externos

Estos pasos ocurren en servicios de terceros y no están automatizados en el repositorio; cada entorno (Staging y Producción) usa credenciales **distintas**.

- **Supabase:** crear el proyecto, el rol restringido `ori_app_runtime` y copiar el host del *session pooler*. Detalle de roles y permisos en [supabase.md](supabase.md#database-roles). Para migraciones se usa un usuario administrativo aparte que **nunca** se entrega a Render.
- **Brevo:** crear la cuenta, generar una llave de API y verificar el correo remitente (`EMAIL_FROM_ADDRESS`).
- **Microsoft Graph:** el código usa el endpoint de cuentas personales (`consumers`) y el permiso `Files.ReadWrite.AppFolder` con `offline_access`. Hay que registrar una aplicación en Microsoft, generar su secreto y completar una autorización con la cuenta dueña de los archivos para obtener el *refresh token*. La carpeta de la aplicación (AppFolder) de esa cuenta contiene una subcarpeta por entorno, nombrada en `MICROSOFT_STORAGE_ROOT`.

## 7. Despliegue en un servidor (Render)

El despliegue está definido como *Blueprint* en [`render.production.yaml`](../../render.production.yaml) (Producción, rama `main`) y [`render.yaml`](../../render.yaml) (Staging, rama `develop`). Crean dos servicios:

| Servicio | Tipo | Compilación | Arranque |
|---|---|---|---|
| `ori-manager-backend-production` | Web (Python), carpeta `backend` | `uv sync --frozen --no-dev` | `uv run --no-sync uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| `ori-manager-frontend-production` | Sitio estático, carpeta `frontend` | `npm ci && npm run build` → publica `dist` | — |

El frontend reenvía `/api/*` al backend y cualquier otra ruta a `/index.html` (la app es de una sola página).

### 7.1 Pasos

1. **Base de datos.** Crear el proyecto de Supabase y el rol `ori_app_runtime` ([supabase.md](supabase.md)). Cargar la estructura con **Alembic** usando el usuario administrativo (no el script SQL, porque los privilegios del rol de runtime se configuran aparte):
   ```bash
   # desde backend/, con DATABASE_* apuntando a Supabase y DATABASE_SSLMODE=require
   uv run alembic upgrade head
   ```
2. **Render.** *New → Blueprint*, apuntar al repositorio y al archivo `render.production.yaml`. Render crea los dos servicios.
3. **Variables.** En el servicio backend, escribir a mano los valores de las variables `sync: false`: `DATABASE_HOST`, `DATABASE_USER`, `DATABASE_PASSWORD`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_REFRESH_TOKEN`, `BREVO_API_KEY`, `EMAIL_FROM_ADDRESS`. Las demás ya vienen en el archivo.
4. **URLs.** Si los servicios no se llaman exactamente como en el archivo, ajustar en los `render*.yaml`: `PUBLIC_FRONTEND_URL`, el destino de la regla `/api/*` y `VITE_WS_BACKEND_URL`.
5. **Primer administrador.** Ejecutar `crear_admin` (§4.5) con `DATABASE_*` apuntando a la base de la nube, o en la *Shell* del servicio backend en Render.
6. **Verificar.**
   ```text
   GET  <url-backend>/health     → {"status":"ok"}
   GET  <url-backend>/ready      → {"status":"ok","database":"reachable"}
   GET  <url-frontend>/          → carga la aplicación
   GET  <url-frontend>/<ruta-interna>  → carga la aplicación (no 404)
   ```
   Luego iniciar sesión, subir un documento (prueba de Microsoft Graph) y provocar un correo (prueba de Brevo). Ver [las pruebas de humo del runbook](production-release.md#step-6--production-smoke-tests).

### 7.2 Despliegue automático y migraciones

- Cada push a la rama del entorno redespliega solo cuando pasan las verificaciones de CI (`autoDeployTrigger: checksPass`).
- **Render no ejecuta migraciones.** Las aplica el flujo de GitHub Actions con el *GitHub Environment* `staging` o `production` y estos secretos administrativos: `STAGING_MIGRATION_DATABASE_HOST/_USER/_PASSWORD` y `PRODUCTION_MIGRATION_DATABASE_HOST/_USER/_PASSWORD`.
- La promoción `develop` → `main`, las pruebas de humo y el *rollback* están en el [Production Release Runbook](production-release.md). Los datos reales solo existen en Staging y Producción: **no copiarlos a local ni usarlos en grabaciones o capacitaciones**.

### 7.3 Si se instala en un servidor propio (sin Render)

El proyecto no trae una receta lista para eso, pero los requisitos son los mismos: PostgreSQL 18, Python 3.13.17 con uv para correr `uvicorn backend.main:app`, y servir `frontend/dist` con un servidor web que reenvíe `/api/*` al backend, devuelva `/index.html` para el resto de rutas y permita la conexión WebSocket del navegador al backend (o configure `VITE_WS_BACKEND_URL` antes de compilar). Usar HTTPS y `DATABASE_SSLMODE=require` si la base no es local.

> El archivo `backend/Dockerfile` existente parte de Python 3.11, pero el backend exige `>=3.13`; no está en uso por el despliegue y no debe tomarse como método de instalación sin corregirlo.

## 8. Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El backend no arranca: *field required* `database_password` | Falta `DATABASE_PASSWORD` | Definirla en `backend/.env` o en Render |
| `/health` ok pero `/ready` falla | Host, usuario, contraseña o TLS incorrectos | Revisar `DATABASE_*`; en la nube `DATABASE_SSLMODE=require` |
| `uv` dice que no encuentra Python 3.13.17 | `uv` antiguo o sin salida a internet | Actualizar `uv` a 0.13.5 o usar el DevContainer |
| `crear_admin`: *No existe ADMINISTRADOR_ORI* | Base sin migrar ni catálogos cargados | Ejecutar §4.4 primero |
| `alembic upgrade head` falla con *relation already exists* | Se cargó el script SQL de estructura (queda sin `alembic_version` ni catálogos) | Recrear la base vacía y usar `alembic upgrade head` |
| No llegan correos | `EMAIL_PROVIDER=local`, llave Brevo inválida o remitente no verificado | [Failure scenarios del runbook](production-release.md#transactional-email-fails) |
| Fallan los documentos en la nube | Credenciales o `MICROSOFT_STORAGE_ROOT` incorrectos | [Failure scenarios del runbook](production-release.md#document-storage-fails) |
| Las notificaciones en tiempo real no llegan en la nube | Falta `VITE_WS_BACKEND_URL` al compilar | Definirla y volver a desplegar el frontend |
| Pantalla en blanco al recargar una ruta | Falta la regla `/*` → `/index.html` | Revisar las `routes` del frontend |

## 9. Seguridad

- Ningún secreto en Git. `backend/.env` está ignorado; las llaves de la nube viven solo en Render y en GitHub Secrets.
- La contraseña de desarrollo que aparece en `compose.yaml` es solo para la base local; **no reutilizarla** en ningún otro entorno.
- El backend en la nube usa un rol restringido; las migraciones, un usuario administrativo separado.
- Si un secreto se expuso, rotarlo en el proveedor (Supabase, Brevo, Microsoft) y actualizarlo en Render y GitHub.
