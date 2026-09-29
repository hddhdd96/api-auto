import { createVolumeTestData } from '../../../data/volume-test-data';
import { expect, test } from '../../../fixtures/base-test';
import { captureCheckpointScreenshot } from '../../../utils/evidence-recorder';

test('creates, inspects, and deletes a volume', async ({ page, volumePage }, testInfo) => {
  const volume = createVolumeTestData();

  await volumePage.openStorage();
  await volumePage.createVolume(volume.name, volume.sizeGiB);
  await expect(volumePage.getVolumeStatus(volume.name)).toHaveText('Available');

  await volumePage.openVolumeDetails(volume.name);
  await volumePage.expectVolumeDetails(volume.name, volume.sizeGiB);
  await captureCheckpointScreenshot(page, testInfo, 'volume-details');

  await volumePage.deleteVolume(volume.name);
});
