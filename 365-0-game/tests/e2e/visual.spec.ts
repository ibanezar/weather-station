import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { localDate } from '../../src/app/dates.ts';
import { puzzleFor, type MysteryFile } from '../../src/engine/mystery.ts';
import { openReturning, seriousViolations } from './helpers.ts';

const root = join(import.meta.dirname, '../..');
const file = JSON.parse(
  readFileSync(join(root, 'public/data/mystery.v1.json'), 'utf8'),
) as MysteryFile;
const cities = JSON.parse(readFileSync(join(root, 'data/cities.seed.json'), 'utf8')) as {
  id: string;
  name: { en: string };
}[];
const nameOf = (id: string): string => cities.find((c) => c.id === id)?.name.en ?? id;
const primaryColor = (page: Page): Promise<string> =>
  page
    .getByRole('button', { name: /^Play daily/ })
    .evaluate((el) => getComputedStyle(el).backgroundColor);

test.describe('the picture of a month on a city card', () => {
  test('every card has ten bars, one per year, each covering the whole month', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card').first().waitFor();
    await expect(page.locator('.city-card')).toHaveCount(3);
    await expect(page.locator('.year-strip__bar')).toHaveCount(30);
    const monthDays = await page
      .locator('.city-card')
      .first()
      .evaluate((card) => {
        const bar = card.querySelector('.year-strip__bar');
        return [...(bar?.children ?? [])].reduce(
          (n, seg) => n + Number(getComputedStyle(seg).flexGrow),
          0,
        );
      });
    expect(monthDays).toBe(31); // the first round is January: a bar covers the whole month
  });

  test('the bars follow what you chase: wins first, then draws, then losses', async ({ page }) => {
    await openReturning(page, { settings: { chase: 'snow' } });
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card').first().waitFor();
    // For snow, freezing days win, hot and perfect days lose and everything else is a draw.
    const sequences = await page.locator('.year-strip__bar').evaluateAll((bars) =>
      bars.map((bar) =>
        [...bar.children].map((seg) => {
          const type = /day-([a-z])/.exec(seg.className)?.[1] ?? '';
          return type === 'f' ? 0 : type === 'h' || type === 'p' ? 2 : 1;
        }),
      ),
    );
    expect(sequences).toHaveLength(30);
    for (const seq of sequences) expect(seq).toEqual([...seq].sort((a, b) => a - b));
    await expect(page.getByText(/The bars are ten real years/)).toBeVisible();
  });
});

test.describe('the colour of what you chase', () => {
  test('buttons take the colour of the chase, and the mystery keeps gold', async ({ page }) => {
    await openReturning(page);
    await expect(page.locator('html')).toHaveAttribute('data-chase', 'sun');
    const gold = await primaryColor(page);
    await page.getByRole('radio', { name: /Rain/ }).check();
    await expect(page.locator('html')).toHaveAttribute('data-chase', 'rain');
    expect(await primaryColor(page)).not.toBe(gold);
    await page.getByRole('radio', { name: /Heat/ }).check();
    expect(await primaryColor(page)).not.toBe(gold);

    await page.getByRole('button', { name: 'Daily mystery' }).click();
    await page.locator('.mystery__choice').first().waitFor();
    await expect(page.locator('html')).toHaveAttribute('data-chase', 'sun');
    await page.getByRole('button', { name: 'Back' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-chase', 'heat'); // the choice was remembered
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-chase', 'heat');
  });
});

test.describe('the pictures of the mystery', () => {
  test('clues come with pictures, the end with a dot map of the three cities', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Daily mystery' }).click();
    await page.locator('.mystery__choice').first().waitFor();
    for (let i = 0; i < 3; i++)
      await page.getByRole('button', { name: /Show another clue/ }).click();
    await expect(page.locator('.mystery__clue')).toHaveCount(4);
    await expect(page.locator('.viz--range')).toHaveCount(1);
    await expect(page.locator('.viz--dial')).toHaveCount(1);
    expect(await page.locator('.viz--fill').count()).toBeGreaterThanOrEqual(2); // cloud and wind at least
    await expect(page.locator('.mystery__map')).toHaveCount(0); // the map would be a spoiler of nothing, but it belongs to the end

    const p = puzzleFor(file, localDate());
    await page
      .locator('.mystery__choice')
      .filter({ has: page.getByText(nameOf(p.city), { exact: true }) })
      .click();
    const map = page.locator('canvas.mystery__map');
    await expect(map).toBeVisible();
    await expect(map).toHaveAttribute('aria-label', /Map of the three cities: 1 .*, 2 .*, 3 /);
    await expect(page.locator('.mystery__n')).toHaveCount(3);
    // The canvas is really painted: it has dots in it.
    const painted = await map.evaluate((c: HTMLCanvasElement) => {
      const ctx = c.getContext('2d');
      if (!ctx) return 0;
      const data = ctx.getImageData(0, 0, c.width, c.height).data;
      let n = 0;
      for (let i = 3; i < data.length; i += 4) if ((data[i] ?? 0) > 0) n += 1;
      return n;
    });
    expect(painted).toBeGreaterThan(500);
  });
});

test.describe('the calendar in Statistics', () => {
  test('shows twelve weeks, marks the days played, and passes axe', async ({ page }) => {
    const d = new Date();
    const iso = (back: number): string => {
      const x = new Date(d);
      x.setDate(x.getDate() - back);
      return `${String(x.getFullYear())}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
    };
    const run = { picks: [], record: { w: 100, d: 150, l: 115 }, grade: 'sun-chaser' };
    await openReturning(page, {
      daily: { [iso(1)]: run, [iso(2)]: run },
      mystery: { [iso(1)]: { guesses: ['x'], revealed: 1, points: 4, done: true } },
    });
    await page.goto('/#/stats');
    const cal = page.locator('.stats__cal');
    await expect(cal).toBeVisible();
    await expect(page.locator('.stats__day')).toHaveCount(84);
    await expect(cal).toHaveAttribute('aria-label', /^2 of the last \d+ days played$/);
    await expect(page.locator('.stats__day[data-n="2"]')).toHaveCount(1);
    await expect(page.locator('.stats__day[data-n="1"]')).toHaveCount(1);
    expect(await seriousViolations(page)).toEqual([]);
  });
});
