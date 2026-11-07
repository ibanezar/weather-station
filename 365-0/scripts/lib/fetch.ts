// Open-Meteo archive access with an on-disk cache, retries and a clean stop at the rate limit.
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import type { SeedCity } from '../../src/data/types.ts';
import { DAILY_VARIABLES, type ApiResponse } from './build.ts';

export const API_URL = 'https://archive-api.open-meteo.com/v1/archive';
/** ERA5 for all years: the default best_match switches models in 2017, which would make years inconsistent. */
export const MODEL = 'era5';

export type LimitKind = 'daily' | 'hourly' | 'minutely' | 'other';

export class RateLimitError extends Error {
  readonly kind: LimitKind;
  readonly retryAfterSec: number | undefined;
  constructor(kind: LimitKind, reason: string, retryAfterSec: number | undefined) {
    super(reason);
    this.name = 'RateLimitError';
    this.kind = kind;
    this.retryAfterSec = retryAfterSec;
  }
}

/** Work out which limit a 429 response refers to. Exported for tests. */
export function classifyLimit(reason: string): LimitKind {
  const r = reason.toLowerCase();
  if (r.includes('daily')) return 'daily';
  if (r.includes('hourly')) return 'hourly';
  if (r.includes('minutely')) return 'minutely';
  return 'other';
}

export function buildUrl(city: Pick<SeedCity, 'lat' | 'lon'>, year: number): string {
  const q = new URLSearchParams({
    latitude: String(city.lat),
    longitude: String(city.lon),
    start_date: `${String(year)}-01-01`,
    end_date: `${String(year)}-12-31`,
    daily: DAILY_VARIABLES.join(','),
    timezone: 'auto',
    models: MODEL,
    temperature_unit: 'celsius',
    wind_speed_unit: 'kmh',
    precipitation_unit: 'mm',
  });
  return `${API_URL}?${q.toString()}`;
}

export function cachePath(cacheDir: string, id: string, year: number): string {
  return join(cacheDir, id, `${String(year)}.json`);
}

export function readCache(cacheDir: string, id: string, year: number): ApiResponse | undefined {
  const path = cachePath(cacheDir, id, year);
  if (!existsSync(path)) return undefined;
  return JSON.parse(readFileSync(path, 'utf8')) as ApiResponse;
}

function writeCache(cacheDir: string, id: string, year: number, data: ApiResponse): void {
  const path = cachePath(cacheDir, id, year);
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, JSON.stringify(data));
  renameSync(tmp, path); // atomic: a stopped run never leaves half a file
}

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

function isApiResponse(v: unknown): v is ApiResponse {
  if (typeof v !== 'object' || v === null) return false;
  const daily = (v as { daily?: unknown }).daily;
  return (
    typeof daily === 'object' && daily !== null && Array.isArray((daily as { time?: unknown }).time)
  );
}

export interface FetchOptions {
  cacheDir: string;
  log: (msg: string) => void;
}

/**
 * Get one city-year, from the cache if present. Waits out minutely and short hourly limits, retries
 * transient errors with backoff, and throws RateLimitError when the daily (or a long hourly) limit
 * is hit, so the caller can stop and be re-run later.
 */
export async function getCityYear(
  city: SeedCity,
  year: number,
  opts: FetchOptions,
): Promise<{ data: ApiResponse; fromCache: boolean }> {
  const cached = readCache(opts.cacheDir, city.id, year);
  if (cached) return { data: cached, fromCache: true };

  const url = buildUrl(city, year);
  const backoff = [2, 4, 8, 16];
  let transient = 0;
  let limitWaits = 0;

  for (;;) {
    let res: Response;
    try {
      res = await fetch(url, { signal: AbortSignal.timeout(60_000) });
    } catch (err) {
      if (transient >= backoff.length) throw err;
      const wait = backoff[transient++] ?? 16;
      opts.log(`  network error (${String(err)}), retrying in ${String(wait)} s`);
      await sleep(wait * 1000);
      continue;
    }

    if (res.ok) {
      const body: unknown = await res.json();
      if (!isApiResponse(body))
        throw new Error(`${city.id} ${String(year)}: unexpected response shape`);
      writeCache(opts.cacheDir, city.id, year, body);
      return { data: body, fromCache: false };
    }

    const text = await res.text();
    let reason = text.slice(0, 200);
    try {
      const parsed = JSON.parse(text) as { reason?: unknown };
      if (typeof parsed.reason === 'string') reason = parsed.reason;
    } catch {
      // keep the raw text
    }

    if (res.status === 429) {
      const retryAfter = Number(res.headers.get('retry-after'));
      const retryAfterSec = Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : undefined;
      const kind = classifyLimit(reason);
      const shortWait =
        kind === 'minutely' || (kind === 'hourly' && (retryAfterSec ?? Infinity) <= 3700);
      if (shortWait && limitWaits < 3) {
        limitWaits += 1;
        const wait = Math.min(retryAfterSec ?? 65, 3700) + 2;
        opts.log(`  ${kind} limit, waiting ${String(wait)} s`);
        await sleep(wait * 1000);
        continue;
      }
      throw new RateLimitError(kind, reason, retryAfterSec);
    }

    if (res.status >= 500 && transient < backoff.length) {
      const wait = backoff[transient++] ?? 16;
      opts.log(`  HTTP ${String(res.status)}, retrying in ${String(wait)} s`);
      await sleep(wait * 1000);
      continue;
    }
    throw new Error(`${city.id} ${String(year)}: HTTP ${String(res.status)}: ${reason}`);
  }
}
