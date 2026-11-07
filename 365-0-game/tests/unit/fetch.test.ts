import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cachePath, getCityYear, RateLimitError } from '../../scripts/lib/fetch.ts';
import type { SeedCity } from '../../src/data/types.ts';

const city: SeedCity = {
  id: 'testville',
  name: { en: 'Testville' },
  country: 'SI',
  continent: 'europe',
  lat: 46,
  lon: 14,
  archetype: 'continental',
  tags: ['continental'],
};

const goodBody = JSON.stringify({
  latitude: 46,
  longitude: 14,
  elevation: 300,
  daily: { time: ['2021-01-01'] },
});

let dir: string;
const log = vi.fn();

beforeEach(() => {
  vi.useFakeTimers();
  dir = mkdtempSync(join(tmpdir(), 'cache-test-'));
  log.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  rmSync(dir, { recursive: true, force: true });
});

describe('getCityYear', () => {
  it('retries a 200 response whose body is not JSON, and only caches the good one', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('Unexpected server error', { status: 200 }))
      .mockResolvedValueOnce(new Response(goodBody, { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    const pending = getCityYear(city, 2021, { cacheDir: dir, log });
    await vi.advanceTimersByTimeAsync(2000);
    const result = await pending;

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.fromCache).toBe(false);
    expect(existsSync(cachePath(dir, city.id, 2021))).toBe(true);
    expect(log).toHaveBeenCalledWith(expect.stringMatching(/unusable response body/));
  });

  it('gives up with a clear error when the body stays unusable, and caches nothing', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockImplementation(() => Promise.resolve(new Response('Unexpected', { status: 200 }))),
    );
    const pending = getCityYear(city, 2021, { cacheDir: dir, log });
    const assertion = expect(pending).rejects.toThrow(/unusable response body/);
    await vi.advanceTimersByTimeAsync(2000 + 4000 + 8000 + 16000);
    await assertion;
    expect(existsSync(cachePath(dir, city.id, 2021))).toBe(false);
  });

  it('reads a cached city-year without calling the network', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(goodBody, { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    await getCityYear(city, 2021, { cacheDir: dir, log });
    const again = await getCityYear(city, 2021, { cacheDir: dir, log });
    expect(again.fromCache).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('turns a daily-limit 429 into a RateLimitError carrying the retry delay', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ error: true, reason: 'Daily API request limit exceeded.' }),
            { status: 429, headers: { 'retry-after': '34309' } },
          ),
        ),
    );
    const err = await getCityYear(city, 2021, { cacheDir: dir, log }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(RateLimitError);
    expect((err as RateLimitError).kind).toBe('daily');
    expect((err as RateLimitError).retryAfterSec).toBe(34309);
  });
});
