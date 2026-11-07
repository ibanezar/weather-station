// The deterministic outcome of picking a city in a round (SPEC 1.8).
import { eventAffects, getCity, getEvent } from './lookup.ts';
import { makeRng, randInt } from './rng.ts';
import type { DayType } from './thresholds.ts';
import type { EngineData } from './types.ts';

export interface Outcome {
  /** The historical year that was drawn, e.g. 2021. */
  year: number;
  days: DayType[];
}

/**
 * Pick a stored year for this (seed, round, city), then apply the event if it affects the city.
 * Each (seed, round, city) has its own generator, so no other pick can change the result.
 */
export function resolve(
  data: EngineData,
  seed: string,
  round: number,
  cityId: string,
  month: number,
  eventId?: string,
): Outcome {
  const city = data.world.cities[cityId];
  if (!city) throw new Error(`no world data for ${cityId}`);
  const yearIndex = randInt(makeRng(seed, 'year', round, cityId), data.world.years.length);
  const year = data.world.years[yearIndex] as number;
  const source = city.d[month]?.[yearIndex];
  if (source === undefined) throw new Error(`no data for ${cityId} month ${String(month)}`);
  // The stored strings are plain ASCII, one character per day.
  const days = source.split('') as DayType[];

  if (eventId !== undefined) {
    const event = getEvent(data, eventId);
    if (eventAffects(event, getCity(data, cityId))) {
      const rng = makeRng(seed, 'event-days', round, cityId, eventId);
      for (let i = 0; i < days.length; i++) {
        const type = days[i] as DayType;
        // The first transform that lists this day type decides; one draw per matching day.
        const transform = event.transforms.find((t) => t.from.includes(type));
        if (transform && rng() < transform.p) days[i] = transform.to;
      }
    }
  }
  return { year, days };
}
