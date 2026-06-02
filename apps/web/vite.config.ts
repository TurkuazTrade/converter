import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 7501,
    allowedHosts: ['.ngrok-free.dev'],
    proxy: {
      '/api': process.env.VITE_PROXY_TARGET ?? 'http://localhost:8501',
    },
  },
});
