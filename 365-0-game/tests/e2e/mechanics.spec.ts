import { expect, test } from '@playwright/test';
import {
  draftTwelve,
  openReturning,
  recordOf,
  seriousViolations,
  skipToResult,
} from './helpers.ts';

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

  test('a month can be drawn again from the result screen; the new year stands and the record still adds up', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await skipToResult(page);

    const buttons = page.locator('.chances__btn');
    await expect(buttons).toHaveCount(12);
    const chancesBefore = await buttons.evaluateAll(
      (els) => els.filter((e) => !(e as HTMLButtonElement).disabled).length,
    );
    expect(chancesBefore).toBe(12); // enabled while a second chance is left

    const before = await recordOf(page);
    await buttons.nth(5).click();
    await expect(page.locator('.toast')).toContainText('drawn again');
    await expect(page.locator('.chances__mark')).toHaveCount(1);
    const after = await recordOf(page);
    expect(after.w + after.d + after.l).toBe(365);
    expect(before.w + before.d + before.l).toBe(365);

    // One free second chance: unless a combo earned more, the buttons are now off.
    const left = await page.locator('.chances p').first().textContent();
    if (left?.includes('No second chances left')) {
      await expect(buttons.first()).toBeDisabled();
    }
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

  test('the reveal takes about three seconds', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    const start = Date.now();
    await page.locator('.reveal__done button').waitFor({ state: 'visible', timeout: 6000 });
    expect(Date.now() - start).toBeLessThan(4500);
  });
});
