// The picture of a city-month on its card: one thin bar per stored year, split by how the days went.
import { CHASES, type ChaseId } from './chase.ts';
import { DAY_TYPE_CHARS, type DayType } from './thresholds.ts';
import type { EngineData } from './types.ts';

export interface StripSegment {
  type: DayType;
  days: number;
}

/**
 * For each stored year of a month: the day types and how many days of each, with the days that win under
 * the chase first, then the draws, then the losses. Lined up on the left edge, a steady month reads as
 * even bars and a swingy one as ragged ones.
 */
export function monthStrip(
  data: Pick<EngineData, 'world'>,
  cityId: string,
  month: number,
  chase: ChaseId,
): StripSegment[][] {
  const years = data.world.cities[cityId]?.d[month];
  if (!years) throw new Error(`no world data for ${cityId} month ${String(month)}`);
  const { win, loss } = CHASES[chase];
  const draw = DAY_TYPE_CHARS.filter((t) => !win.includes(t) && !loss.includes(t));
  const order = [...win, ...draw, ...loss];
  return years.map((days) => {
    const counts = new Map<DayType, number>();
    for (const c of days) counts.set(c as DayType, (counts.get(c as DayType) ?? 0) + 1);
    return order.flatMap((type) => {
      const n = counts.get(type) ?? 0;
      return n > 0 ? [{ type, days: n }] : [];
    });
  });
}
