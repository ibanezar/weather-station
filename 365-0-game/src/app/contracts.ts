import type { DayRecord } from '../engine/types.ts';

export const CONTRACT_IDS = ['record', 'steady', 'clean-months'] as const;
export type ContractId = (typeof CONTRACT_IDS)[number];
export const DEFAULT_CONTRACT: ContractId = 'record';

export function isContractId(value: unknown): value is ContractId {
  return typeof value === 'string' && (CONTRACT_IDS as readonly string[]).includes(value);
}

export interface ContractProgress {
  current: number;
  target: number;
  months: number;
  passed: boolean;
  complete: boolean;
  percent: number;
}

type RoundScore = { record: DayRecord; best: { record: DayRecord } };

/** Calculate an objective from the finalized months only; a pending month is not counted yet. */
export function contractProgress(
  id: ContractId,
  rounds: readonly RoundScore[],
  bestRecord: DayRecord,
  complete = rounds.length === 12,
): ContractProgress {
  const wins = rounds.reduce((sum, round) => sum + round.record.w, 0);
  const losses = rounds.reduce((sum, round) => sum + round.record.l, 0);
  const worstMonthOverBest = rounds.reduce(
    (worst, round) => Math.max(worst, Math.max(0, round.record.l - round.best.record.l)),
    0,
  );

  if (id === 'record') {
    const target = Math.ceil(bestRecord.w * 0.9);
    return {
      current: wins,
      target,
      months: rounds.length,
      passed: wins >= target,
      complete,
      percent: target > 0 ? Math.min(100, Math.round((wins / target) * 100)) : 0,
    };
  }

  if (id === 'steady') {
    const target = bestRecord.l + 40;
    return {
      current: losses,
      target,
      months: rounds.length,
      passed: losses <= target,
      complete,
      percent: Math.round((rounds.length / 12) * 100),
    };
  }

  const target = 8;
  return {
    current: worstMonthOverBest,
    target,
    months: rounds.length,
    passed: complete && rounds.length === 12 && worstMonthOverBest <= target,
    complete,
    percent: Math.round((rounds.length / 12) * 100),
  };
}
