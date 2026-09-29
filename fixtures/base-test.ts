import { test as playwrightTest, expect } from '@playwright/test';
import { VolumePage } from '../pages/storage/VolumePage';

type PortfolioFixtures = {
  volumePage: VolumePage;
};

export const test = playwrightTest.extend<PortfolioFixtures>({
  volumePage: async ({ page }, use) => {
    await use(new VolumePage(page));
  },
});

export { expect };
