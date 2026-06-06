import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Proxy API requests to the FastAPI backend during development.
    // Without this, a request to /articles from localhost:5173 would
    // fail (CORS / wrong port). Vite forwards it to localhost:8000 instead.
    proxy: {
      '/articles': 'http://localhost:8000',
      '/digest': 'http://localhost:8000',
    },
  },
})
