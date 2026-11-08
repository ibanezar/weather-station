// Builds the daily mystery puzzles from the same API responses as the world data (see src/engine/mystery.ts).
// Pure: responses in, a puzzle file out. The puzzle for a date depends only on that date and the data, so
// rebuilding the file for a longer range never changes puzzles that are already out.
import type { SeedCity } from '../../src/data/types.ts';
import type { MysteryFile, Puzzle, Typical } from '../../src/engine/mystery.ts';
import { makeRng, randInt, shuffle, type Rng } from '../../src/engine/rng.ts';
import type { ApiResponse } from './build.ts';

/** First date a puzzle is built for, and how many days the file covers. */
export const MYSTERY_FROM = '2026-11-09';
export const MYSTERY_DAYS = 400;

const DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

export interface MonthStat {
  txMean: number;
  txSd: number;
  tnMean: number;
  tnSd: number;
  /** 10th and 90th percentile of the daily highs and lows. */
  txP: [number, number];
  tnP: [number, number];
  /** Share of days with 1 mm of rain or more, 0-1. */
  wet: number;
}

/** One day of the weather of a city in one year, by month and day of the month. */
interface DayValues {
  tx: number;
  tn: number;
  p: number;
  s: number;
  g: number;
  cl: number | null;
}

function dayAt(resp: ApiResponse, i: number): DayValues | null {
  const d = resp.daily;
  const tx = d.temperature_2m_max[i];
  const tn = d.temperature_2m_min[i];
  const p = d.precipitation_sum[i];
  const s = d.snowfall_sum[i];
  const g = d.wind_gusts_10m_max[i];
  const cl = d.cloud_cover_mean[i];
  if (
    tx === null ||
    tx === undefined ||
    tn === null ||
    tn === undefined ||
    p === null ||
    p === undefined ||
    s === null ||
    s === undefined ||
    g === null ||
    g === undefined
  )
    return null;
  return { tx, tn, p, s, g, cl: cl === null || cl === undefined ? null : cl };
}

function percentile(sorted: number[], q: number): number {
  const i = (sorted.length - 1) * q;
  const lo = Math.floor(i);
  const hi = Math.ceil(i);
  return (sorted[lo] ?? 0) + ((sorted[hi] ?? 0) - (sorted[lo] ?? 0)) * (i - lo);
}

/** Climate of one city, month by month, over all the years. */
export function monthStats(responses: ApiResponse[]): MonthStat[] {
  const tx: number[][] = Array.from({ length: 12 }, () => []);
  const tn: number[][] = Array.from({ length: 12 }, () => []);
  const wet: number[] = Array.from({ length: 12 }, () => 0);
  for (const resp of responses) {
    resp.daily.time.forEach((date, i) => {
      const m = Number(date.slice(5, 7)) - 1;
      const day = dayAt(resp, i);
      if (!day) return;
      tx[m]?.push(day.tx);
      tn[m]?.push(day.tn);
      if (day.p >= 1) wet[m] = (wet[m] ?? 0) + 1;
    });
  }
  const mean = (a: number[]): number => a.reduce((x, y) => x + y, 0) / Math.max(1, a.length);
  const sd = (a: number[]): number => {
    const m = mean(a);
    return Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / Math.max(1, a.length));
  };
  return Array.from({ length: 12 }, (_, m) => {
    const hi = [...(tx[m] ?? [])].sort((a, b) => a - b);
    const lo = [...(tn[m] ?? [])].sort((a, b) => a - b);
    return {
      txMean: mean(hi),
      txSd: sd(hi),
      tnMean: mean(lo),
      tnSd: sd(lo),
      txP: [percentile(hi, 0.1), percentile(hi, 0.9)],
      tnP: [percentile(lo, 0.1), percentile(lo, 0.9)],
      wet: (wet[m] ?? 0) / Math.max(1, hi.length),
    };
  });
}

/** Smallest SD allowed when judging a fit: the tropics barely vary, but one degree is not a clear difference. */
const SD_FLOOR = 1.5;

/** How far a day's temperatures are from what a month is usually like: in standard deviations, the larger of high and low. */
export function misfit(obs: { tx: number; tn: number }, st: MonthStat): number {
  const zx = Math.abs(obs.tx - st.txMean) / Math.max(SD_FLOOR, st.txSd);
  const zn = Math.abs(obs.tn - st.tnMean) / Math.max(SD_FLOOR, st.tnSd);
  return Math.max(zx, zn);
}

/** The biggest gap in degrees between the day and the month's averages (high or low). */
export function gapDegrees(obs: { tx: number; tn: number }, st: MonthStat): number {
  return Math.max(Math.abs(obs.tx - st.txMean), Math.abs(obs.tn - st.tnMean));
}

/** How clearly a wrong city must differ (in SDs, in degrees), tried in order until enough cities qualify. */
const DECOY_TIERS: readonly (readonly [number, number])[] = [
  [2.5, 8],
  [2, 6],
  [1.5, 4],
  [1, 2],
];
/** The right city must fit the day well, or the puzzle would be unfair to someone who knows the climate. */
const ANSWER_MAX_MISFIT = 1.5;

const round1 = (n: number): number => Math.round(n * 10) / 10;
const pad = (n: number): string => String(n).padStart(2, '0');

function addDays(date: string, days: number): string {
  const [y, m, d] = date.split('-').map(Number) as [number, number, number];
  const t = new Date(Date.UTC(y, m - 1, d + days));
  return `${String(t.getUTCFullYear())}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`;
}

export interface MysteryInput {
  cities: readonly SeedCity[];
  /** Responses by `cityId/year`. */
  responses: ReadonlyMap<string, ApiResponse>;
  years: readonly number[];
}

function typical(st: MonthStat): Typical {
  return [
    Math.round(st.txP[0]),
    Math.round(st.txP[1]),
    Math.round(st.tnP[0]),
    Math.round(st.tnP[1]),
    Math.round(st.wet * 100),
  ];
}

/** Build the puzzle for one calendar date. */
export function buildPuzzle(
  date: string,
  input: MysteryInput,
  stats: ReadonlyMap<string, MonthStat[]>,
  index: ReadonlyMap<string, Map<string, number>>,
): Puzzle {
  const month = Number(date.slice(5, 7)) - 1;
  const dom = Math.min(Number(date.slice(8, 10)), DAYS[month] ?? 28); // 29 February plays as 28 February
  const ids = input.cities.map((c) => c.id).sort();
  const byId = new Map(input.cities.map((c) => [c.id, c]));
  const [first, last] = [input.years[0] ?? 0, input.years[input.years.length - 1] ?? 0];

  for (let attempt = 0; attempt < 400; attempt++) {
    const rng: Rng = makeRng('mystery', date, attempt);
    const cityId = ids[randInt(rng, ids.length)] ?? '';
    const year = input.years[randInt(rng, input.years.length)] ?? first;
    const resp = input.responses.get(`${cityId}/${String(year)}`);
    const row = index
      .get(`${cityId}/${String(year)}`)
      ?.get(`${String(year)}-${pad(month + 1)}-${pad(dom)}`);
    if (!resp || row === undefined) continue;
    const day = dayAt(resp, row);
    if (!day || day.cl === null) continue;
    const own = stats.get(cityId)?.[month];
    if (!own || misfit(day, own) > ANSWER_MAX_MISFIT) continue;

    const country = byId.get(cityId)?.country;
    for (const [sd, deg] of DECOY_TIERS) {
      const pool = ids.filter((id) => {
        const st = stats.get(id)?.[month];
        return (
          id !== cityId &&
          byId.get(id)?.country !== country &&
          st !== undefined &&
          misfit(day, st) >= sd &&
          gapDegrees(day, st) >= deg
        );
      });
      if (pool.length < 2) continue;
      const decoys = shuffle(pool, rng).slice(0, 2) as [string, string];
      const typ: Record<string, Typical> = {};
      for (const id of [cityId, ...decoys]) {
        const st = stats.get(id)?.[month];
        if (st) typ[id] = typical(st);
      }
      return {
        m: month,
        d: dom,
        year,
        city: cityId,
        decoys,
        w: {
          tx: round1(day.tx),
          tn: round1(day.tn),
          p: round1(day.p),
          s: round1(day.s),
          g: Math.round(day.g),
          cl: Math.round(day.cl),
        },
        typ,
      };
    }
  }
  throw new Error(`no fair mystery found for ${date} (years ${String(first)}-${String(last)})`);
}

/** Build the puzzle file: one puzzle per day starting at `from`. */
export function buildMystery(
  input: MysteryInput,
  from: string = MYSTERY_FROM,
  days: number = MYSTERY_DAYS,
): MysteryFile {
  const stats = new Map<string, MonthStat[]>();
  const index = new Map<string, Map<string, number>>();
  for (const city of input.cities) {
    const own = input.years.flatMap((y) => {
      const r = input.responses.get(`${city.id}/${String(y)}`);
      return r ? [r] : [];
    });
    stats.set(city.id, monthStats(own));
    for (const y of input.years) {
      const resp = input.responses.get(`${city.id}/${String(y)}`);
      if (resp)
        index.set(`${city.id}/${String(y)}`, new Map(resp.daily.time.map((t, i) => [t, i])));
    }
  }
  const puzzles: Puzzle[] = [];
  for (let i = 0; i < days; i++) puzzles.push(buildPuzzle(addDays(from, i), input, stats, index));
  return {
    v: 1,
    from,
    years: [input.years[0] ?? 0, input.years[input.years.length - 1] ?? 0],
    puzzles,
  };
}
