import 'dotenv/config';

import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

const authStatePath = path.join(__dirname, 'auth', 'storageState.json');
const TEST_TIMEOUT_MS = 30_000;
const ASSERTION_TIMEOUT_MS = 5_000;
const CI_RETRY_COUNT = 1;

export default defineConfig({
  testDir: './',
  testMatch: 'tests/testsuite/**/*.spec.ts',
  timeout: TEST_TIMEOUT_MS,
  expect: {
    timeout: ASSERTION_TIMEOUT_MS,
  },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? CI_RETRY_COUNT : 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  outputDir: 'test-results',
  projects: [
    {
      name: 'setup',
      testDir: './auth',
      testMatch: '**/auth.setup.ts',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: process.env.BASE_URL ?? 'https://example.com',
      },
    },
    {
      name: 'chromium',
      testMatch: 'tests/testsuite/**/*.spec.ts',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        baseURL: process.env.BASE_URL ?? 'https://example.com',
        storageState: authStatePath,
        screenshot: 'only-on-failure',
        trace: 'retain-on-failure',
        video: 'retain-on-failure',
      },
    },
    {
      name: 'unit',
      testDir: './tests/unit',
      testMatch: '**/*.spec.ts',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
});
