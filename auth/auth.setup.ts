import 'dotenv/config';

import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { test } from '@playwright/test';
import { LoginPage } from '../pages/auth/LoginPage';

const authStatePath = path.join(__dirname, 'storageState.json');

test('authenticate and save reusable browser state', async ({ page }) => {
  const username = process.env.LOGIN_ID;
  const password = process.env.LOGIN_PASSWORD;

  if (!username || !password) {
    throw new Error('LOGIN_ID and LOGIN_PASSWORD must be set in the local .env file.');
  }

  await page.goto('/login');
  await new LoginPage(page).signIn(username, password);
  await mkdir(path.dirname(authStatePath), { recursive: true });
  await page.context().storageState({ path: authStatePath });
});
