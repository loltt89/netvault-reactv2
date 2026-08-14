import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Separate from vite.config.ts (kept minimal/prod-focused) rather than
// merging test config into it — vitest's own `defineConfig` here gives
// proper typing for the `test` block without pulling test-only options
// into the file Vite itself reads for dev/build.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: false,
    include: ['src/**/*.test.{ts,tsx}'],
    exclude: ['e2e/**'],
  },
});
