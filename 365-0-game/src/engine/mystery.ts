// The daily mystery ("Where was this?"): a real day of weather, three cities, one of them is right.
// Pure and deterministic. The puzzles themselves are built ahead of time by scripts/lib/mystery.ts from
// the same weather data as the rest of the game; this file holds their shape, the clues, the scoring and
// the small amount of astronomy the day-length clue needs.
import { makeRng, shuffle } from './rng.ts';

/** The clues, in the order they are shown. The first is free; every further one costs a point. */
export const CLUES = ['temp', 'sky', 'wind', 'daylight'] as const;
export type Clue = (typeof CLUES)[number];
export const MAX_POINTS = CLUES.length;

/** What the day was like, from the weather data. */
export interface MysteryWeather {
  /** Highest and lowest temperature, °C. */
  tx: number;
  tn: number;
  /** Precipitation, mm. */
  p: number;
  /** Snowfall, cm. */
  s: number;
  /** Strongest gust, km/h. */
  g: number;
  /** Average cloud cover, 0-100 %. */
  cl: number;
}

/** What that month is usually like in one city: 10th and 90th percentile of the daily highs and lows, and rainy days. */
export type Typical = [
  txLow: number,
  txHigh: number,
  tnLow: number,
  tnHigh: number,
  wetPct: number,
];

export interface Puzzle {
  /** Month (0-11) and day of the month the weather was recorded on. */
  m: number;
  d: number;
  year: number;
  /** The right city, and the two wrong ones. */
  city: string;
  decoys: [string, string];
  w: MysteryWeather;
  /** Typical weather of each of the three cities in that month, for the explanation at the end. */
  typ: Record<string, Typical>;
}

export interface MysteryFile {
  v: 1;
  /** The calendar date of puzzles[0]; puzzle n is for the date n days later. */
  from: string;
  years: [number, number];
  puzzles: Puzzle[];
}

const DAY_MS = 86_400_000;

function utc(date: string): number {
  const [y, m, d] = date.split('-').map(Number) as [number, number, number];
  return Date.UTC(y, m - 1, d);
}

/** The puzzle for a calendar date (YYYY-MM-DD). Past the end of the file it starts over, so it never runs out. */
export function puzzleFor(file: MysteryFile, date: string): Puzzle {
  const n = file.puzzles.length;
  const index = Math.round((utc(date) - utc(file.from)) / DAY_MS);
  const puzzle = file.puzzles[((index % n) + n) % n];
  if (!puzzle) throw new Error('mystery file has no puzzles');
  return puzzle;
}

/** The three cities in the order they are offered (the same for everyone on a given date). */
export function candidateOrder(puzzle: Puzzle, date: string): string[] {
  return shuffle([puzzle.city, ...puzzle.decoys], makeRng('mystery-order', date));
}

// ── Length of the day ──────────────────────────────────────────────────────────────────────

const MONTH_START = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

/**
 * Minutes between sunrise and sunset on a day, from the latitude alone (the sun's declination for the day of
 * the year, with the usual allowance for refraction). 0 in polar night and 1440 in polar day. Good to a few
 * minutes, which is plenty for a clue.
 */
export function dayLengthMinutes(latitude: number, month: number, day: number): number {
  const doy = (MONTH_START[month] ?? 0) + day;
  const decl = -23.44 * Math.cos((2 * Math.PI * (doy + 10)) / 365) * (Math.PI / 180);
  const lat = latitude * (Math.PI / 180);
  const cosH =
    (Math.sin(-0.833 * (Math.PI / 180)) - Math.sin(lat) * Math.sin(decl)) /
    (Math.cos(lat) * Math.cos(decl));
  if (cosH >= 1) return 0;
  if (cosH <= -1) return 1440;
  return Math.round(2 * Math.acos(cosH) * (180 / Math.PI) * 4);
}

// ── Playing ────────────────────────────────────────────────────────────────────────────────

export interface MysteryState {
  /** How many clues are showing (1 to 4). */
  revealed: number;
  /** Cities guessed wrong, in order. */
  wrong: string[];
  solved: boolean;
}

export const newMystery = (): MysteryState => ({ revealed: 1, wrong: [], solved: false });

/** Two wrong guesses leave one city, so the puzzle is over: it is the answer by elimination. */
export function isFinished(state: MysteryState): boolean {
  return state.solved || state.wrong.length >= 2;
}

/** Look at one more clue (costs a point). */
export function reveal(state: MysteryState): MysteryState {
  if (isFinished(state) || state.revealed >= CLUES.length) return state;
  return { ...state, revealed: state.revealed + 1 };
}

/** Guess a city. A wrong guess crosses it out and shows the next clue. */
export function guess(state: MysteryState, puzzle: Puzzle, cityId: string): MysteryState {
  if (isFinished(state) || state.wrong.includes(cityId)) return state;
  if (cityId === puzzle.city) return { ...state, solved: true };
  return {
    ...state,
    wrong: [...state.wrong, cityId],
    revealed: Math.min(CLUES.length, state.revealed + 1),
  };
}

/** 4 points for solving it from the first clue, down to 1 with all four; 0 if it was not solved. */
export function points(state: MysteryState): number {
  return state.solved ? MAX_POINTS + 1 - state.revealed : 0;
}

/** The guesses and clues of a finished puzzle, enough to show it again after a restart. */
export interface MysteryResult {
  /** City ids guessed, in order, the right one last when it was found. */
  guesses: string[];
  revealed: number;
  points: number;
  /** Solved, or two wrong guesses. A result that is not done is a puzzle in progress. */
  done: boolean;
}

export function resultOf(state: MysteryState, puzzle: Puzzle): MysteryResult {
  return {
    guesses: state.solved ? [...state.wrong, puzzle.city] : [...state.wrong],
    revealed: state.revealed,
    points: points(state),
    done: isFinished(state),
  };
}

/** Rebuild the state from a stored result (the clues looked at on purpose are in `revealed`). */
export function stateFrom(result: MysteryResult, puzzle: Puzzle): MysteryState {
  const replayed = result.guesses.reduce((s, id) => guess(s, puzzle, id), newMystery());
  return { ...replayed, revealed: Math.max(replayed.revealed, result.revealed) };
}
