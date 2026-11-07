import { expect, test } from '@playwright/test';

test('the app loads with one h1 and no console errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', (err) => errors.push(err.message));

  await page.goto('/');
  // A first visit shows the three-line introduction.
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('How it works');
  await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
  expect(errors).toEqual([]);
});
