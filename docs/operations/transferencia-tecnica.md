# Transferencia técnica a la ORI

**Propósito:** dejar registrado qué se entrega a la ORI, qué debe revisarse antes de transferir los derechos del repositorio y cómo comprobar, después, que la ORI tiene control real del código y de los servicios.
**Estado:** plantilla de verificación para el cierre del Sprint 5. Este archivo no se edita en cada paso: el seguimiento (fecha, responsable y decisiones tomadas, como visibilidad, licencia u opción de transferencia) se registra en la carpeta de [Gestión de releases](https://drive.google.com/drive/folders/1TwlYItxGI0bYmJ6nxw6Ggk0Sbc08cRdb) en Drive. Solo se hace un PR adicional si cambia un archivo del repositorio (por ejemplo `LICENSE` o `CODEOWNERS`).
**Fuente base de los hallazgos:** estado de los archivos de `main` en el commit `00ede0f` (17/11/2026), equivalente al de `develop` antes de los PR documentales del 19/11/2026. Las ramas tenían historiales de integración distintos.

> **Regla:** este documento no contiene credenciales y nunca debe contenerlas. Las variables se citan por **nombre**; sus valores se entregan por un canal seguro fuera de Git, de la wiki y del chat.

Detalle técnico que **no se repite aquí**: [Manual técnico e instalación](manual-tecnico-instalacion.md) · [Script de base de datos](base-de-datos/README.md) · [Arquitectura](../architecture/overview.md) · [Supabase](supabase.md) · [Runbook de producción](production-release.md).

---

## 1. Qué se entrega

| Entregable | Dónde está | Responsable de revisarlo |
|---|---|---|
| Código fuente completo (frontend y backend) | Repositorio `ORI-USB-CALI/ori-manager`, ramas `main` y `develop` | Líder Técnico |
| Script de base de datos (estructura, sin datos) | [`docs/operations/base-de-datos/`](base-de-datos/README.md) | DBA |
| Manual técnico e instalación desde cero | [`manual-tecnico-instalacion.md`](manual-tecnico-instalacion.md) | Equipo de documentación |
| Manual de usuario | [`docs/manual-usuario.md`](../manual-usuario.md) | Equipo de documentación |
| Video tutorial (15 min) | Enlace en la [wiki](https://github.com/ORI-USB-CALI/ori-manager/wiki) | Equipo de documentación |
| Wiki de GitHub | Repositorio asociado `ori-manager.wiki` (viaja con el repositorio) | Equipo de documentación |
| Pipeline de integración y análisis | [`.github/workflows/`](../../.github/workflows/) (`ci.yml`, `codeql.yml`) | Líder Técnico |
| Configuración de despliegue | [`render.yaml`](../../render.yaml) (Staging) y [`render.production.yaml`](../../render.production.yaml) (Producción) | Líder Técnico |

**Fuera del alcance de la entrega** (acta de inicio): migración de datos históricos y despliegue institucional, que corresponden a la ORI y a TI; el soporte posterior se limita a bugs críticos reportados dentro de los 7 días hábiles siguientes a la entrega final.

## 2. Servicios externos que hay que traspasar

El repositorio solo contiene la **configuración**. Las cuentas y los secretos viven en cada proveedor y no se transfieren con el repositorio.

| Servicio | Para qué se usa | Variables (solo nombres) | Qué hay que hacer |
|---|---|---|---|
| **GitHub** | Código, CI, CodeQL, wiki, issues | Secrets de Actions (si existen; revisar en *Settings → Secrets and variables*) | Dar propiedad a la ORI (§4) |
| **Render** | Hospeda backend y frontend, Staging y Producción | `PYTHON_VERSION`, `UV_VERSION`, `NODE_VERSION`, `VITE_WS_BACKEND_URL` y todas las del backend | La ORI crea su cuenta/equipo y recrea o recibe los servicios; cargar las variables |
| **Supabase** | PostgreSQL en la nube | `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_SSLMODE` | Proyecto de la ORI; roles de migración y de ejecución como indica [Supabase](supabase.md) |
| **Microsoft Graph** | Almacenamiento de documentos en la nube | `DOCUMENT_STORAGE_PROVIDER`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_REFRESH_TOKEN`, `MICROSOFT_STORAGE_ROOT` | La ORI registra su propia aplicación y almacén; el equipo no entrega su token |
| **Brevo** | Correo transaccional | `EMAIL_PROVIDER`, `BREVO_API_KEY`, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`, `PUBLIC_FRONTEND_URL` | La ORI crea su cuenta y verifica su remitente |

**Principio:** la ORI debe terminar con **credenciales propias**. Las que usó el equipo durante el proyecto se **rotan o se revocan** al cerrar, porque quedaron en equipos y servicios personales.

## 3. Verificaciones antes de transferir

### 3.1 Secretos en el código y en el historial

Revisión del 17/11/2026 sobre **todas las ramas y todo el historial** del repositorio, buscando por patrones (llaves de GitHub, AWS y Brevo, llaves privadas, JWT, cadenas de conexión de Supabase con contraseña, archivos `.env` versionados y variables de Microsoft/Brevo con valor asignado):

- **Hallazgos: ninguno** de tipo secreto real. Los únicos archivos de entorno que alguna vez estuvieron versionados son las plantillas `backend/.env.example` y `frontend/.env.development`.
- Solo aparece la contraseña de **desarrollo local** `ori_dev_password` en `compose.yaml` y `backend/.env.example`. Es un valor de contenedor local, sin acceso a ningún servicio; aun así, **no debe reutilizarse en ningún entorno de la nube**.
- `backend/alembic.ini` trae `sqlalchemy.url = postgresql+psycopg://unused`, que es un marcador sin credenciales.

**Limitación:** es una búsqueda por patrones, no sustituye una herramienta dedicada. Antes de entregar, repetirla con `gitleaks` o activar *Secret scanning* de GitHub y dejar la evidencia.

```bash
# Ejemplo (instalar gitleaks aparte). Revisar el resultado, no pegarlo en canales públicos.
gitleaks detect --source . --log-opts="--all" --redact
```

- [ ] Escaneo con herramienta dedicada ejecutado: ____/____/2026, por: ________
- [ ] Sin hallazgos, o hallazgos rotados y documentados

### 3.2 Evidencias y capturas en `docs/`

`docs/evidencia/` contiene 40 archivos (capturas y correos de ejemplo, ~2 MB). Los correos de ejemplo usan el dominio ficticio `ori.example.invalid` y un token `FICTICIO`. Falta confirmar que **ninguna captura muestre datos reales** (correos, nombres, documentos), porque los datos reales están en Staging.

- [ ] Capturas revisadas una por una

### 3.3 La base de datos entregada debe coincidir con el último código

El script SQL representa una foto del esquema en la revisión de Alembic usada para generarlo. El **19/11/2026**, el PR **#204** actualizó el script de [`base-de-datos/`](base-de-datos/README.md) al head **`3816fbbdff1a`**, incorporando las columnas correspondientes a HT-17 (`c17a20261115`) y HT-15 (`3816fbbdff1a`). El volcado contiene **solo estructura, sin datos**, y no sustituye la creación de una base funcional mediante Alembic.

Antes de entregar, **verificar que la revisión documentada coincide con el head vigente**. Si entra otra migración, regenerar el script SQL y actualizar el README de la base de datos y el [manual técnico](manual-tecnico-instalacion.md).

- [ ] `uv run alembic heads` en la rama de entrega = revisión escrita en el README de la base de datos
- [ ] Script SQL regenerado si el head cambió

### 3.4 Versión de entrega

- [ ] Crear un tag o *release* en `main` después del merge final (por ejemplo `v1.0.0`), para que la ORI sepa exactamente qué versión recibió.
- [ ] El manual de usuario, el video y el script de BD citan esa misma versión.

### 3.5 Piezas del repositorio que dependen de la organización actual

- **`.github/CODEOWNERS`** apunta a `@ORI-USB-CALI/tech-leads`, un equipo de la organización actual. Si el repositorio pasa a otra organización, ese equipo deja de existir y las reglas de revisión obligatoria pueden quedar sin revisores. Cambiarlo por el equipo o las personas de la ORI.
- **Protección de ramas** (`main`, `develop`): confirmar, después de transferir, que siguen vigentes las revisiones obligatorias, los checks `Backend CI`, `Frontend CI` y `CodeQL`, y la prohibición de push directo.
- **Secrets de GitHub Actions:** no se transfieren con el repositorio (§2).

### 3.6 Visibilidad y licencia

- El repositorio es hoy **público**. El acta de inicio habla de un repositorio **privado** como entregable. Confirmar con el Product Owner y la ORI cuál es la decisión antes de transferir; cambiar la visibilidad requiere permisos de administrador y no deshace copias ya clonadas.
- **No existe archivo `LICENSE`.** La definición de propiedad y uso del código corresponde a la Universidad; decidirla y registrarla.

- [ ] Visibilidad confirmada: público / privado
- [ ] Licencia o declaración de propiedad definida

## 4. Transferir los derechos sobre el repositorio

Hay dos caminos. **Elegir uno con el Product Owner y la ORI.**

| Opción | Cuándo conviene | Cómo |
|---|---|---|
| **A. Transferir el repositorio a la organización o cuenta de la ORI** | La ORI tiene su organización en GitHub | *Settings → General → Danger Zone → Transfer ownership*. Lo ejecuta un *Owner* del repositorio y se necesita un *Owner* en el destino. GitHub redirige las URL antiguas; la wiki, los issues y los PR viajan con el repositorio. |
| **B. Mantenerlo en `ORI-USB-CALI` y dar rol Owner/Admin a personas de la ORI** | La ORI no tiene organización todavía | *Organization → People* (rol *Owner*) y *Repository → Settings → Collaborators* (rol *Admin*). |

Quién ejecuta el paso: quien tenga rol *Owner* de la organización (**confirmar con el Líder Técnico**).

## 5. Verificación posterior (hecha con la ORI presente)

- [ ] Una persona de la ORI clona el repositorio con su propia cuenta.
- [ ] Puede abrir un *pull request* y ver los checks de Actions.
- [ ] Puede abrir la wiki y los enlaces funcionan.
- [ ] Ejecuta el [manual técnico](manual-tecnico-instalacion.md) en un equipo limpio y llega a `/health` y `/ready` correctos.
- [ ] La ORI accede con cuentas propias a Render, Supabase, Microsoft y Brevo.
- [ ] Las credenciales del equipo están rotadas o revocadas.
- [ ] Se deja registro de la entrega (fecha, quién recibió, versión) en la carpeta de [Gestión de releases](https://drive.google.com/drive/folders/1TwlYItxGI0bYmJ6nxw6Ggk0Sbc08cRdb).

## 6. Inconsistencias menores detectadas durante la revisión

No bloquean la entrega, pero conviene corregirlas o dejarlas anotadas:

- `backend/.env.example` trae `DATABASE_HOST=localhost`; dentro del DevContainer debe ser `db`. El manual técnico ya lo explica.
- `frontend/.env.development` define `VITE_API_URL`, pero el código del frontend no la usa. Las variables que sí se leen son `VITE_API_PROXY_TARGET` y `VITE_WS_BACKEND_URL`.
- `backend/README.md` estaba vacío y `frontend/README.md` era la plantilla de Vite; esta entrega los reemplaza.
- `docs/wiki/Home.md` decía «pendiente de publicar» y listaba solo hasta el Sprint 3; esta entrega lo actualiza.
