import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5174,
    strictPort: true,
    open: 'http://localhost:5174/',
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/slides': 'http://127.0.0.1:8000',
      '/docs': 'http://127.0.0.1:8000'
    }
  },
  preview: {
    host: 'localhost',
    port: 5174,
    strictPort: true
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
});
