import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Frontend pratar med FastAPI-backenden pa :8000 via proxy, sa allt gar
// same-origin (inga CORS-bekymmer) under utveckling.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
