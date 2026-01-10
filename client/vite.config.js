import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from "path"
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },  server: {
    proxy: {
      '/analyze_issue': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/safe-route': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/potholes/report': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/potholes/iot': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/potholes/map': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },  theme: {
    extend: {
      fontFamily: {
        poppins: ['Poppins', 'sans-serif'],
      },
    },
  },
})
