// Chases: what a "win" is. The sunny year (perfect days) is the classic game; the other chases score the
// same real weather differently, so the best city for a month depends on what you are chasing.
import type { World } from '../data/types.ts';
import type { DayType } from './thresholds.ts';
import type { DayRecord } from './types.ts';

export const CHASE_IDS = ['sun', 'snow', 'rain', 'storm', 'heat'] as const;
export type ChaseId = (typeof CHASE_IDS)[number];
export const DEFAULT_CHASE: ChaseId = 'sun';

export interface ChaseDef {
  id: ChaseId;
  /** Day types that win. */
  win: readonly DayType[];
  /** Day types that lose. Everything else is a draw. */
  loss: readonly DayType[];
}

export const CHASES: Record<ChaseId, ChaseDef> = {
  sun: { id: 'sun', win: ['p'], loss: ['r', 's', 'h', 'f'] },
  /** Snow and frost: a day at or below 3 °C, or with snowfall (the freeze type). */
  snow: { id: 'snow', win: ['f'], loss: ['h', 'p'] },
  rain: { id: 'rain', win: ['r'], loss: ['p', 'h'] },
  storm: { id: 'storm', win: ['s'], loss: ['p'] },
  heat: { id: 'heat', win: ['h'], loss: ['f', 'r'] },
};

export function isChaseId(value: unknown): value is ChaseId {
  return typeof value === 'string' && (CHASE_IDS as readonly string[]).includes(value);
}

export function isWin(type: DayType, chase: ChaseId = DEFAULT_CHASE): boolean {
  return CHASES[chase].win.includes(type);
}

export function isLossFor(type: DayType, chase: ChaseId = DEFAULT_CHASE): boolean {
  return CHASES[chase].loss.includes(type);
}

/** Wins, draws and losses of a list of days under a chase. */
export function recordFor(days: readonly DayType[], chase: ChaseId = DEFAULT_CHASE): DayRecord {
  const r: DayRecord = { w: 0, d: 0, l: 0 };
  for (const type of days) {
    if (isWin(type, chase)) r.w += 1;
    else if (isLossFor(type, chase)) r.l += 1;
    else r.d += 1;
  }
  return r;
}

/**
 * Quintile bucket (0-4) of each value among all values, using midranks so equal values always share
 * a bucket. Higher value, higher bucket.
 */
export function quintileBuckets(values: number[]): number[] {
  const n = values.length;
  return values.map((v) => {
    let less = 0;
    let equal = 0;
    for (const x of values) {
      if (x < v) less += 1;
      else if (x === v) equal += 1;
    }
    const fraction = (less + equal / 2) / n;
    return Math.min(4, Math.floor(fraction * 5));
  });
}

/** Share of the days in `years` (one string per year) for which `pick` is true. */
export function dayShare(years: readonly string[], pick: (type: DayType) => boolean): number {
  let total = 0;
  let hit = 0;
  for (const s of years) {
    for (const ch of s) {
      total += 1;
      if (pick(ch as DayType)) hit += 1;
    }
  }
  return total === 0 ? 0 : hit / total;
}

interface ChaseBuckets {
  /** [month][city id] */
  win: Map<string, number>[];
  loss: Map<string, number>[];
}

const bucketCache = new WeakMap<World, Map<ChaseId, ChaseBuckets>>();

/** Scout buckets (0 to 4) of a city-month for a chase, ranked against every city in the world. */
export function chaseBuckets(
  world: World,
  chase: ChaseId,
  cityId: string,
  month: number,
): { win: number; loss: number } {
  let perChase = bucketCache.get(world);
  if (!perChase) {
    perChase = new Map();
    bucketCache.set(world, perChase);
  }
  let buckets = perChase.get(chase);
  if (!buckets) {
    const ids = Object.keys(world.cities);
    const def = CHASES[chase];
    const win: Map<string, number>[] = [];
    const loss: Map<string, number>[] = [];
    for (let m = 0; m < 12; m++) {
      const wins = ids.map((id) =>
        dayShare(world.cities[id]?.d[m] ?? [], (t) => def.win.includes(t)),
      );
      const losses = ids.map((id) =>
        dayShare(world.cities[id]?.d[m] ?? [], (t) => def.loss.includes(t)),
      );
      // A place with none of those days at all is the lowest bucket, even when most places have none
      // (heat and storms are rare, so ties at zero would otherwise land in the middle).
      const rank = (values: number[]): number[] =>
        quintileBuckets(values).map((b, i) => (values[i] === 0 ? 0 : b));
      const wb = rank(wins);
      const lb = rank(losses);
      win.push(new Map(ids.map((id, i) => [id, wb[i] ?? 0])));
      loss.push(new Map(ids.map((id, i) => [id, lb[i] ?? 0])));
    }
    buckets = { win, loss };
    perChase.set(chase, buckets);
  }
  return {
    win: buckets.win[month]?.get(cityId) ?? 0,
    loss: buckets.loss[month]?.get(cityId) ?? 0,
  };
}

/**
 * The fewest wins the best possible year must hold, so a snow, rain, storm or heat run is never a draft of
 * cities that have none of those days. The sunny game has no floor (its drafts are always rich in perfect days).
 */
export const MIN_BEST_WINS: Record<ChaseId, number> = {
  sun: 0,
  snow: 50,
  rain: 80,
  storm: 20,
  heat: 25,
};

/** How many drafts of the same seed are tried before taking the best one found. */
export const DRAFT_ATTEMPTS = 12;
