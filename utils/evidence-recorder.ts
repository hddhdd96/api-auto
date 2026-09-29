import type { Page, TestInfo } from '@playwright/test';

export async function captureCheckpointScreenshot(
  page: Page,
  testInfo: TestInfo,
  checkpointName: string,
): Promise<void> {
  await testInfo.attach(checkpointName, {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  });
}
