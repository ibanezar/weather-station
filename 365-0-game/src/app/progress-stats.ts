// What the Statistics screen shows, worked out from what the game already stores on this device.
import { CHASE_IDS, type ChaseId } from '../engine/chase.ts';
import type { GradeId } from '../engine/grades.ts';
import type { DayRecord } from '../engine/types.ts';
import { addDays } from './dates.ts';
import type { Stored } from './storage.ts';

export interface RecentDaily {
  date: string;
  chase: ChaseId;
  record: DayRecord;
  grade: GradeId;
}

export interface ChaseStats {
  chase: ChaseId;
  /** Finished games, daily and endless. */
  runs: number;
  dailies: number;
  bestDaily: DayRecord | null;
  bestEndless: DayRecord | null;
}

export interface ProgressStats {
  /** Finished games of every kind. */
  runs: number;
  dailies: number;
  /** Longest run of consecutive days with a daily (any chase). */
  longestStreak: number;
  perChase: ChaseStats[];
  /** The daily mystery: puzzles finished and the average score (0-4), null before the first. */
  mystery: { played: number; averagePoints: number | null };
  /** The latest dailies, newest first. */
  recent: RecentDaily[];
}

export const RECENT_LIMIT = 10;

/** `2026-11-05` or `2026-11-05:snow`. */
function splitKey(key: string): { date: string; chase: ChaseId } | null {
  const [date, id] = key.split(':') as [string, string | undefined];
  const chase = id ?? 'sun';
  return (CHASE_IDS as readonly string[]).includes(chase)
    ? { date, chase: chase as ChaseId }
    : null;
}

/** Longest stretch of consecutive calendar days in a list of dates (any order, repeats allowed). */
export function longestStretch(dates: readonly string[]): number {
  const sorted = [...new Set(dates)].sort();
  let best = 0;
  let run = 0;
  let prev: string | null = null;
  for (const d of sorted) {
    run = prev !== null && addDays(prev, 1) === d ? run + 1 : 1;
    best = Math.max(best, run);
    prev = d;
  }
  return best;
}

export function computeStats(stored: Stored): ProgressStats {
  const daily = Object.entries(stored.daily).flatMap(([key, result]) => {
    const k = splitKey(key);
    return k ? [{ ...k, record: result.record, grade: result.grade }] : [];
  });
  const perChase = CHASE_IDS.map((chase): ChaseStats => {
    const mine = daily.filter((d) => d.chase === chase);
    const best = mine.reduce<DayRecord | null>(
      (b, d) => (b === null || d.record.w > b.w ? d.record : b),
      null,
    );
    return {
      chase,
      runs: stored.runs[chase] ?? 0,
      dailies: mine.length,
      bestDaily: best,
      bestEndless: stored.bestEndless[chase] ?? null,
    };
  });
  const recent = [...daily]
    .sort((a, b) => (a.date === b.date ? 0 : a.date < b.date ? 1 : -1))
    .slice(0, RECENT_LIMIT);
  const mysteries = Object.entries(stored.mystery).filter(([, r]) => r.done);
  const mysteryPoints = mysteries.reduce((n, [, r]) => n + r.points, 0);
  return {
    runs: perChase.reduce((n, c) => n + c.runs, 0),
    dailies: daily.length,
    longestStreak: Math.max(
      longestStretch([...daily.map((d) => d.date), ...mysteries.map(([date]) => date)]),
      stored.streak.count,
    ),
    perChase,
    mystery: {
      played: mysteries.length,
      averagePoints: mysteries.length > 0 ? mysteryPoints / mysteries.length : null,
    },
    recent,
  };
}
