import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/v1': {
        target: process.env.VITE_BYOS_BACKEND_URL || 'https://api.veklom.com',
        changeOrigin: true,
      },
      '/v1': {
        target: process.env.VITE_CAPPO_BACKEND_URL || 'https://cappo.veklom.com',
        changeOrigin: true,
      },
    },
  },
})
