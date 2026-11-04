/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL pública del backend para el WebSocket de notificaciones en Render
   * (el frontend es un static site y no puede hacer proxy de WebSocket).
   * Vacía en desarrollo local: se usa el mismo origen vía el proxy de Vite. */
  readonly VITE_WS_BACKEND_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}