// Vite + Vitest configuration for the CyberHero front-end.
// Output goes straight into the Flask static tree; the Flask shell reads
// `app/static/cyberhero/.vite/manifest.json` to find the hashed entry files.
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { mockApiPlugin } from './mock/api.js';

const FLASK_DEV = 'http://127.0.0.1:8000';

export default defineConfig(({ mode }) => ({
  base: '/static/cyberhero/',
  publicDir: false,
  plugins: [
    react(),
    // The mock API is only registered for `vite --mode mock` (npm run dev:mock).
    ...(mode === 'mock' ? [mockApiPlugin()] : []),
  ],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': { target: FLASK_DEV, changeOrigin: false },
      '/static/fonts': { target: FLASK_DEV, changeOrigin: false },
    },
  },
  build: {
    outDir: '../app/static/cyberhero',
    emptyOutDir: true,
    manifest: true,
    sourcemap: false,
    target: 'es2020',
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      input: 'src/main.jsx',
      output: {
        manualChunks(id) {
          // three.js + react-three-fiber are only ever imported by the lazy
          // mascot scene, so this chunk is downloaded when the mascot mounts.
          if (id.includes('node_modules/three/') || id.includes('node_modules/@react-three/')) {
            return 'three-vendor';
          }
          return undefined;
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./test/setup.js'],
    include: ['src/**/*.test.{js,jsx}', 'test/**/*.test.{js,jsx}'],
    css: false,
  },
}));
