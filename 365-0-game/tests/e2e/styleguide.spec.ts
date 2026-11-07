import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const open = async (page: Page): Promise<string[]> => {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', (err) => errors.push(err.message));
  await page.goto('/#/styleguide');
  await expect(page.getByRole('heading', { level: 1, name: 'Styleguide' })).toBeVisible();
  await page.locator('canvas').waitFor();
  return errors;
};

test('renders without console errors and the grid canvas has a size', async ({ page }) => {
  const errors = await open(page);
  const box = await page.locator('canvas').boundingBox();
  expect(box?.width).toBeGreaterThan(200);
  expect(box?.height).toBeGreaterThan(200);
  expect(errors).toEqual([]);
});

for (const scheme of ['light', 'dark'] as const) {
  test(`has no serious or critical axe violations in ${scheme} mode`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await open(page);
    const results = await new AxeBuilder({ page }).analyze();
    const bad = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
    expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual(
      [],
    );
  });
}

test('has no serious or critical axe violations in pattern mode', async ({ page }) => {
  await open(page);
  await page.getByRole('group', { name: 'Patterns' }).getByRole('button', { name: 'on' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-pattern', 'on');
  const results = await new AxeBuilder({ page }).analyze();
  const bad = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  expect(bad.map((v) => v.id)).toEqual([]);
});

for (const width of [360, 430]) {
  test(`has no horizontal overflow at ${String(width)} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await open(page);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
}

test('scouting flips a card and puts the scouted values in the pick button name', async ({
  page,
}) => {
  await open(page);
  const card = page.locator('.city-card').first();
  await card.getByRole('button', { name: 'Scout' }).click();
  await expect(card).toHaveAttribute('data-flipped', 'true');
  const pick = card.locator('.city-card__pick');
  await expect(pick).toHaveAccessibleName(
    /^Pick this city\.\s*Reykjavik.*Perfect days 2 of 5.*Bad days 3 of 5/,
  );
  // The Scout button is gone and keyboard focus moved to the card instead of being lost.
  await expect(pick).toBeFocused();
});

test('picking shows an undo toast that disappears after about two seconds', async ({ page }) => {
  await open(page);
  await page.locator('.city-card__pick').first().click();
  const toast = page.locator('.toast');
  await expect(toast).toBeVisible();
  await expect(toast.getByRole('button', { name: 'Undo' })).toBeVisible();
  await expect(toast).toBeHidden({ timeout: 3500 });
});

test('the card can be operated with the keyboard alone', async ({ page }) => {
  await open(page);
  const pick = page.locator('.city-card__pick').first();
  await pick.focus();
  await page.keyboard.press('Tab'); // moves to this card's Scout button
  await expect(page.locator('.city-card__scout').first()).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('.city-card').first()).toHaveAttribute('data-flipped', 'true');
});

/** The flip duration token in milliseconds (the build writes 200ms as .2s, so read the unit). */
const flipMs = (page: Page): Promise<number> =>
  page.evaluate(() => {
    const raw = getComputedStyle(document.documentElement).getPropertyValue('--dur-flip').trim();
    return raw.endsWith('ms') ? parseFloat(raw) : parseFloat(raw) * 1000;
  });

test('reduced motion removes the flip and press animations', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await open(page);
  expect(await flipMs(page)).toBe(0);
});

test('the in-app motion override works without the system setting', async ({ page }) => {
  await open(page);
  expect(await flipMs(page)).toBe(200);
  await page.getByRole('group', { name: 'Motion' }).getByRole('button', { name: 'reduce' }).click();
  expect(await flipMs(page)).toBe(0);
  await page.getByRole('group', { name: 'Motion' }).getByRole('button', { name: 'full' }).click();
  expect(await flipMs(page)).toBe(200);
});

test('pattern mode puts patterns on the four loss swatches and not on the others', async ({
  page,
}) => {
  await open(page);
  const imageOf = (cls: string): Promise<string> =>
    page
      .locator(`.sg-legend .swatch.${cls}`)
      .evaluate((el) => getComputedStyle(el).backgroundImage);
  expect(await imageOf('day-r')).toBe('none');
  await page.getByRole('group', { name: 'Patterns' }).getByRole('button', { name: 'on' }).click();
  for (const cls of ['day-r', 'day-s', 'day-h', 'day-f']) {
    expect(await imageOf(cls)).not.toBe('none');
  }
  for (const cls of ['day-p', 'day-o']) expect(await imageOf(cls)).toBe('none');
});

test('system dark mode and the data-theme override both apply', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await open(page);
  const bg = (): Promise<string> =>
    page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  const dark = await bg();
  await page.getByRole('group', { name: 'Theme' }).getByRole('button', { name: 'light' }).click();
  expect(await bg()).not.toBe(dark);
});

test('the grid redraws when more tiles are revealed', async ({ page }) => {
  await open(page);
  const snapshot = (): Promise<string> =>
    page.locator('canvas').evaluate((c) => (c as HTMLCanvasElement).toDataURL());
  const full = await snapshot();
  await page.locator('#sg-reveal').fill('100');
  expect(await snapshot()).not.toBe(full);
});
