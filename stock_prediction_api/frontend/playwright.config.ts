import { defineConfig } from '@playwright/test';
import path from 'node:path';

export default defineConfig({
  testDir: './e2e',
  testIgnore: 'production.spec.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  outputDir: './test-results',
  use: { baseURL: 'http://127.0.0.1:8011', channel: process.env.PLAYWRIGHT_CHANNEL || undefined, headless: true, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: {
    command: `"${process.env.PYTHON_EXECUTABLE || (process.platform === 'win32' ? '.venv-prod\\Scripts\\python.exe' : 'python')}" -m uvicorn app.local_main:app --host 127.0.0.1 --port 8011`,
    cwd: path.resolve(import.meta.dirname, '..'),
    url: 'http://127.0.0.1:8011/health',
    env: { ANALYSIS_DB_PATH: path.resolve(import.meta.dirname, `../.test-artifacts/e2e-${Date.now()}.sqlite3`) },
    reuseExistingServer: false,
    timeout: 60000,
  },
});
