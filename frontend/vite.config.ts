import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Mismo origen para el navegador: la cookie de sesión viaja sin CORS.
    proxy: { '/api': process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000' },
    watch: { usePolling: process.env.VITE_USE_POLLING === 'true' },
  },
})
