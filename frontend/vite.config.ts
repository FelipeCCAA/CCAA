import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    host: true,
    proxy: {
      '/api': {
        // Permite que Playwright levante un backend aislado sin desviar las
        // llamadas del navegador al servidor de desarrollo que ya esté abierto.
        target: process.env.VITE_API_PROXY_TARGET
          ?? process.env.E2E_API_URL
          ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
