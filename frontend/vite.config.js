import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    allowedHosts: [
      'aoi-tool-rpi',
      'aoi-tool-rpi.ihl',
      'aoi-tool-rpi.local',
      'hostname',
    ],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:57842',
        timeout: 60000,
      },
    },
  },
})