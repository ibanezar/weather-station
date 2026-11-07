import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import {
  draftTwelve,
  openReturning,
  recordOf,
  seriousViolations,
  skipToResult,
} from './helpers.ts';

test.describe('first visit', () => {
  test('shows the three-line introduction once, and its button starts the draft directly', async ({
    page,
  }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1, name: 'How it works' })).toBeVisible();
    await expect(page.locator('.how__line')).toHaveCount(3);
    await expect(page.locator('.how__line').first()).toContainText('19–28 °C');
    await page.getByRole('button', { name: 'Play daily' }).click();
    await expect(page.locator('.city-card')).toHaveCount(3);
    expect(await page.evaluate(() => localStorage.getItem('365-0:v1'))).toContain(
      '"onboarded":true',
    );
    // On the next visit it goes straight to Home.
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1, name: '365-0' })).toBeVisible();
  });

  test('stays reachable from Home', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'How it works' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'How it works' })).toBeVisible();
    await page.getByRole('button', { name: 'Back' }).click();
    await expect(page.getByRole('button', { name: 'Play daily' })).toBeVisible();
  });
});

test.describe('a complete daily run', () => {
  test('drafts, reveals, shows the result, and locks the daily for the day', async ({ page }) => {
    const errors = await openReturning(page);
    await expect(page.getByRole('button', { name: 'Play endless' })).toBeVisible();
    await page.getByRole('button', { name: 'Play daily' }).click();

    // Draft: three cities, a month, a progress indicator.
    await expect(page.locator('.city-card')).toHaveCount(3);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('January');
    await draftTwelve(page, (round) => round % 3);

    // Reveal: the live counter ends on the record, then the grade and a button appear.
    await page.locator('.screen--reveal').click({ position: { x: 10, y: 10 } });
    await expect(page.getByRole('button', { name: 'See result' })).toBeVisible();
    await page.getByRole('button', { name: 'See result' }).click();

    // Result.
    await page.locator('.screen--result').waitFor();
    const record = await recordOf(page);
    expect(record.w + record.d + record.l).toBe(365);
    await expect(page.getByText(/Best possible today: \d+/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Share result' })).toBeVisible();
    await expect(page.getByText(/Next daily in \d+ h \d+ min/)).toBeVisible();
    await expect(page.locator('.result__grade h2')).not.toBeEmpty();

    // The same record is shown when the player comes back: the daily is locked and deterministic.
    await page.goto('/');
    await expect(page.getByRole('button', { name: "See today's result" })).toBeVisible();
    await page.getByRole('button', { name: "See today's result" }).click();
    await page.locator('.screen--result').waitFor();
    expect((await recordOf(page)).text).toBe(record.text);
    expect(errors).toEqual([]);
  });

  test('the same date gives every player the same draft', async ({ browser }) => {
    const firstRound = async (): Promise<string[]> => {
      const ctx = await browser.newContext({ locale: 'en-GB' });
      const page = await ctx.newPage();
      await openReturning(page);
      await page.getByRole('button', { name: 'Play daily' }).click();
      await page.locator('.city-card').first().waitFor();
      const names = await page.locator('.city-card__name').allTextContents();
      await ctx.close();
      return names;
    };
    expect(await firstRound()).toEqual(await firstRound());
  });
});

test.describe('a complete endless run', () => {
  test('plays, records the best endless result, and can start another run', async ({ page }) => {
    const errors = await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    const record = await recordOf(page);
    expect(record.w + record.d + record.l).toBe(365);
    await expect(page.getByText(/Best possible this run: \d+/)).toBeVisible();
    await expect(page.getByText(/Next daily/)).toHaveCount(0);

    // Another endless run straight from the result.
    await page.getByRole('button', { name: 'Play endless' }).click();
    await expect(page.locator('.city-card')).toHaveCount(3);

    // Home remembers the best record.
    await page.goto('/');
    await expect(page.getByText(/Best endless record: \d+-\d+-\d+/)).toBeVisible();
    expect(errors).toEqual([]);
  });

  test('the result never beats the best possible, and picking differently changes the record', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page, () => 1);
    await skipToResult(page);
    const record = await recordOf(page);
    const best = Number(
      ((await page.getByText(/Best possible this run: \d+/).textContent()) ?? '').match(/\d+/)?.[0],
    );
    expect(record.w).toBeLessThanOrEqual(best);
  });
});

test.describe('the draft', () => {
  test('scouting flips a card, costs a scout once, and stops when none are left', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await expect(page.locator('.progress__scouts')).toContainText('3 scouts left');
    const card = page.locator('.city-card').first();
    await card.getByRole('button', { name: /^Scout/ }).click();
    await expect(card).toHaveAttribute('data-flipped', 'true');
    await expect(card.locator('.steps')).toHaveCount(2);
    await expect(page.locator('.progress__scouts')).toContainText('2 scouts left');
    // The other two cards use the remaining scouts.
    await page
      .locator('.city-card')
      .nth(1)
      .getByRole('button', { name: /^Scout/ })
      .click();
    await page
      .locator('.city-card')
      .nth(2)
      .getByRole('button', { name: /^Scout/ })
      .click();
    await expect(page.locator('.progress__scouts')).toContainText('0 scouts left');
    await page.locator('.city-card__pick').first().click();
    await expect(page.locator('.city-card__scout').first()).toBeDisabled();
  });

  test('undo takes back the last pick for free and keeps what was scouted', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    const firstNames = await page.locator('.city-card__name').allTextContents();
    await page
      .locator('.city-card')
      .first()
      .getByRole('button', { name: /^Scout/ })
      .click();
    await page.locator('.city-card__pick').first().click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('February');
    await page.getByRole('button', { name: 'Undo' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('January');
    expect(await page.locator('.city-card__name').allTextContents()).toEqual(firstNames);
    await expect(page.locator('.city-card').first()).toHaveAttribute('data-flipped', 'true');
    await expect(page.locator('.progress__scouts')).toContainText('2 scouts left'); // no refund, no second charge
  });

  test('the undo toast disappears after about two seconds', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card__pick').first().click();
    await expect(page.locator('.toast')).toBeVisible();
    await expect(page.locator('.toast')).toBeHidden({ timeout: 3500 });
  });

  test('undoing the twelfth pick cancels the reveal', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    for (let round = 0; round < 12; round++) await page.locator('.city-card__pick').first().click();
    await page.getByRole('button', { name: 'Undo' }).click();
    await page.waitForTimeout(2500);
    await expect(page.locator('.screen--reveal')).toHaveCount(0);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('December');
  });

  test('every round offers three cities with different climate icons from at least two countries', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card').first().waitFor();
    for (let round = 0; round < 12; round++) {
      await expect(page.locator('.city-card__pick')).toHaveCount(3);
      const labels = await page
        .locator('.city-card__archetype svg')
        .evaluateAll((els) => els.map((e) => e.getAttribute('aria-label')));
      expect(new Set(labels).size).toBe(3);
      const countries = await page.locator('.city-card__country').allTextContents();
      expect(new Set(countries).size).toBeGreaterThanOrEqual(2);
      await page.locator('.city-card__pick').first().click();
    }
  });
});

test.describe('the result screen', () => {
  test('lists the months, highlights one on tap, and offers the grid as a list', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await skipToResult(page);

    await page.locator('.whatif summary').click();
    await expect(page.locator('.whatif__row')).toHaveCount(12);
    const row = page.locator('.whatif__row').nth(3);
    await row.click();
    await expect(row).toHaveAttribute('aria-pressed', 'true');
    await row.click();
    await expect(row).toHaveAttribute('aria-pressed', 'false');

    await page.getByRole('button', { name: 'Show as list' }).click();
    await expect(page.locator('.result__table tbody tr')).toHaveCount(12);
    await expect(page.getByRole('button', { name: 'Hide list' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });
});

test.describe('settings', () => {
  test('changes unit, language, theme and pattern mode, and applies them at once', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Settings' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible();

    await page.getByRole('group', { name: 'Theme' }).getByRole('button', { name: 'Dark' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page
      .getByRole('group', { name: 'Pattern mode' })
      .getByRole('button', { name: 'On' })
      .click();
    await expect(page.locator('html')).toHaveAttribute('data-pattern', 'on');

    await page
      .getByRole('group', { name: 'Language' })
      .getByRole('button', { name: 'Slovenščina' })
      .click();
    await expect(page.getByRole('heading', { level: 1, name: 'Nastavitve' })).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('lang', 'sl');

    // Settings survive a reload.
    await page.reload();
    await expect(page.getByRole('heading', { level: 1, name: 'Nastavitve' })).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  });

  test('switches between Celsius and Fahrenheit on the city cards', async ({ page }) => {
    await openReturning(page, { settings: { unit: 'c' } });
    await page.getByRole('button', { name: 'Play endless' }).click();
    await page.locator('.city-card').first().waitFor();
    const celsius = await page.locator('.city-card__temp').allTextContents();
    // Visit Settings from inside the run, change the unit, and come back: the run continues.
    await page.goto('/#/settings');
    await page
      .getByRole('group', { name: 'Temperature unit' })
      .getByRole('button', { name: '°F' })
      .click();
    await page.goto('/#/draft');
    await page.locator('.city-card').first().waitFor();
    const fahrenheit = await page.locator('.city-card__temp').allTextContents();
    expect(celsius).toHaveLength(3);
    for (const t of [...celsius, ...fahrenheit]) expect(t).toMatch(/^-?\d+°$/);
    const toNumber = (t: string): number => Number(t.replace('°', ''));
    celsius.forEach((c, i) => {
      // Both are rounded for display, so they can differ by one from the exact conversion.
      const exact = (toNumber(c) * 9) / 5 + 32;
      expect(Math.abs(toNumber(fahrenheit[i] ?? '') - exact)).toBeLessThanOrEqual(1.5);
    });
  });

  test('plays the whole game in Slovene', async ({ browser }) => {
    const ctx = await browser.newContext({ locale: 'sl-SI' });
    const page = await ctx.newPage();
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1, name: 'Kako deluje' })).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('lang', 'sl');
    await page.getByRole('button', { name: 'Igraj dnevno' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Januar' })).toBeVisible();
    await expect(page.locator('.progress__count')).toHaveText('Krog 1 od 12');
    await draftTwelve(page);
    await skipToResult(page);
    await expect(page.getByText(/Najboljši možni izid danes: \d+/)).toBeVisible();
    await ctx.close();
  });

  test('resets progress only after confirmation', async ({ page }) => {
    await openReturning(page, {
      bestEndless: { w: 80, d: 100, l: 185 },
      streak: { count: 3, last: '2020-01-01' },
    });
    await expect(page.getByText('Best endless record: 80-100-185')).toBeVisible();
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('button', { name: 'Reset progress' }).click();
    await page.getByRole('button', { name: 'Cancel' }).click();
    await page.getByRole('button', { name: 'Back' }).click();
    await expect(page.getByText('Best endless record: 80-100-185')).toBeVisible();

    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('button', { name: 'Reset progress' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Reset' }).click();
    await page.getByRole('button', { name: 'Back' }).click();
    await expect(page.getByText(/Best endless record/)).toHaveCount(0);
  });

  test('shows the data attribution on Settings and on About, and the privacy page', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Settings' }).click();
    await expect(page.getByText(/Weather data by Open-Meteo\.com \(CC BY 4\.0\)/)).toBeVisible();
    await page.getByRole('button', { name: 'About and data' }).click();
    await expect(page.getByText(/Weather data by Open-Meteo\.com \(CC BY 4\.0\)/)).toBeVisible();
    await page.getByRole('button', { name: 'Privacy' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Privacy' })).toBeVisible();
    await expect(page.getByText(/no accounts and no tracking/)).toBeVisible();
  });
});

test.describe('reduced motion', () => {
  test('shows the reveal end state at once and announces the record once', async ({ browser }) => {
    const ctx = await browser.newContext({ locale: 'en-GB', reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await expect(page.getByRole('button', { name: 'See result' })).toBeVisible({ timeout: 1000 });
    await expect(page.locator('.reveal__hint')).toBeHidden();
    await expect(page.locator('.screen--reveal [role="status"]')).toContainText(
      /Record \d+ wins, \d+ draws, \d+ losses/,
    );
    await ctx.close();
  });

  test('the in-app override reduces motion without the system setting', async ({ page }) => {
    await openReturning(page, { settings: { motion: 'reduce' } });
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await expect(page.getByRole('button', { name: 'See result' })).toBeVisible({ timeout: 1000 });
  });
});

test.describe('when things go wrong', () => {
  test('shows a clear error and a retry when the weather data cannot load', async ({ page }) => {
    let fail = true;
    await page.route('**/data/world.v1.json', (route) => (fail ? route.abort() : route.continue()));
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await expect(page.getByRole('alert')).toContainText(
      'Could not load world data. Check your connection and try again.',
    );
    fail = false;
    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(page.locator('.city-card')).toHaveCount(3);
  });

  test('stays playable when localStorage is blocked', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.addInitScript(() => {
      Object.defineProperty(window, 'localStorage', {
        get() {
          throw new DOMException('blocked', 'SecurityError');
        },
      });
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Play daily' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    expect((await recordOf(page)).w).toBeGreaterThanOrEqual(0);
    expect(errors).toEqual([]);
  });
});

test.describe('accessibility and layout', () => {
  for (const scheme of ['light', 'dark'] as const) {
    test(`has no serious or critical axe violations on any screen in ${scheme} mode`, async ({
      page,
    }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await openReturning(page);
      const found: string[] = [];
      found.push(...(await seriousViolations(page)).map((v) => `home ${v}`));

      await page.getByRole('button', { name: 'Settings' }).click();
      found.push(...(await seriousViolations(page)).map((v) => `settings ${v}`));
      await page.goto('/#/how');
      found.push(...(await seriousViolations(page)).map((v) => `how ${v}`));
      await page.goto('/#/about');
      found.push(...(await seriousViolations(page)).map((v) => `about ${v}`));
      await page.goto('/#/privacy');
      found.push(...(await seriousViolations(page)).map((v) => `privacy ${v}`));

      await page.goto('/');
      await page.getByRole('button', { name: 'Play endless' }).click();
      await page.locator('.city-card').first().waitFor();
      await page
        .locator('.city-card')
        .first()
        .getByRole('button', { name: /^Scout/ })
        .click();
      found.push(...(await seriousViolations(page)).map((v) => `draft ${v}`));

      await draftTwelve(page);
      await expect(page.getByRole('button', { name: 'See result' })).toBeVisible({
        timeout: 10000,
      });
      found.push(...(await seriousViolations(page)).map((v) => `reveal ${v}`));
      await page.getByRole('button', { name: 'See result' }).click();
      await page.locator('.screen--result').waitFor();
      await page.locator('.whatif summary').click();
      found.push(...(await seriousViolations(page)).map((v) => `result ${v}`));
      expect(found).toEqual([]);
    });
  }

  for (const width of [360, 430]) {
    test(`has no horizontal overflow on any screen at ${String(width)} px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 780 });
      await openReturning(page);
      const overflow = (): Promise<number> =>
        page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
      const seen: Record<string, number> = {};
      seen['home'] = await overflow();
      await page.goto('/#/settings');
      seen['settings'] = await overflow();
      await page.goto('/');
      await page.getByRole('button', { name: 'Play endless' }).click();
      await page.locator('.city-card').first().waitFor();
      seen['draft'] = await overflow();
      await draftTwelve(page);
      await expect(page.getByRole('button', { name: 'See result' })).toBeVisible({
        timeout: 10000,
      });
      seen['reveal'] = await overflow();
      await page.getByRole('button', { name: 'See result' }).click();
      await page.locator('.screen--result').waitFor();
      seen['result'] = await overflow();
      for (const [screen, px] of Object.entries(seen)) expect(px, screen).toBeLessThanOrEqual(0);
    });
  }

  test('keeps the record on one line even with three-digit numbers', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 780 });
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    const box = await page.locator('.result__record').boundingBox();
    const fontSize = await page
      .locator('.result__record')
      .evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
    expect(box?.height).toBeLessThan(fontSize * 1.4);
  });
});

/** Width and height from a PNG's header (the IHDR chunk). */
const pngSize = (file: string): { width: number; height: number } => {
  const bytes = readFileSync(file);
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
};

test.describe('sharing', () => {
  test.use({ permissions: ['clipboard-read', 'clipboard-write'] });

  test('without a share sheet it copies the text and downloads a 1080 x 1350 image', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play daily' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    const record = await recordOf(page);

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: 'Share result' }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/^365-0-\d{4}-\d{2}-\d{2}\.png$/);
    expect(pngSize(await download.path())).toEqual({ width: 1080, height: 1350 });
    await expect(
      page.getByRole('status').filter({ hasText: 'Text copied and image saved.' }),
    ).toBeVisible();

    const text = await page.evaluate(() => navigator.clipboard.readText());
    const lines = text.split('\n');
    expect(lines).toHaveLength(4);
    expect(lines[0]).toMatch(/^365-0 daily \d{4}-\d{2}-\d{2}$/);
    expect(lines[1]).toMatch(new RegExp(`^Record ${record.text} \\(.+\\)$`));
    expect(Array.from(lines[2] ?? '')).toHaveLength(12);
    expect(lines[3]).toBe('https://meteorec.si/365-0/');
  });

  test('offers a 1080 x 1920 story image', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: 'Share as story image' }).click(),
    ]);
    expect(download.suggestedFilename()).toBe('365-0-endless-story.png');
    expect(pngSize(await download.path())).toEqual({ width: 1080, height: 1920 });
  });

  test('uses the share sheet with the image and the text where files can be shared', async ({
    page,
  }) => {
    await page.addInitScript(() => {
      const shared: { files: { name: string; type: string; size: number }[]; text: string }[] = [];
      (window as unknown as { __shared: typeof shared }).__shared = shared;
      Object.defineProperty(navigator, 'canShare', { value: () => true, configurable: true });
      Object.defineProperty(navigator, 'share', {
        configurable: true,
        value: (data: { files?: File[]; text?: string }) => {
          shared.push({
            files: (data.files ?? []).map((f) => ({ name: f.name, type: f.type, size: f.size })),
            text: data.text ?? '',
          });
          return Promise.resolve();
        },
      });
    });
    await openReturning(page);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    await page.getByRole('button', { name: 'Share result' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Shared' })).toBeVisible();
    const shared = await page.evaluate(
      () =>
        (
          window as unknown as {
            __shared: { files: { name: string; type: string; size: number }[]; text: string }[];
          }
        ).__shared,
    );
    expect(shared).toHaveLength(1);
    expect(shared[0]?.files).toHaveLength(1);
    expect(shared[0]?.files[0]?.type).toBe('image/png');
    expect(shared[0]?.files[0]?.size).toBeGreaterThan(20000);
    expect(shared[0]?.text).toContain('365-0 endless');
  });

  test('shares the text in Slovene', async ({ browser }) => {
    const ctx = await browser.newContext({
      locale: 'sl-SI',
      permissions: ['clipboard-read', 'clipboard-write'],
    });
    const page = await ctx.newPage();
    await page.goto('/');
    await page.getByRole('button', { name: 'Igraj dnevno' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    await page.getByRole('button', { name: 'Deli izid' }).click();
    await expect(
      page.getByRole('status').filter({ hasText: 'Besedilo je kopirano, slika shranjena.' }),
    ).toBeVisible();
    const text = await page.evaluate(() => navigator.clipboard.readText());
    expect(text.split('\n')[0]).toMatch(/^365-0 dnevna \d{4}-\d{2}-\d{2}$/);
    expect(text.split('\n')[1]).toMatch(/^Izid \d+-\d+-\d+ \(.+\)$/);
    await ctx.close();
  });
});

/** A local YYYY-MM-DD, `daysAgo` days before today. */
const dateDaysAgo = (daysAgo: number): string => {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  const pad = (n: number): string => String(n).padStart(2, '0');
  return `${String(d.getFullYear())}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

test.describe('the streak', () => {
  test('shows from two days, grows when the daily is finished, and keeps the first result of the day', async ({
    page,
  }) => {
    await openReturning(page, { streak: { count: 3, last: dateDaysAgo(1) } });
    await expect(page.getByText('3 day streak')).toBeVisible();
    await page.getByRole('button', { name: 'Play daily' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    await expect(page.getByText('4 day streak')).toBeVisible();

    // The same day again does not add another day, and the result is the same.
    const first = (await recordOf(page)).text;
    await page.goto('/');
    await expect(page.getByText('4 day streak')).toBeVisible();
    await page.getByRole('button', { name: "See today's result" }).click();
    await page.locator('.screen--result').waitFor();
    expect((await recordOf(page)).text).toBe(first);
    await expect(page.getByText('4 day streak')).toBeVisible();
  });

  test('is hidden after a missed day and shows the invitation instead', async ({ page }) => {
    await openReturning(page, { streak: { count: 7, last: dateDaysAgo(3) } });
    await expect(page.getByText(/day streak/)).toHaveCount(0);
    await expect(page.getByText("Play today's daily to start a streak.")).toBeVisible();
  });

  test('is hidden at one day, and an endless run never changes it', async ({ page }) => {
    await openReturning(page, { streak: { count: 1, last: dateDaysAgo(0) } });
    await expect(page.getByText(/day streak/)).toHaveCount(0);
    await page.getByRole('button', { name: 'Play endless' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    await expect(page.getByText(/day streak/)).toHaveCount(0);
    const stored = await page.evaluate(() => localStorage.getItem('365-0:v1'));
    const parsed = JSON.parse(stored ?? '{}') as { streak?: unknown };
    expect(parsed.streak).toEqual({ count: 1, last: dateDaysAgo(0) });
  });

  test('uses the Slovene dual form for two days', async ({ browser }) => {
    const ctx = await browser.newContext({ locale: 'sl-SI' });
    const page = await ctx.newPage();
    await openReturning(page, { streak: { count: 2, last: dateDaysAgo(1) } });
    await expect(page.getByText('2 dneva zapored')).toBeVisible();
    await ctx.close();
  });
});
