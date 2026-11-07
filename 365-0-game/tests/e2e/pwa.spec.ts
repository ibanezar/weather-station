import { expect, test, type Page } from '@playwright/test';
import { draftTwelve, openReturning, recordOf, skipToResult } from './helpers.ts';

/** Wait until the service worker controls the page (it claims clients once it has installed). */
async function waitForServiceWorker(page: Page): Promise<void> {
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
    if (!navigator.serviceWorker.controller) {
      await new Promise<void>((resolve) => {
        navigator.serviceWorker.addEventListener('controllerchange', () => {
          resolve();
        });
      });
    }
  });
}

test.describe('manifest and page head', () => {
  test('has a complete web app manifest whose icons exist', async ({ page, request }) => {
    await page.goto('/');
    const href = await page.locator('link[rel="manifest"]').getAttribute('href');
    expect(href).toBeTruthy();
    const manifestUrl = new URL(href ?? '', page.url()).toString();
    const manifest = (await (await request.get(manifestUrl)).json()) as {
      name: string;
      start_url: string;
      scope: string;
      display: string;
      orientation: string;
      icons: { src: string; sizes: string; purpose?: string }[];
    };
    expect(manifest.name).toBe('365-0');
    expect(manifest.display).toBe('standalone');
    expect(manifest.orientation).toBe('portrait');
    expect(manifest.start_url).toBe('./');
    expect(manifest.icons.some((i) => i.sizes === '192x192')).toBe(true);
    expect(manifest.icons.some((i) => i.sizes === '512x512' && i.purpose === 'maskable')).toBe(
      true,
    );
    for (const icon of manifest.icons) {
      const res = await request.get(new URL(icon.src, manifestUrl).toString());
      expect(res.status(), icon.src).toBe(200);
      expect(res.headers()['content-type']).toContain('image/png');
    }
  });

  test('declares theme colours, a description and the touch icon', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('meta[name="theme-color"]')).toHaveCount(2);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute(
      'content',
      /twelve world cities/,
    );
    await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveCount(1);
    await expect(page.locator('meta[name="viewport"]')).toHaveAttribute(
      'content',
      /viewport-fit=cover/,
    );
  });

  test('preloads the display font and the UI regular weight', async ({ page }) => {
    await page.goto('/');
    const hrefs = await page
      .locator('link[rel="preload"][as="font"]')
      .evaluateAll((els) => els.map((e) => e.getAttribute('href') ?? ''));
    expect(hrefs).toHaveLength(2);
    expect(hrefs.some((h) => h.includes('big-shoulders-display-latin-wght'))).toBe(true);
    expect(hrefs.some((h) => h.includes('instrument-sans-latin-wght'))).toBe(true);
  });

  test('the status bar colour follows the chosen theme', async ({ page }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Settings' }).click();
    const colors = (): Promise<string[]> =>
      page
        .locator('meta[name="theme-color"]')
        .evaluateAll((els) => els.map((e) => e.getAttribute('content') ?? ''));
    await page.getByRole('group', { name: 'Theme' }).getByRole('button', { name: 'Dark' }).click();
    expect(await colors()).toEqual(['#0e1624', '#0e1624']);
    await page.getByRole('group', { name: 'Theme' }).getByRole('button', { name: 'Light' }).click();
    expect(await colors()).toEqual(['#edf1f4', '#edf1f4']);
    await page
      .getByRole('group', { name: 'Theme' })
      .getByRole('button', { name: 'System' })
      .click();
    expect(await colors()).toEqual(['#edf1f4', '#0e1624']);
  });
});

test.describe('offline', () => {
  test('registers a service worker that precaches the shell and the weather data', async ({
    page,
  }) => {
    await page.goto('/');
    await waitForServiceWorker(page);
    const cached = await page.evaluate(async () => {
      const names = await caches.keys();
      const cache = await caches.open(names.find((n) => n.startsWith('365-0-')) ?? '');
      return (await cache.keys()).map((r) => new URL(r.url).pathname);
    });
    expect(cached.some((p) => p.endsWith('/index.html'))).toBe(true);
    expect(cached.some((p) => p.endsWith('/data/world.v1.json'))).toBe(true);
    expect(cached.some((p) => p.endsWith('/manifest.webmanifest'))).toBe(true);
    expect(cached.some((p) => /\/assets\/index-.*\.js$/.test(p))).toBe(true);
  });

  test('plays a whole daily run with the network off after the first visit', async ({
    page,
    context,
  }) => {
    await openReturning(page);
    await waitForServiceWorker(page);
    await context.setOffline(true);
    await page.reload();
    await expect(page.getByRole('heading', { level: 1, name: '365-0' })).toBeVisible();
    await page.getByRole('button', { name: 'Play daily' }).click();
    await draftTwelve(page);
    await skipToResult(page);
    const record = await recordOf(page);
    expect(record.w + record.d + record.l).toBe(365);
    await context.setOffline(false);
  });
});

test.describe('install', () => {
  test('shows an Install button in Settings only when the browser offers installation', async ({
    page,
  }) => {
    await openReturning(page);
    await page.getByRole('button', { name: 'Settings' }).click();
    await expect(page.getByRole('button', { name: 'Install the app' })).toHaveCount(0);

    // The browser fires beforeinstallprompt: simulate it, with a prompt we can observe.
    await page.evaluate(() => {
      const event = new Event('beforeinstallprompt', { cancelable: true }) as Event & {
        prompt: () => Promise<void>;
        userChoice: Promise<{ outcome: string }>;
      };
      (window as unknown as { __prompted: boolean }).__prompted = false;
      event.prompt = () => {
        (window as unknown as { __prompted: boolean }).__prompted = true;
        return Promise.resolve();
      };
      event.userChoice = Promise.resolve({ outcome: 'accepted' });
      window.dispatchEvent(event);
    });
    const install = page.getByRole('button', { name: 'Install the app' });
    await expect(install).toBeVisible();
    await install.click();
    expect(
      await page.evaluate(() => (window as unknown as { __prompted: boolean }).__prompted),
    ).toBe(true);
    await expect(install).toHaveCount(0); // an offer can be used once
  });
});
