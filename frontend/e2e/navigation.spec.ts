import { test, expect } from '@playwright/test';

/**
 * Navigation E2E tests
 * Tests app navigation and routing without authentication
 */

test.describe('Navigation', () => {
  test('root redirects to login or dashboard', async ({ page }) => {
    await page.goto('/');

    // Should redirect to login (if not authenticated) or dashboard
    await expect(page).toHaveURL(/\/(login|dashboard)/);
  });

  test('404 page for unknown routes', async ({ page }) => {
    await page.goto('/this-page-does-not-exist');

    // Should show 404 or redirect to login
    const content = await page.content();
    const is404 = content.includes('404') || content.includes('not found') || content.includes('Not Found');
    const isLogin = page.url().includes('login');

    expect(is404 || isLogin).toBeTruthy();
  });

  test('login page is accessible', async ({ page }) => {
    await page.goto('/login');

    await expect(page).toHaveURL(/.*login/);
    await expect(page.locator('body')).toBeVisible();
  });
});

test.describe('UI Elements', () => {
  test('login page has proper form structure', async ({ page }) => {
    await page.goto('/login');

    // Check form exists
    const form = page.locator('form');
    await expect(form).toBeVisible();

    // Check inputs exist
    const emailInput = page.locator('input[name="email"], input[type="email"]');
    const passwordInput = page.locator('input[name="password"], input[type="password"]');

    await expect(emailInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
  });

  test('login page has NetVault branding', async ({ page }) => {
    await page.goto('/login');

    // Check for NetVault text or logo
    const pageContent = await page.content();
    const hasNetVault = pageContent.toLowerCase().includes('netvault');

    expect(hasNetVault).toBeTruthy();
  });
});

test.describe('Responsive Design', () => {
  test('login page works on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/login');

    // Form should still be visible
    await expect(page.locator('form')).toBeVisible();
    await expect(page.locator('input[name="email"], input[type="email"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('login page works on tablet viewport', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/login');

    // Form should be visible
    await expect(page.locator('form')).toBeVisible();
  });

  test('login page works on desktop viewport', async ({ page }) => {
    // Set desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/login');

    // Form should be visible
    await expect(page.locator('form')).toBeVisible();
  });
});
