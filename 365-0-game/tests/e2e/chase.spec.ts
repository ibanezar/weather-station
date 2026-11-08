import { expect, test } from '@playwright/test';
import {
  draftTwelve,
  keepMonth,
  openReturning,
  recordOf,
  seriousViolations,
  skipToResult,
} from './helpers.ts';

test.describe('what to chase', () => {
  test('the first page offers sun, snow, rain, storms and heat; sun is chosen, the choice is remembered', async ({
    page,
  }) => {
    await openReturning(page);
    await expect(page.getByRole('radio', { name: 'Sun' })).toBeChecked();
    await expect(page.locator('.home__chase-note')).toContainText('Perfect days win');
    await page.getByRole('radio', { name: 'Snow' }).check();
    await expect(page.locator('.home__chase-note')).toContainText('Snow and frost days win');
    await expect(page.locator('.home__step').nth(2)).toContainText('Collect snow and frost days');
    await page.reload();
    await expect(page.getByRole('radio', { name: 'Snow' })).toBeChecked();
  });

  test('a snow game says what it scores: scout bars, risk and the month are about snow', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('radio', { name: 'Snow' }).check();
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card').first().waitFor();
    await expect(page.locator('.draft__ask')).toContainText('most snow and frost');
    await page
      .locator('.city-card')
      .first()
      .getByRole('button', { name: /^Scout/ })
      .click();
    await expect(page.locator('.city-card').first()).toContainText('Snow and frost days');
    await expect(page.locator('.city-card').first()).toContainText('Warm days');
    await page.locator('.city-card__pick').first().click();
    await expect(page.locator('.month-result__stat').first()).toContainText('snowy');
  });

  test('a whole snow game ends with a snow grade, the record adds up and the chase is named', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('radio', { name: 'Storms' }).check();
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    const record = await recordOf(page);
    expect(record.w + record.d + record.l).toBe(365);
    await expect(page.locator('.result__head .chip').filter({ hasText: 'Storms' })).toBeVisible();
    await expect(page.locator('.result__explain')).toContainText('stormy days');
    await expect(page.locator('.result__grade h2')).not.toHaveText(/^(Stormbound|Sun chaser)$/);
  });

  test('each chase has its own daily, and a daily of any chase keeps the streak', async ({
    page,
  }) => {
    test.setTimeout(90_000); // two whole games
    await openReturning(page);
    await page.getByRole('button', { name: 'Play daily' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    const sunRecord = (await recordOf(page)).text;
    await page.getByRole('button', { name: 'Home', exact: false }).first().click();
    // The sunny daily is done; the rain daily is still open.
    await expect(page.getByRole('button', { name: "See today's result" })).toBeVisible();
    await page.getByRole('radio', { name: 'Rain' }).check();
    await expect(page.getByRole('button', { name: 'Play daily' })).toBeVisible();
    await page.getByRole('button', { name: 'Play daily' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    await page.getByRole('button', { name: 'Home', exact: false }).first().click();
    await expect(page.getByRole('button', { name: "See today's result" })).toBeVisible();
    // Back to sun: its result is still the first one.
    await page.getByRole('radio', { name: 'Sun' }).check();
    await page.getByRole('button', { name: "See today's result" }).click();
    expect((await recordOf(page)).text).toBe(sunRecord);
  });

  test('an invented event is labelled as invented', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    // Play endless games until a round shows an invented event (they are common: about a third of the events).
    for (let tries = 0; tries < 6; tries++) {
      await page.locator('.city-card').first().waitFor();
      for (let round = 0; round < 12; round++) {
        const chip = page.locator('.draft__event .chip');
        if ((await chip.count()) > 0 && (await chip.textContent())?.startsWith('What if:')) {
          await expect(page.locator('.draft__invented')).toContainText('Invented');
          return;
        }
        await page.locator('.city-card__pick').first().click();
        await keepMonth(page);
      }
      await page.locator('.reveal__done button').waitFor({ timeout: 6000 });
      await page.goto('/');
      await page.getByRole('button', { name: 'Play endless' }).click();
    }
    throw new Error('no invented event in six games');
  });

  test('has no serious axe violations on the first page, with a chase chosen', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('radio', { name: 'Heat' }).check();
    expect(await seriousViolations(page)).toEqual([]);
  });
});
