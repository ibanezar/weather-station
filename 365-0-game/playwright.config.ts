import { defineConfig } from '@playwright/test';

// In the cloud sandbox Chromium is preinstalled; point PW_CHROMIUM_PATH at it.
// Elsewhere (CI, laptops) leave it unset and use `npx playwright install chromium`.
const executablePath = process.env['PW_CHROMIUM_PATH'];

export default defineConfig({
  testDir: 'tests/e2e',
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:4173',
    viewport: { width: 390, height: 844 },
    locale: 'en-GB',
    ...(executablePath ? { launchOptions: { executablePath, args: ['--no-sandbox'] } } : {}),
  },
  webServer: {
    command: 'npm run build && npm run preview',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env['CI'],
    timeout: 120_000,
  },
});
