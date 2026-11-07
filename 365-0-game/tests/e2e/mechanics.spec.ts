import { expect, test, type Page } from '@playwright/test';
import {
  draftTwelve,
  keepMonth,
  openReturning,
  recordOf,
  seriousViolations,
  skipToResult,
} from './helpers.ts';

/** The eleven months after the first. */
async function draftRest(page: Page): Promise<void> {
  for (let i = 1; i < 12; i++) {
    await page.locator('.city-card__pick').first().click();
    await keepMonth(page);
  }
  await page.locator('.screen--reveal').waitFor({ timeout: 6000 });
}

test.describe('risk and second chances', () => {
  test('every card shows how much the month varies, and the counter starts at one second chance', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card').first().waitFor();
    await expect(page.locator('.city-card__risk')).toHaveCount(3);
    for (const text of await page.locator('.city-card__risk').allTextContents()) {
      expect(text).toMatch(/Steady|Mixed|Swingy|Rarely perfect/);
    }
    await expect(page.locator('.progress__chances')).toContainText('1 second chance');
  });

  test('a redraw is allowed once at first; the year still adds up to 365 days', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card__pick').first().click();
    await page.getByRole('button', { name: /Redraw this month/ }).click({ timeout: 4000 });
    await keepMonth(page);
    await draftRest(page);
    await skipToResult(page);
    const record = await recordOf(page);
    expect(record.w + record.d + record.l).toBe(365);
  });

  test('has no serious axe violations on the cards and on the result screen', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card').first().waitFor();
    expect(await seriousViolations(page)).toEqual([]);
    await draftTwelve(page);
    await skipToResult(page);
    expect(await seriousViolations(page)).toEqual([]);
  });

  test('the finale after the twelfth month is short', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    const start = Date.now();
    await page.locator('.reveal__done button').waitFor({ state: 'visible', timeout: 6000 });
    expect(Date.now() - start).toBeLessThan(3000);
  });
});
