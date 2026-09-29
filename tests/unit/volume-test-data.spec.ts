import { expect, test } from '@playwright/test';
import { createVolumeTestData } from '../../data/volume-test-data';

test('creates unique volume names and a positive size', () => {
  const firstVolume = createVolumeTestData();
  const secondVolume = createVolumeTestData();

  expect(firstVolume.name).toMatch(/^portfolio-volume-[a-f0-9]{8}$/);
  expect(secondVolume.name).not.toBe(firstVolume.name);
  expect(firstVolume.sizeGiB).toBeGreaterThan(0);
});
