// Local-date helpers. The daily seed uses the player's local date (SPEC 1.5).

const pad = (n: number): string => String(n).padStart(2, '0');

/** YYYY-MM-DD in the player's local time zone. */
export function localDate(now: Date = new Date()): string {
  return `${String(now.getFullYear())}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Add days to a YYYY-MM-DD date (calendar arithmetic, safe across month ends and DST). */
export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split('-').map(Number) as [number, number, number];
  const base = new Date(Date.UTC(y, m - 1, d + days));
  return `${String(base.getUTCFullYear())}-${pad(base.getUTCMonth() + 1)}-${pad(base.getUTCDate())}`;
}

/** Milliseconds from `now` until the next local midnight. */
export function msUntilTomorrow(now: Date = new Date()): number {
  const next = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  return next.getTime() - now.getTime();
}

export interface Streak {
  count: number;
  /** Local date of the last completed daily, or null. */
  last: string | null;
}

/** The streak after completing the daily of `date`. Completing the same day twice changes nothing. */
export function completeDaily(streak: Streak, date: string): Streak {
  if (streak.last === date) return streak;
  if (streak.last !== null && addDays(streak.last, 1) === date) {
    return { count: streak.count + 1, last: date };
  }
  return { count: 1, last: date };
}

/** The streak to show today: still alive if the last daily was today or yesterday. */
export function activeStreak(streak: Streak, today: string): number {
  if (streak.last === null) return 0;
  return streak.last === today || addDays(streak.last, 1) === today ? streak.count : 0;
}
