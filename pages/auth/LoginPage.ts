import { expect, type Page } from '@playwright/test';
import { BasePage } from '../BasePage';

export class LoginPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  private readonly usernameInput = this.page.getByLabel('Username', { exact: true });
  private readonly passwordInput = this.page.getByLabel('Password', { exact: true });
  private readonly signInButton = this.page.getByRole('button', {
    name: 'Sign in',
    exact: true,
  });
  private readonly dashboardHeading = this.page.getByRole('heading', {
    name: 'Dashboard',
    exact: true,
  });

  async signIn(username: string, password: string): Promise<void> {
    await this.usernameInput.fill(username);
    await this.passwordInput.fill(password);
    await this.signInButton.click();
    await expect(this.dashboardHeading).toBeVisible();
  }
}
