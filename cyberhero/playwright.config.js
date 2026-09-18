// Playwright smoke tests run against the Flask shell serving the built bundle.
// `scripts/e2e_server.py` (repo root) starts Flask with seeded content on 5055.
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5055',
    trace: 'retain-on-failure',
    locale: 'ka-GE',
    // A pre-installed Chromium can be used instead of `playwright install`
    // (CI and locked-down build agents): PLAYWRIGHT_CHROMIUM_PATH=/path/to/chrome
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'python ../scripts/e2e_server.py',
    url: 'http://127.0.0.1:5055/health',
    reuseExistingServer: true,
    timeout: 120000,
  },
});
