# Arquitectura y contratos generales

**Corte:** `develop` consultado el 13/10/2026. Este documento describe la estructura observada, no prueba disponibilidad de proveedores en producción.

## Componentes

```text
React / Vite / TypeScript
          | HTTPS /api
          v
       FastAPI
          |  routers + permisos
          |  servicios de negocio / SQLAlchemy
          |  documentos: local (dev) o Microsoft Graph (cloud)
          |  correo: local (dev) o Brevo (cloud)
          |  Alembic para cambios de esquema (job separado)
          v
PostgreSQL Docker (dev/CI) o Supabase (cloud)
```

Las rutas `backend/src/backend/api/routers/` incluyen `auth`, `usuarios`, `aliados`, `convenios`, `solicitudes`, `notificaciones` y los flujos públicos de contraparte y firmas. La UI está organizada en `frontend/src/pages/` y rutas con protección por permisos en `frontend/src/app/router.tsx`.

## Accesos y autorizaciones

| Código de rol (`backend/core/roles.py`) | Ámbito general |
|---|---|
| `ADMINISTRADOR_ORI` | Administración y gestión ORI según permisos |
| `GESTOR_ORI` | Operación y seguimiento de convenios/solicitudes según permisos |
| `REVISOR_ORI` | Revisión y aval jurídico |
| `SOLICITANTE_INTERNO` | Operaciones sobre solicitudes propias y las respuestas autorizadas |
| `SOLICITANTE_EXTERNO` | Operaciones sobre solicitudes propias y las respuestas autorizadas |

La matriz exacta está en `backend/src/backend/core/permisos.py`; **no** deducir privilegios por el nombre del rol ni confiar solo en controles visuales. La funcionalidad de invitado/directorio público se planifica aparte en HU-08 (directorio público, `Sin iniciar`).

## Entornos y despliegue

| Entorno | Rama | DB | Documentos |
|---|---|---|---|
| Development | Rama de trabajo | Docker PostgreSQL | Adaptador local |
| CI | PR/push | DB efímera | Dobles de prueba |
| Staging | `develop` | Supabase staging | Root `staging` en Microsoft Graph |
| Production | `main` | Supabase production | Root `production` en Microsoft Graph |

`/health` verifica que vive el proceso; `/ready` verifica conexión PostgreSQL. Ninguno reemplaza una prueba funcional completa. Supabase se consulta mediante FastAPI y PostgreSQL/TLS, no desde React.

## Relación con el backlog

Sprint 1: autenticación, roles, usuarios, aliados y convenio base. Sprint 2: solicitudes, elaboración, jurídica, contraparte, firmas y tablero. Sprint 3: HU y HT en diferentes estados de avance según backlog. **Archivo de convenio (HU-16)** sigue `Sin iniciar` (Sprint 5), y está expresamente fuera de R1.

Fuentes: `compose.yaml`, `render.yaml`, `render.production.yaml`, `.github/workflows/ci.yml`, `backend/src/backend/core/roles.py`, `backend/src/backend/core/permisos.py` y [operaciones](../operations/README.md).
