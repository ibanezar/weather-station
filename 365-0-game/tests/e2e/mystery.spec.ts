import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { localDate } from '../../src/app/dates.ts';
import { puzzleFor, type MysteryFile, type Puzzle } from '../../src/engine/mystery.ts';
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

/** Today's puzzle, worked out the same way the game does. */
const puzzle = (): Puzzle => puzzleFor(file, localDate());
const choice = (page: Page, id: string) =>
  page.locator('.mystery__choice').filter({ has: page.getByText(nameOf(id), { exact: true }) });
const openMystery = async (page: Page): Promise<void> => {
  await page.getByRole('button', { name: 'Daily mystery' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Where was this?' })).toBeVisible();
  await expect(page.locator('.mystery__choice')).toHaveCount(3);
};

test.describe('the daily mystery', () => {
  test('starts with one clue and three cities, and the right guess scores 4', async ({ page }) => {
    const errors = await openReturning(page);
    await openMystery(page);
    await expect(page.locator('.mystery__clue')).toHaveCount(1);
    await expect(page.locator('.mystery__clue').first()).toContainText('Temperature');
    await expect(page.getByText(/Worth 4 points/)).toBeVisible();
    const p = puzzle();
    for (const id of [p.city, ...p.decoys]) await expect(choice(page, id)).toBeVisible();

    await choice(page, p.city).click();
    await expect(page.getByRole('heading', { name: 'Correct!' })).toBeVisible();
    await expect(page.getByText('4 of 4 points')).toBeVisible();
    await expect(page.locator('.mystery__clue')).toHaveCount(4); // everything is shown at the end
    await expect(page.locator('.mystery__usual li')).toHaveCount(3);
    await expect(page.locator('.mystery__usual .is-answer')).toContainText(nameOf(p.city));
    await expect(page.locator('.mystery__choice:not([disabled])')).toHaveCount(0);

    // It is locked for the day: reopening shows the same result.
    await page.reload();
    await expect(page.getByText('4 of 4 points')).toBeVisible();
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Daily mystery: see result' })).toBeVisible();
    expect(errors).toEqual([]);
  });

  test('a clue costs a point, a wrong guess shows the next clue', async ({ page }) => {
    await openReturning(page);
    await openMystery(page);
    const p = puzzle();
    await page.getByRole('button', { name: /Show another clue/ }).click();
    await expect(page.locator('.mystery__clue')).toHaveCount(2);
    await expect(page.getByText(/Worth 3 points/)).toBeVisible();

    await choice(page, p.decoys[0]).click();
    await expect(page.locator('.mystery__clue')).toHaveCount(3);
    await expect(choice(page, p.decoys[0])).toBeDisabled();
    await expect(choice(page, p.decoys[0])).toContainText('Not this one');
    await expect(page.getByText(/Worth 2 points/)).toBeVisible();

    await choice(page, p.city).click();
    await expect(page.getByText('2 of 4 points')).toBeVisible();
  });

  test('two wrong guesses end it with no points and show the answer', async ({ page }) => {
    await openReturning(page);
    await openMystery(page);
    const p = puzzle();
    await choice(page, p.decoys[0]).click();
    await choice(page, p.decoys[1]).click();
    await expect(
      page.getByRole('heading', { name: `Not this time. It was ${nameOf(p.city)}.` }),
    ).toBeVisible();
    await expect(page.getByText('0 of 4 points')).toBeVisible();
    await expect(choice(page, p.city)).toHaveClass(/is-answer/);
  });

  test('a puzzle in progress is still in progress after a reload, with the clues and crossed-out cities', async ({
    page,
  }) => {
    await openReturning(page);
    await openMystery(page);
    const p = puzzle();
    await page.getByRole('button', { name: /Show another clue/ }).click();
    await choice(page, p.decoys[1]).click();
    await page.reload();
    await expect(page.locator('.mystery__clue')).toHaveCount(3);
    await expect(choice(page, p.decoys[1])).toBeDisabled();
    await expect(choice(page, p.city)).toBeEnabled();
  });

  test('shows up in Statistics and the streak, and Reset progress clears it', async ({ page }) => {
    await openReturning(page);
    await openMystery(page);
    await choice(page, puzzle().city).click();
    await page.goto('/#/stats');
    const tiles = page.locator('.stats__tile');
    await expect(tiles.filter({ hasText: 'Mysteries played' }).locator('.stats__value')).toHaveText(
      '1',
    );
    await expect(tiles.filter({ hasText: 'Mystery average' }).locator('.stats__value')).toHaveText(
      '4',
    );
    await page.goto('/#/settings');
    await page.getByRole('button', { name: /Reset progress/ }).click();
    await page
      .getByRole('button', { name: /^Reset/ })
      .last()
      .click();
    await page.goto('/#/mystery');
    await expect(page.locator('.mystery__clue')).toHaveCount(1);
  });

  test('speaks Slovene', async ({ page }) => {
    await openReturning(page, { settings: { language: 'sl' } });
    await page.getByRole('button', { name: 'Dnevna uganka' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Kje je bilo to?' })).toBeVisible();
    await expect(page.getByText(/Vredno 4 točke/)).toBeVisible();
    await expect(page.getByText('Temperatura')).toBeVisible();
  });

  test('has no serious axe violations and does not overflow at 360 px, while playing and at the end', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 360, height: 780 });
    await openReturning(page);
    await openMystery(page);
    const overflow = (): Promise<number> =>
      page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
    expect(await seriousViolations(page)).toEqual([]);
    expect(await overflow()).toBeLessThanOrEqual(0);
    await choice(page, puzzle().city).click();
    await page.getByText(/of 4 points/).waitFor();
    expect(await seriousViolations(page)).toEqual([]);
    expect(await overflow()).toBeLessThanOrEqual(0);
  });
});

test.describe('the daily mystery without its data', () => {
  test.use({ serviceWorkers: 'block' });
  test('says so, offers a retry, and works once the file is back', async ({ page }) => {
    let fail = true;
    await page.route('**/data/mystery.v1.json', (route) =>
      fail ? route.abort() : route.continue(),
    );
    await openReturning(page);
    await page.getByRole('button', { name: 'Daily mystery' }).click();
    await expect(page.getByText('The puzzle could not be loaded.')).toBeVisible();
    fail = false;
    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(page.locator('.mystery__choice')).toHaveCount(3);
  });
});
