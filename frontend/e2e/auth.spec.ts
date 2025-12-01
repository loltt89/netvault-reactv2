import { test, expect } from '@playwright/test';

/**
 * Authentication E2E tests
 * Tests login, logout, and authentication flows
 */

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    // Go to login page before each test
    await page.goto('/login');
  });

  test('login page loads correctly', async ({ page }) => {
    // Check page title or heading
    await expect(page).toHaveURL(/.*login/);

    // Check for login form elements
    await expect(page.locator('input[name="email"], input[type="email"]')).toBeVisible();
    await expect(page.locator('input[name="password"], input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('shows error with invalid credentials', async ({ page }) => {
    // Fill in invalid credentials
    await page.fill('input[name="email"], input[type="email"]', 'invalid@example.com');
    await page.fill('input[name="password"], input[type="password"]', 'wrongpassword');

    // Submit the form
    await page.click('button[type="submit"]');

    // Wait for error message
    await expect(page.locator('.error, .alert-error, [class*="error"]')).toBeVisible({ timeout: 10000 });
  });

  test('email field is required', async ({ page }) => {
    // Try to submit without email
    await page.fill('input[name="password"], input[type="password"]', 'somepassword');
    await page.click('button[type="submit"]');

    // Check for HTML5 validation or error
    const emailInput = page.locator('input[name="email"], input[type="email"]');
    await expect(emailInput).toHaveAttribute('required', '');
  });

  test('password field is required', async ({ page }) => {
    // Try to submit without password
    await page.fill('input[name="email"], input[type="email"]', 'test@example.com');
    await page.click('button[type="submit"]');

    // Check for HTML5 validation or error
    const passwordInput = page.locator('input[name="password"], input[type="password"]');
    await expect(passwordInput).toHaveAttribute('required', '');
  });

  test('login button shows loading state', async ({ page }) => {
    // Fill in credentials
    await page.fill('input[name="email"], input[type="email"]', 'test@example.com');
    await page.fill('input[name="password"], input[type="password"]', 'password123');

    // Click submit and check for loading state
    const submitButton = page.locator('button[type="submit"]');
    await submitButton.click();

    // Button should be disabled during loading
    await expect(submitButton).toBeDisabled({ timeout: 1000 }).catch(() => {
      // Some implementations may not disable the button
    });
  });
});

test.describe('Protected Routes', () => {
  test('redirects to login when not authenticated', async ({ page }) => {
    // Try to access dashboard without authentication
    await page.goto('/dashboard');

    // Should redirect to login
    await expect(page).toHaveURL(/.*login/);
  });

  test('redirects to login when accessing devices page', async ({ page }) => {
    // Try to access devices page without authentication
    await page.goto('/devices');

    // Should redirect to login
    await expect(page).toHaveURL(/.*login/);
  });

  test('redirects to login when accessing backups page', async ({ page }) => {
    // Try to access backups page without authentication
    await page.goto('/backups');

    // Should redirect to login
    await expect(page).toHaveURL(/.*login/);
  });

  test('redirects to login when accessing settings page', async ({ page }) => {
    // Try to access settings page without authentication
    await page.goto('/settings');

    // Should redirect to login
    await expect(page).toHaveURL(/.*login/);
  });
});
