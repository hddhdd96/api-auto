import type { Page, TestInfo } from '@playwright/test';

export async function captureFailureScreenshot(
  page: Page,
  testInfo: TestInfo,
): Promise<void> {
  if (testInfo.status === testInfo.expectedStatus || page.isClosed()) {
    return;
  }

  await testInfo.attach('failure-screenshot', {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  });
}
