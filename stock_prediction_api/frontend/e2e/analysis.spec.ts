import { test, expect } from '@playwright/test';
import path from 'node:path';

test('analyze, reveal, save history and inspect performance', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/analyze');
  await expect(page.getByRole('button', { name: 'Analyze session' })).toBeEnabled();
  const response = page.waitForResponse(res => res.url().endsWith('/app/analysis/predict') && res.request().method() === 'POST');
  await page.getByRole('button', { name: 'Analyze session' }).click();
  const prediction = await (await response).json();
  expect(prediction.symbol).toBe('RELIANCE');
  expect(prediction.outcome).toBeNull();
  expect(prediction.history.length).toBe(90);
  await expect(page.getByRole('button', { name: 'Reveal actual next session' })).toBeEnabled();
  await page.screenshot({ path: 'test-results/analyzer-desktop.png', fullPage: true });
  await page.getByRole('button', { name: 'Reveal actual next session' }).click();
  await expect(page.getByText(/What actually happened/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Actual outcome revealed' })).toBeDisabled();
  await page.getByRole('link', { name: 'History', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'A record of your research' })).toBeVisible();
  await expect(page.getByRole('cell', { name: /RELIANCE/ }).first()).toBeVisible();
  await page.getByRole('link', { name: 'Model performance', exact: true }).click();
  await expect(page.getByText('Holdout accuracy', { exact: true })).toBeVisible();
  await expect(page.getByText('Has not beaten the baseline', { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('latest session has no made-up outcome and changing stock clears analysis', async ({ page }) => {
  await page.goto('/analyze');
  const date = page.getByLabel('Analysis date');
  await expect(page.getByRole('button', { name: 'Analyze session' })).toBeEnabled();
  await date.selectOption('2021-04-30');
  await page.getByRole('button', { name: 'Analyze session' }).click();
  await expect(page.getByRole('button', { name: 'No later candle in dataset' })).toBeDisabled();
  await page.getByLabel('NSE stock').selectOption('TCS');
  await expect(page.getByText('Your analysis will appear here.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Analyze session' })).toBeEnabled();
  await page.getByRole('button', { name: 'Analyze session' }).click();
  await expect(page.getByRole('button', { name: 'Reveal actual next session' })).toBeEnabled();
});

test('CSV upload shows validation errors and imports a real dataset', async ({ page }) => {
  await page.goto('/analyze');
  await page.getByRole('button', { name: 'Import CSV' }).click();
  await page.getByLabel('Stock symbol').fill('TCS');
  const upload = page.getByLabel(/Daily CSV/);
  await upload.setInputFiles({ name: 'invalid.csv', mimeType: 'text/csv', buffer: Buffer.from('date,close\n2020-01-01,100') });
  await page.getByRole('button', { name: 'Import and train model' }).click();
  await expect(page.getByRole('alert')).toContainText('Required CSV columns');
  await upload.setInputFiles(path.resolve(import.meta.dirname, '../../data/indian_daily/TCS.csv'));
  await page.getByRole('button', { name: 'Import and train model' }).click();
  await expect(page.getByRole('status')).toContainText('TCS is ready');
  await page.getByRole('button', { name: 'Close import' }).click();
  await page.getByLabel('NSE stock').selectOption('TCS');
  await expect(page.getByRole('button', { name: 'Analyze session' })).toBeEnabled();
});

test('workspace works on a narrow mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/analyze');
  await expect(page.getByRole('button', { name: 'Analyze session' })).toBeEnabled();
  await page.getByRole('button', { name: 'Analyze session' }).click();
  await expect(page.getByRole('button', { name: 'Reveal actual next session' })).toBeEnabled();
  const widths = await page.evaluate(() => ({ viewport: window.innerWidth, document: document.documentElement.scrollWidth }));
  expect(widths.document).toBeLessThanOrEqual(widths.viewport + 1);
  await page.screenshot({ path: 'test-results/analyzer-mobile.png', fullPage: true });
});
