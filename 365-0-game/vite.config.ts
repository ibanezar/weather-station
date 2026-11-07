import { defineConfig } from 'vitest/config';
import { pwa } from './scripts/vite-pwa.ts';

export default defineConfig({
  // Relative base so the build works from any path (this repo serves it from a subfolder).
  base: './',
  plugins: [pwa(import.meta.dirname)],
  build: {
    target: 'es2022',
    sourcemap: false,
  },
  test: {
    include: ['tests/unit/**/*.test.ts'],
    environment: 'node',
  },
});
