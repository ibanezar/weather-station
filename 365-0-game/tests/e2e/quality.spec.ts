import { expect, test, type Page } from '@playwright/test';
import { openReturning, seriousViolations } from './helpers.ts';

test.describe('the Android back gesture', () => {
  test('asks before leaving the run, at any point of a month', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card').first().waitFor();

    // Before a pick.
    await page.goBack();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('Leave this run?');
    await dialog.getByRole('button', { name: 'Keep playing' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('January');
    await expect(page.locator('.city-card')).toHaveCount(3);

    // After a pick, while its month is shown: the pick is not taken back, there is no undo.
    await page.locator('.city-card__pick').first().click();
    await expect(page.locator('.month-result')).toBeVisible();
    await page.goBack();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.getByRole('dialog').getByRole('button', { name: 'Keep playing' }).click();
    await expect(page.locator('.month-result')).toBeVisible();

    await page.goBack();
    await page.getByRole('dialog').getByRole('button', { name: 'Leave' }).click();
    await expect(page.getByRole('button', { name: 'Play endless' })).toBeVisible();
  });
});

/** What the focused element must look like: it has this class, or contains this text. */
interface FocusTarget {
  className?: string;
  text?: string;
}

/** Press Tab until the focused element matches, up to `limit` presses. */
async function tabTo(page: Page, target: FocusTarget, limit = 25): Promise<void> {
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press('Tab');
    const ok = await page.evaluate((t) => {
      const el = document.activeElement;
      if (!el) return false;
      if (t.className !== undefined && !el.classList.contains(t.className)) return false;
      if (t.text !== undefined && !el.textContent.includes(t.text)) return false;
      return true;
    }, target);
    if (ok) return;
  }
  throw new Error('could not reach the element with the keyboard');
}

test.describe('keyboard only', () => {
  test('a whole endless run can be played, and focus is always visible', async ({ page }) => {
    await openReturning(page);
    await tabTo(page, { text: 'Play endless' });
    expect(
      await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle),
    ).not.toBe('none');
    await page.keyboard.press('Enter');

    await page.locator('.city-card').first().waitFor();
    for (let round = 0; round < 12; round++) {
      // Scout the first card once, with the keyboard, to cover that control as well.
      if (round === 0) {
        await tabTo(page, { className: 'city-card__scout' });
        await page.keyboard.press('Space');
        await expect(page.locator('.city-card').first()).toHaveAttribute('data-flipped', 'true');
      }
      await tabTo(page, { className: 'city-card__pick' });
      const ring = await page.evaluate(() => {
        const s = getComputedStyle(document.activeElement as Element);
        return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) };
      });
      expect(ring.style).not.toBe('none');
      expect(ring.width).toBeGreaterThanOrEqual(3);
      await page.keyboard.press('Enter');
      // The month plays out, then focus lands on its Next month button.
      await expect(page.locator('.month-result__actions button').first()).toBeFocused({
        timeout: 4000,
      });
      await page.keyboard.press('Enter');
      if (round < 11) {
        await expect
          .poll(() =>
            page.evaluate(() =>
              [...document.querySelectorAll<HTMLElement>('.progress__step')].findIndex(
                (e) => e.dataset['state'] === 'current',
              ),
            ),
          )
          .toBe(round + 1);
      }
    }

    // The reveal can be skipped with the keyboard, and focus lands on the next action.
    await page.locator('.screen--reveal').waitFor({ timeout: 6000 });
    await page.keyboard.press('Escape');
    await expect(page.locator('.reveal__done button')).toBeFocused();
    await page.keyboard.press('Enter');
    await page.locator('.screen--result').waitFor();
    await tabTo(page, { text: 'Share result' });
    await expect(page.getByRole('button', { name: 'Share result' })).toBeFocused();
  });

  test('has no serious axe violations while the install button is showing', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.evaluate(() => {
      const event = new Event('beforeinstallprompt', { cancelable: true }) as Event & {
        prompt: () => Promise<void>;
        userChoice: Promise<{ outcome: string }>;
      };
      event.prompt = () => Promise.resolve();
      event.userChoice = Promise.resolve({ outcome: 'dismissed' });
      window.dispatchEvent(event);
    });
    await expect(page.getByRole('button', { name: 'Install the app' })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
  });
});

test.describe('performance', () => {
  test('does not shift layout when the fonts arrive late', async ({ page }) => {
    await page.route('**/*.woff2', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 800));
      await route.continue();
    });
    await page.addInitScript(() => {
      (window as unknown as { __cls: number[] }).__cls = [];
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries() as unknown as {
          value: number;
          hadRecentInput: boolean;
        }[]) {
          if (!entry.hadRecentInput)
            (window as unknown as { __cls: number[] }).__cls.push(entry.value);
        }
      }).observe({ type: 'layout-shift', buffered: true });
    });
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card').first().waitFor();
    await page.waitForTimeout(1800);
    const cls = await page.evaluate(() =>
      (window as unknown as { __cls: number[] }).__cls.reduce((a, b) => a + b, 0),
    );
    expect(cls).toBeLessThan(0.02);
  });

  test('the first screen is interactive quickly on a cold load', async ({ page }) => {
    const start = Date.now();
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    expect(Date.now() - start).toBeLessThan(2000);
  });
});
