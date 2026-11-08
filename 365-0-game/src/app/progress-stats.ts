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

export interface CalendarDay {
  date: string;
  /** Daily games and mysteries finished that day: 0, 1 or 2 (any chase counts as the daily). */
  played: 0 | 1 | 2;
  /** After today (the rest of the current week). */
  future: boolean;
}

/** Monday = 0 ... Sunday = 6 for a YYYY-MM-DD date. */
export function weekdayIndex(date: string): number {
  const [y, m, d] = date.split('-').map(Number) as [number, number, number];
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

/**
 * The last `weeks` weeks, Monday to Sunday, oldest week first, ending with the week of `today`.
 * Days after today are marked as future.
 */
export function calendar(stored: Stored, today: string, weeks = 12): CalendarDay[] {
  const dailies = new Set(Object.keys(stored.daily).map((k) => k.slice(0, 10)));
  const mysteries = new Set(
    Object.entries(stored.mystery)
      .filter(([, r]) => r.done)
      .map(([date]) => date),
  );
  const monday = addDays(today, -weekdayIndex(today));
  const first = addDays(monday, -(weeks - 1) * 7);
  return Array.from({ length: weeks * 7 }, (_, i) => {
    const date = addDays(first, i);
    const played = (Number(dailies.has(date)) + Number(mysteries.has(date))) as 0 | 1 | 2;
    return { date, played, future: date > today };
  });
}
