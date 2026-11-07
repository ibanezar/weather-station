// Data validation (SPEC 2.3). Pure functions over parsed JSON; returns a list of problems.
import {
  ALLOWED_TAGS,
  ARCHETYPES,
  CONTINENTS,
  DAYS_IN_MONTH,
  MONTHS_PER_YEAR,
} from '../../src/data/types.ts';
import { DAY_TYPE_CHARS } from '../../src/engine/thresholds.ts';

export const MIN_CITIES_PER_CONTINENT = 6;
/** SPEC 2.2: ten full years per city. Data with fewer years is valid but interim (see yearsNotice). */
export const PLANNED_YEARS = 10;

type Json = unknown;

function isRecord(v: Json): v is Record<string, Json> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function inList(list: readonly string[], v: Json): boolean {
  return typeof v === 'string' && list.includes(v);
}

const DAY_CHARS = new Set<string>(DAY_TYPE_CHARS);

/** Checks the curated city list. */
export function validateSeed(seed: Json): string[] {
  const errors: string[] = [];
  if (!Array.isArray(seed) || seed.length === 0) return ['seed: must be a non-empty array'];

  const ids = new Set<string>();
  const perContinent = new Map<string, number>();

  seed.forEach((raw: Json, i) => {
    if (!isRecord(raw)) {
      errors.push(`seed[${String(i)}]: must be an object`);
      return;
    }
    const id = typeof raw['id'] === 'string' ? raw['id'] : '';
    const at = id === '' ? `seed[${String(i)}]` : `seed ${id}`;

    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(id)) errors.push(`${at}: id must be a lowercase slug`);
    else if (ids.has(id)) errors.push(`${at}: duplicate city id`);
    ids.add(id);

    const name = raw['name'];
    if (!isRecord(name) || typeof name['en'] !== 'string' || name['en'].trim() === '') {
      errors.push(`${at}: name.en is required`);
    } else if ('sl' in name && (typeof name['sl'] !== 'string' || name['sl'].trim() === '')) {
      errors.push(`${at}: name.sl must be a non-empty string when present`);
    }

    if (typeof raw['country'] !== 'string' || !/^[A-Z]{2}$/.test(raw['country'])) {
      errors.push(`${at}: country must be an ISO 3166-1 alpha-2 code`);
    }

    if (!inList(CONTINENTS, raw['continent'])) {
      errors.push(`${at}: unknown continent ${JSON.stringify(raw['continent'])}`);
    } else {
      const continent = raw['continent'] as string;
      perContinent.set(continent, (perContinent.get(continent) ?? 0) + 1);
    }

    const { lat, lon } = raw;
    if (typeof lat !== 'number' || !Number.isFinite(lat) || lat < -90 || lat > 90) {
      errors.push(`${at}: lat must be a number between -90 and 90`);
    }
    if (typeof lon !== 'number' || !Number.isFinite(lon) || lon < -180 || lon > 180) {
      errors.push(`${at}: lon must be a number between -180 and 180`);
    }

    const tags = raw['tags'];
    if (!Array.isArray(tags) || tags.length === 0) {
      errors.push(`${at}: tags must be a non-empty array`);
    } else {
      for (const tag of tags as Json[]) {
        if (!inList(ALLOWED_TAGS, tag))
          errors.push(`${at}: tag ${JSON.stringify(tag)} not allowed`);
      }
      if (new Set(tags as Json[]).size !== tags.length) errors.push(`${at}: duplicate tags`);
    }

    if (!inList(ARCHETYPES, raw['archetype'])) {
      errors.push(`${at}: archetype must be one of ${ARCHETYPES.join(', ')}`);
    } else if (Array.isArray(raw['tags']) && !(raw['tags'] as Json[]).includes(raw['archetype'])) {
      errors.push(`${at}: archetype ${String(raw['archetype'])} must also be listed in tags`);
    }

    if ('note' in raw && (typeof raw['note'] !== 'string' || raw['note'].trim() === '')) {
      errors.push(`${at}: note must be a non-empty string when present`);
    }
  });

  for (const continent of CONTINENTS) {
    const n = perContinent.get(continent) ?? 0;
    if (n < MIN_CITIES_PER_CONTINENT) {
      errors.push(
        `continent ${continent} has ${String(n)} cities, needs at least ${String(MIN_CITIES_PER_CONTINENT)}`,
      );
    }
  }
  return errors;
}

/** Checks the generated world file against the city list. */
export function validateWorld(world: Json, seed: Json): string[] {
  const errors: string[] = [];
  if (!isRecord(world)) return ['world: must be an object'];
  if (world['v'] !== 1) errors.push('world: v must be 1');

  // The number of years follows the file (interim data may hold fewer than PLANNED_YEARS); every
  // month of every city must then carry exactly one string per listed year.
  const years = world['years'];
  const yearsOk =
    Array.isArray(years) &&
    years.length >= 1 &&
    years.every(
      (y, i) => Number.isInteger(y) && (i === 0 || (y as number) > (years[i - 1] as number)),
    );
  if (!yearsOk)
    errors.push('world: years must be a non-empty, strictly ascending list of integers');
  const yearCount = yearsOk ? years.length : PLANNED_YEARS;

  const cities = world['cities'];
  if (!isRecord(cities)) return [...errors, 'world: cities must be an object'];

  const seedIds = Array.isArray(seed)
    ? (seed as Json[]).flatMap((c) => (isRecord(c) && typeof c['id'] === 'string' ? [c['id']] : []))
    : [];
  for (const id of seedIds) if (!(id in cities)) errors.push(`world: missing city ${id}`);
  for (const id of Object.keys(cities)) {
    if (!seedIds.includes(id)) errors.push(`world: city ${id} is not in the seed list`);
  }

  for (const [id, city] of Object.entries(cities)) {
    if (!isRecord(city)) {
      errors.push(`world ${id}: must be an object`);
      continue;
    }

    const t = city['t'];
    if (
      !Array.isArray(t) ||
      t.length !== MONTHS_PER_YEAR ||
      !t.every((v) => typeof v === 'number' && Number.isFinite(v))
    ) {
      errors.push(`world ${id}: t must hold ${String(MONTHS_PER_YEAR)} finite temperatures`);
    }

    for (const key of ['sp', 'sb'] as const) {
      const buckets = city[key];
      if (
        !Array.isArray(buckets) ||
        buckets.length !== MONTHS_PER_YEAR ||
        !buckets.every((v) => Number.isInteger(v) && (v as number) >= 0 && (v as number) <= 4)
      ) {
        errors.push(
          `world ${id}: ${key} must hold ${String(MONTHS_PER_YEAR)} integers from 0 to 4`,
        );
      }
    }

    const d = city['d'];
    if (!Array.isArray(d) || d.length !== MONTHS_PER_YEAR) {
      errors.push(`world ${id}: d must hold ${String(MONTHS_PER_YEAR)} months`);
      continue;
    }
    d.forEach((month: Json, m) => {
      const where = `world ${id} month ${String(m + 1)}`;
      if (!Array.isArray(month) || month.length !== yearCount) {
        errors.push(`${where}: needs ${String(yearCount)} year strings`);
        return;
      }
      const expected = DAYS_IN_MONTH[m] ?? 0;
      month.forEach((s: Json, y) => {
        if (typeof s !== 'string') {
          errors.push(`${where} year ${String(y)}: must be a string`);
          return;
        }
        if (s.length !== expected) {
          errors.push(
            `${where} year ${String(y)}: length ${String(s.length)}, expected ${String(expected)}`,
          );
        }
        for (const ch of s) {
          if (!DAY_CHARS.has(ch)) {
            errors.push(`${where} year ${String(y)}: illegal character ${JSON.stringify(ch)}`);
            break;
          }
        }
      });
    });
  }
  return errors;
}

/** The bundled index must describe exactly the seed list, in the same order. */
export function validateIndex(index: Json, seed: Json): string[] {
  if (!Array.isArray(index)) return ['index: must be an array'];
  if (!Array.isArray(seed)) return ['index: cannot compare, seed is invalid'];
  const errors: string[] = [];
  if (JSON.stringify(index) !== JSON.stringify(seed)) {
    errors.push('index: cities.index.json is out of date with cities.seed.json (run npm run data)');
  }
  return errors;
}

/**
 * A notice (not an error) when the world file holds fewer than the planned ten years. Returns
 * undefined for a full dataset or when the file has no readable year list.
 */
export function yearsNotice(world: Json): string | undefined {
  if (!isRecord(world) || !Array.isArray(world['years'])) return undefined;
  const n = world['years'].length;
  return n < PLANNED_YEARS
    ? `INTERIM DATA: ${String(n)} of ${String(PLANNED_YEARS)} planned years. Fetch the remaining years before phase 1 is done.`
    : undefined;
}
