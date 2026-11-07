// Shared engine types. Pure data shapes: no DOM, no I/O.
import type { ClimateTag, SeedCity, World } from '../data/types.ts';
import type { DayType } from './thresholds.ts';

export interface EventTransform {
  /** Day types that may be converted. */
  from: readonly DayType[];
  to: DayType;
  /** Probability per matching day. */
  p: number;
}

/** World event (SPEC 1.7), loaded from data/events.json. */
export interface WorldEvent {
  id: string;
  /** English source text; the UI reads the translated text from the i18n catalogs. */
  name: string;
  blurb: string;
  /** Cities with at least one of these tags are affected, or 'all'. */
  tags: readonly ClimateTag[] | 'all';
  transforms: readonly EventTransform[];
}

/** Everything the engine needs, injected by the caller (app, tests, scripts). */
export interface EngineData {
  cities: readonly SeedCity[];
  world: World;
  events: readonly WorldEvent[];
}

/** One round of the draft. `month` is 0 for January to 11 for December. */
export interface DraftRound {
  month: number;
  cities: [string, string, string];
  event?: string;
}

/** Wins (perfect days), draws (ok days) and losses (rain, storm, heat, freeze). */
export interface DayRecord {
  w: number;
  d: number;
  l: number;
}
