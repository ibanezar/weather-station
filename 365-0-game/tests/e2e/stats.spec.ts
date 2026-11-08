import { expect, test } from '@playwright/test';
import {
  draftTwelve,
  openReturning,
  recordOf,
  seriousViolations,
  skipToResult,
} from './helpers.ts';

test.describe('statistics', () => {
  test('say so when nothing has been played yet', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Statistics' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Statistics' })).toBeVisible();
    await expect(page.getByText(/Nothing here yet/)).toBeVisible();
    await page.getByRole('button', { name: 'Back' }).click();
    await expect(page.getByRole('heading', { level: 1, name: '365-0' })).toBeVisible();
  });

  test('show a finished daily and a finished endless run', async ({ page }) => {
    test.setTimeout(90_000); // two whole games
    await openReturning(page);
    await page.getByRole('button', { name: 'Play daily' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    const daily = await recordOf(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await skipToResult(page);

    await page.goto('/#/stats');
    const tiles = page.locator('.stats__tile');
    await expect(tiles).toHaveCount(4);
    await expect(tiles.filter({ hasText: 'Games played' }).locator('.stats__value')).toHaveText(
      '2',
    );
    await expect(tiles.filter({ hasText: 'Dailies played' }).locator('.stats__value')).toHaveText(
      '1',
    );
    const sunshine = page.locator('.stats__table tbody tr').first();
    await expect(sunshine).toContainText('Sunshine');
    await expect(sunshine).toContainText(
      `${String(daily.w)}-${String(daily.d)}-${String(daily.l)}`,
    );
    await expect(sunshine.locator('td').last()).toHaveText('2');
    await expect(page.locator('.stats__recent li')).toHaveCount(1);

    // Resetting progress empties it again.
    await page.goto('/#/settings');
    await page.getByRole('button', { name: /Reset progress/ }).click();
    await page
      .getByRole('button', { name: /^Reset/ })
      .last()
      .click();
    await page.goto('/#/stats');
    await expect(page.getByText(/Nothing here yet/)).toBeVisible();
  });

  test('has no serious axe violations and does not overflow at 360 px', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 780 });
    await openReturning(page);
    await page.getByRole('button', { name: 'Play daily' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    await page.goto('/#/stats');
    await page.locator('.stats__tile').first().waitFor();
    expect(await seriousViolations(page)).toEqual([]);
    const over = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(over).toBeLessThanOrEqual(0);
  });
});

test.describe('anonymous play counts', () => {
  test('are off by switch, explained in Privacy, and never sent from a test or development host', async ({
    page,
  }) => {
    const sent: string[] = [];
    page.on('request', (r) => {
      if (r.url().includes('/365-0/stat')) sent.push(r.url());
    });
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    expect(sent).toEqual([]); // only the live site sends counts

    await page.goto('/#/settings');
    const sw = page.getByRole('switch', { name: 'Anonymous play counts' });
    await expect(sw).toHaveAttribute('aria-checked', 'true');
    await sw.click();
    await expect(sw).toHaveAttribute('aria-checked', 'false');
    await page.reload();
    await expect(page.getByRole('switch', { name: 'Anonymous play counts' })).toHaveAttribute(
      'aria-checked',
      'false',
    );

    await page.goto('/#/privacy');
    await expect(page.getByText(/anonymous count/)).toBeVisible();
  });
});
