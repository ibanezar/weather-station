import AxeBuilder from '@axe-core/playwright';
import { expect, type Page } from '@playwright/test';

/** Open the game as a returning player (onboarding already seen) unless storage already has data. */
export async function openReturning(
  page: Page,
  extra: Record<string, unknown> = {},
): Promise<string[]> {
  const errors: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  page.on('pageerror', (e) => errors.push(e.message));
  await page.addInitScript((seed) => {
    if (!localStorage.getItem('365-0:v1')) {
      localStorage.setItem('365-0:v1', JSON.stringify({ v: 1, onboarded: true, ...seed }));
    }
  }, extra);
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  return errors;
}

/** Pick one of the three cards in every round (0 = first card) and land on the reveal. */
export async function draftTwelve(
  page: Page,
  choose: (round: number) => number = () => 0,
): Promise<void> {
  await page.locator('.city-card').first().waitFor();
  for (let round = 0; round < 12; round++) {
    await expect
      .poll(() =>
        page.evaluate(() =>
          [...document.querySelectorAll<HTMLElement>('.progress__step')].findIndex(
            (e) => e.dataset['state'] === 'current',
          ),
        ),
      )
      .toBe(round);
    await page.locator('.city-card__pick').nth(choose(round)).click();
  }
  await page.locator('.screen--reveal').waitFor({ timeout: 6000 });
}

/** Skip the reveal animation and open the result screen. */
export async function skipToResult(page: Page): Promise<void> {
  await page.locator('.screen--reveal').click({ position: { x: 10, y: 10 } });
  await page.locator('.reveal__done button').click();
  await page.locator('.screen--result').waitFor();
}

export async function recordOf(
  page: Page,
): Promise<{ w: number; d: number; l: number; text: string }> {
  const text = ((await page.locator('.result__record').textContent()) ?? '')
    .replace('Record', '')
    .trim();
  const [w, d, l] = text.split('-').map(Number) as [number, number, number];
  return { w, d, l, text };
}

export async function seriousViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).analyze();
  return results.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
}
