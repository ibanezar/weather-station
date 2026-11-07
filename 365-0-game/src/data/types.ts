// Shared data contracts: used by the build script, the validator and (from phase 2) the app.

export const CONTINENTS = [
  'africa',
  'asia',
  'europe',
  'north-america',
  'south-america',
  'oceania',
] as const;
export type Continent = (typeof CONTINENTS)[number];

/** The 16 climate tags from SPEC 2.1. A city may carry several. */
export const ALLOWED_TAGS = [
  'desert',
  'steppe',
  'monsoon',
  'tropical',
  'equatorial',
  'savanna',
  'mediterranean',
  'oceanic',
  'maritime',
  'continental',
  'temperate',
  'subarctic',
  'polar',
  'highland',
  'island',
  'pacific-coast',
] as const;
export type ClimateTag = (typeof ALLOWED_TAGS)[number];

/**
 * The ten archetypes that have an icon (SPEC 6.4). Every city has exactly one primary archetype,
 * used for the "3 different archetypes per round" rule and the card icon. It is always also a tag.
 */
export const ARCHETYPES = [
  'desert',
  'monsoon',
  'tropical',
  'mediterranean',
  'oceanic',
  'continental',
  'subarctic',
  'polar',
  'highland',
  'island',
] as const satisfies readonly ClimateTag[];
export type Archetype = (typeof ARCHETYPES)[number];

export interface SeedCity {
  id: string;
  name: { en: string; sl?: string };
  /** ISO 3166-1 alpha-2 (AQ for Antarctica). */
  country: string;
  continent: Continent;
  lat: number;
  lon: number;
  archetype: Archetype;
  tags: ClimateTag[];
  /** Shown for extreme places; states which grid point stands in for the real place. */
  note?: string;
}

/** What the app bundles for the first paint (src/data/cities.index.json). */
export type CityIndexEntry = SeedCity;

export const MONTHS_PER_YEAR = 12;
/** Days per month with 29 February dropped (SPEC 2.2). */
export const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31] as const;

export interface WorldCity {
  /** Mean temperature per month in °C. */
  t: number[];
  /** Scout bucket (0-4) for perfect days per month. */
  sp: number[];
  /** Scout bucket (0-4) for bad days per month. */
  sb: number[];
  /** d[month][yearIndex]: one character per day, see DayType. */
  d: string[][];
}

/** public/data/world.v1.json */
export interface World {
  v: 1;
  years: number[];
  cities: Record<string, WorldCity>;
}
