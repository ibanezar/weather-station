import { defineConfig } from 'vitest/config';

export default defineConfig({
  // Relative base so the build works from any path (this repo serves it from a subfolder).
  base: './',
  build: {
    target: 'es2022',
    sourcemap: false,
  },
  test: {
    include: ['tests/unit/**/*.test.ts'],
    environment: 'node',
  },
});
