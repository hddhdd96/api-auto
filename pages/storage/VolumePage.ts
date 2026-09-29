import { expect, type Locator, type Page } from '@playwright/test';
import { BasePage } from '../BasePage';

export class VolumePage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  private readonly storageNavigationLink = this.page.getByRole('link', {
    name: 'Storage',
    exact: true,
  });
  private readonly volumesHeading = this.page.getByRole('heading', {
    name: 'Volumes',
    exact: true,
  });
  private readonly createVolumeButton = this.page.getByRole('button', {
    name: 'Create volume',
    exact: true,
  });
  private readonly createVolumeDialog = this.page.getByRole('dialog', {
    name: 'Create volume',
    exact: true,
  });
  private readonly volumeNameInput = this.createVolumeDialog.getByLabel('Volume name', {
    exact: true,
  });
  private readonly volumeSizeSelect = this.createVolumeDialog.getByLabel('Size (GiB)', {
    exact: true,
  });
  private readonly createDialogSubmitButton = this.createVolumeDialog.getByRole('button', {
    name: 'Create',
    exact: true,
  });
  private readonly volumeDetailsPanel = this.page.getByRole('region', {
    name: 'Volume details',
    exact: true,
  });
  private readonly deleteConfirmationDialog = this.page.getByRole('dialog', {
    name: 'Delete volume',
    exact: true,
  });

  async openStorage(): Promise<void> {
    await this.storageNavigationLink.click();
    await expect(this.volumesHeading).toBeVisible();
  }

  async createVolume(name: string, sizeGiB: number): Promise<void> {
    await this.createVolumeButton.click();
    await expect(this.createVolumeDialog).toBeVisible();
    await this.volumeNameInput.fill(name);
    await this.volumeSizeSelect.selectOption(String(sizeGiB));
    await this.createDialogSubmitButton.click();
    await expect(this.getVolumeRow(name)).toBeVisible();
  }

  getVolumeStatus(volumeName: string): Locator {
    return this.getVolumeRow(volumeName)
      .getByRole('cell')
      .filter({ hasText: /^(Creating|Available|In use|Error)$/ });
  }

  getVolumeRow(volumeName: string): Locator {
    return this.page.getByRole('row').filter({ hasText: volumeName });
  }

  async openVolumeDetails(volumeName: string): Promise<void> {
    await this.getVolumeRow(volumeName)
      .getByRole('link', { name: volumeName, exact: true })
      .click();
    await expect(this.volumeDetailsPanel).toBeVisible();
  }

  async expectVolumeDetails(volumeName: string, sizeGiB: number): Promise<void> {
    await expect(this.volumeDetailsPanel.getByText(volumeName, { exact: true })).toBeVisible();
    await expect(
      this.volumeDetailsPanel.getByText(`${sizeGiB} GiB`, { exact: true }),
    ).toBeVisible();
    await expect(this.volumeDetailsPanel.getByText('Available', { exact: true })).toBeVisible();
  }

  async deleteVolume(volumeName: string): Promise<void> {
    await this.getVolumeRow(volumeName)
      .getByRole('button', { name: 'Delete', exact: true })
      .click();
    await expect(this.deleteConfirmationDialog).toBeVisible();
    await this.deleteConfirmationDialog
      .getByRole('button', { name: 'Delete', exact: true })
      .click();
    await expect(this.getVolumeRow(volumeName)).toHaveCount(0);
  }
}
