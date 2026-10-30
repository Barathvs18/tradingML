import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: 'production.spec.ts',
  workers: 1,
  timeout: 60000,
  outputDir: './test-results/production',
  use: {
    baseURL: process.env.PRODUCTION_TEST_URL || 'https://localhost:8443',
    ignoreHTTPSErrors: true, // Local Caddy uses its internal CA; public deployment requires valid TLS.
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    trace: 'retain-on-failure', screenshot: 'only-on-failure',
  },
});
