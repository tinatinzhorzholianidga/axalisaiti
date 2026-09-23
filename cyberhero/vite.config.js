// Vite + Vitest configuration for the CyberHero front-end.
// Output goes straight into the Flask static tree; the Flask shell reads
// `app/static/cyberhero/.vite/manifest.json` to find the hashed entry files.
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { mockApiPlugin } from './mock/api.js';

const FLASK_DEV = 'http://127.0.0.1:8000';

export default defineConfig(({ mode, command }) => ({
  // the production bundle lives under Flask's static tree; the dev server serves from /
  base: command === 'build' ? '/static/cyberhero/' : '/',
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
      // two pages share one bundle: the CyberHero app (src/main.jsx) and IO
      // as the welcome host on the eLearning home page (src/io-host.jsx);
      // the manifest keeps both under their source paths
      input: { main: 'src/main.jsx', 'io-host': 'src/io-host.jsx' },
      output: {
        manualChunks(id) {
          // three.js + react-three-fiber are only ever imported by the lazy
          // mascot scene, so this chunk is downloaded when the mascot mounts.
          if (id.includes('node_modules/three/') || id.includes('node_modules/@react-three/')) {
            return 'three-vendor';
          }
          // WebLLM is only imported when an operator has configured a
          // self-hosted tutor model and the visitor presses "load".
          if (id.includes('node_modules/@mlc-ai/')) {
            return 'webllm-vendor';
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
