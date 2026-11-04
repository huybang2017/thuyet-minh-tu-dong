import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxy = { '/api': 'http://localhost:8000', '/static': 'http://localhost:8000' }

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  test: { environment: 'node' },
})
