# Frontend — ORI Manager

Interfaz web de ORI Manager (gestión y trazabilidad de convenios de la ORI, Universidad de San Buenaventura Cali).

**Stack:** React 19 · TypeScript · Vite · React Router · TanStack Query · Vitest. Gestor de paquetes: `npm` con `package-lock.json`.

> La instalación completa y el despliegue están en el [Manual técnico e instalación](../docs/operations/manual-tecnico-instalacion.md). El uso de la plataforma, en el [Manual de usuario](../docs/manual-usuario.md).

## Estructura

```text
frontend/src/
├── app/          # rutas (router.tsx), navegación, cliente de consultas, layout
├── pages/        # pantallas
├── components/   # componentes reutilizables
├── auth/         # sesión y control de acceso por permiso (RequierePermiso)
├── security/     # utilidades de seguridad
└── assets/       # estilos y variables
```

Las rutas protegidas se declaran en `src/app/router.tsx` con el permiso que exige cada una. Algunas pantallas son públicas y se abren con un enlace individual con token (revisión de la contraparte y firma del convenio).

## Puesta en marcha local

Requiere el backend en `http://localhost:8000` (ver [README del backend](../backend/README.md)).

```bash
cd frontend
npm ci
npm run dev -- --host 0.0.0.0     # http://localhost:5173
```

Vite reenvía `/api` al backend. Por defecto apunta a `http://localhost:8000`.

## Scripts

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo |
| `npm run typecheck` | Revisión de tipos con TypeScript |
| `npm run lint` | ESLint |
| `npm run test` | Pruebas con Vitest |
| `npm run build` | Compilación de producción en `dist/` |
| `npm run preview` | Sirve localmente el resultado de `build` |

Antes de un PR: `npm ci`, `npm run typecheck`, `npm run lint`, `npm run build` (y `npm run test`).

## Variables de entorno

Solo nombres; no llevan secretos.

| Variable | Uso |
|---|---|
| `VITE_API_PROXY_TARGET` | Destino al que Vite reenvía `/api` en desarrollo (por defecto `http://localhost:8000`) |
| `VITE_WS_BACKEND_URL` | URL del backend para la conexión en tiempo real de las notificaciones (se configura en Render) |

## Despliegue

Sitio estático en Render: compila con `npm ci && npm run build` y publica `dist/`. Ver [`render.yaml`](../render.yaml), [`render.production.yaml`](../render.production.yaml) y el [runbook de producción](../docs/operations/production-release.md).
