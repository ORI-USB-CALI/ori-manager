import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // El backend (uvicorn, puerto 8000) no tiene CORSMiddleware configurado.
      // Al proxyear /usuarios desde el propio dev server de Vite, la petición
      // sale del mismo origen (localhost:5173) y el navegador no la bloquea.
      '/usuarios': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
