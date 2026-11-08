// Records and the best possible record for a seed (SPEC 1.8).
import { DEFAULT_CHASE, recordFor, type ChaseId } from './chase.ts';
import type { DayType } from './thresholds.ts';
import { resolve } from './outcome.ts';
import type { DayRecord, DraftRound, EngineData } from './types.ts';

export const emptyRecord = (): DayRecord => ({ w: 0, d: 0, l: 0 });

/** Wins, draws and losses of a list of days under a chase (perfect days, draws and losses in the sunny game). */
export function record(days: readonly DayType[], chase: ChaseId = DEFAULT_CHASE): DayRecord {
  return recordFor(days, chase);
}

export function addRecords(a: DayRecord, b: DayRecord): DayRecord {
  return { w: a.w + b.w, d: a.d + b.d, l: a.l + b.l };
}

export interface RoundOption {
  cityId: string;
  year: number;
  record: DayRecord;
}

export interface RoundBest {
  best: RoundOption;
  /** All three options, in the order they were offered. */
  options: RoundOption[];
}

export interface BestPossible {
  record: DayRecord;
  rounds: RoundBest[];
}

/** More wins is better; with equal wins, fewer losses is better. */
export function isBetter(a: DayRecord, b: DayRecord): boolean {
  return a.w > b.w || (a.w === b.w && a.l < b.l);
}

export function roundOptions(
  data: EngineData,
  seed: string,
  round: DraftRound,
  roundIndex: number,
  chase: ChaseId = DEFAULT_CHASE,
): RoundOption[] {
  return round.cities.map((cityId) => {
    const o = resolve(data, seed, roundIndex, cityId, round.month, round.event);
    return { cityId, year: o.year, record: record(o.days, chase) };
  });
}

/**
 * Rounds are independent, so the best record for a seed is the sum of the best option of every round
 * (most perfect days, fewest losses as the tiebreak).
 */
export function bestPossible(
  data: EngineData,
  seed: string,
  draft: readonly DraftRound[],
  chase: ChaseId = DEFAULT_CHASE,
): BestPossible {
  let total = emptyRecord();
  const rounds = draft.map((round, i) => {
    const options = roundOptions(data, seed, round, i, chase);
    let best = options[0] as RoundOption;
    for (const o of options) if (isBetter(o.record, best.record)) best = o;
    total = addRecords(total, best.record);
    return { best, options };
  });
  return { record: total, rounds };
}
