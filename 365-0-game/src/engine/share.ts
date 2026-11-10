// What a finished run shares: a text message and the data for the share image (SPEC 6.8).
import { DAY_TYPE_CHARS, type DayType } from './thresholds.ts';
import type { GradeId } from './grades.ts';
import type { Mode, RunResult } from './run.ts';
import type { DayRecord } from './types.ts';

/** Emoji squares, used only in the plain-text message. There is no cyan square, so freeze uses green. */
export const SQUARES: Record<DayType, string> = {
  p: '🟨',
  o: '⬜',
  r: '🟦',
  s: '🟪',
  h: '🟧',
  f: '🟩',
};

/** Most frequent day type; a tie goes to the type listed first (perfect, ok, rain, storm, heat, freeze). */
export function dominantType(days: readonly DayType[]): DayType {
  const counts: Record<DayType, number> = { p: 0, o: 0, r: 0, s: 0, h: 0, f: 0 };
  for (const t of days) counts[t] += 1;
  let best: DayType = 'p';
  for (const t of DAY_TYPE_CHARS) if (counts[t] > counts[best]) best = t;
  return best;
}

/** Twelve squares, one per month, by dominant day type. */
export function monthSquares(result: RunResult): string {
  return result.rounds.map((r) => SQUARES[dominantType(r.days)]).join('');
}

export const formatRecord = (r: DayRecord): string =>
  `${String(r.w)}-${String(r.d)}-${String(r.l)}`;

export interface ShareTextInput {
  /** Translated words for the lines. */
  title: string;
  modeLabel: string;
  recordLabel: string;
  gradeTitle: string;
  /** YYYY-MM-DD, shown for the daily run. */
  date?: string;
  /** Optional social context, kept outside the engine's game state. */
  contractLine?: string;
  challengeLine?: string;
  url: string;
}

export function buildShareText(result: RunResult, input: ShareTextInput): string {
  const header = [input.title, input.modeLabel, input.date].filter(Boolean).join(' ');
  const lines = [
    header,
    `${input.recordLabel} ${formatRecord(result.record)} (${input.gradeTitle})`,
    input.contractLine,
    monthSquares(result),
    input.challengeLine,
    input.url,
  ];
  return lines.filter((line): line is string => Boolean(line)).join('\n');
}

export interface ShareImageModel {
  mode: Mode;
  date?: string;
  record: DayRecord;
  bestRecord: DayRecord;
  grade: GradeId;
  ratio: number;
  /** One column per month: the picked city and its days, top to bottom. */
  months: { cityId: string; year: number; days: DayType[] }[];
}

export function shareImageModel(
  result: RunResult,
  meta: { mode: Mode; date?: string },
): ShareImageModel {
  return {
    mode: meta.mode,
    ...(meta.date !== undefined ? { date: meta.date } : {}),
    record: result.record,
    bestRecord: result.bestRecord,
    grade: result.grade,
    ratio: result.ratio,
    months: result.rounds.map((r) => ({ cityId: r.cityId, year: r.year, days: r.days })),
  };
}
