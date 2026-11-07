// How much a city's month varies from year to year: the risk of the pick, from the ten stored years.
import type { EngineData } from './types.ts';

export type RiskLevel = 'none' | 'steady' | 'mixed' | 'swingy';

export interface MonthRisk {
  /** Fewest and most perfect days in this month over the stored years. */
  min: number;
  max: number;
  mean: number;
  level: RiskLevel;
}

/**
 * A range of at most STEADY_RANGE perfect days is "steady", at least SWINGY_RANGE is "swingy". On the tuned data
 * about a quarter of the months that have any perfect day fall in each of those two groups.
 */
export const STEADY_RANGE = 5;
export const SWINGY_RANGE = 14;

export function monthRisk(
  data: Pick<EngineData, 'world'>,
  cityId: string,
  month: number,
): MonthRisk {
  const years = data.world.cities[cityId]?.d[month];
  if (!years) throw new Error(`no world data for ${cityId} month ${String(month)}`);
  const wins = years.map((s) => s.split('').filter((c) => c === 'p').length);
  const min = Math.min(...wins);
  const max = Math.max(...wins);
  const mean = wins.reduce((a, b) => a + b, 0) / wins.length;
  const range = max - min;
  const level: RiskLevel =
    max === 0
      ? 'none'
      : range <= STEADY_RANGE
        ? 'steady'
        : range >= SWINGY_RANGE
          ? 'swingy'
          : 'mixed';
  return { min, max, mean, level };
}
