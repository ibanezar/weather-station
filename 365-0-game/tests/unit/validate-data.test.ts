import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  validateIndex,
  validateSeed,
  validateWorld,
  yearsNotice,
} from '../../scripts/lib/validate.ts';
import { CONTINENTS, DAYS_IN_MONTH, type SeedCity, type World } from '../../src/data/types.ts';

/** Six cities on every continent: the smallest valid seed. */
function validSeed(): SeedCity[] {
  const list: SeedCity[] = [];
  for (const continent of CONTINENTS) {
    for (let i = 0; i < 6; i++) {
      list.push({
        id: `${continent}-${String(i)}`,
        name: { en: `City ${String(i)}` },
        country: 'SI',
        continent,
        lat: 10,
        lon: 20,
        archetype: 'continental',
        tags: ['continental', 'temperate'],
      });
    }
  }
  return list;
}

function validWorld(seed: SeedCity[], yearCount = 10): World {
  const cities: World['cities'] = {};
  for (const c of seed) {
    cities[c.id] = {
      t: Array<number>(12).fill(15),
      sp: Array<number>(12).fill(2),
      sb: Array<number>(12).fill(2),
      d: DAYS_IN_MONTH.map((n) => Array.from({ length: yearCount }, () => 'p'.repeat(n))),
    };
  }
  return {
    v: 1,
    years: Array.from({ length: yearCount }, (_, i) => 2025 - yearCount + 1 + i),
    cities,
  };
}

const clone = <T>(x: T): T => structuredClone(x);

describe('validateSeed', () => {
  it('accepts a valid list', () => {
    expect(validateSeed(validSeed())).toEqual([]);
  });

  it('rejects duplicate ids', () => {
    const s = validSeed();
    s[1] = { ...s[1]!, id: s[0]!.id };
    expect(validateSeed(s)).toContainEqual(expect.stringMatching(/duplicate city id/));
  });

  it('rejects tags outside the allowed list', () => {
    const s = clone(validSeed());
    (s[0]!.tags as string[]).push('rainy');
    expect(validateSeed(s)).toContainEqual(expect.stringMatching(/tag "rainy" not allowed/));
  });

  it('rejects an archetype that is not also a tag', () => {
    const s = validSeed();
    s[0] = { ...s[0]!, tags: ['temperate'] };
    expect(validateSeed(s)).toContainEqual(expect.stringMatching(/must also be listed in tags/));
  });

  it('rejects an unknown archetype or continent', () => {
    const s = validSeed();
    s[0] = { ...s[0]!, archetype: 'steppe' as never };
    s[1] = { ...s[1]!, continent: 'atlantis' as never };
    const errors = validateSeed(s);
    expect(errors).toContainEqual(expect.stringMatching(/archetype must be one of/));
    expect(errors).toContainEqual(expect.stringMatching(/unknown continent/));
  });

  it('requires at least 6 cities per continent', () => {
    const s = validSeed().filter((c) => c.id !== 'asia-0');
    expect(validateSeed(s)).toContainEqual(expect.stringMatching(/continent asia has 5 cities/));
  });

  it('rejects out-of-range coordinates', () => {
    const s = validSeed();
    s[0] = { ...s[0]!, lat: 120 };
    expect(validateSeed(s)).toContainEqual(expect.stringMatching(/lat must be/));
  });
});

describe('validateWorld', () => {
  const seed = validSeed();

  it('accepts valid data', () => {
    expect(validateWorld(validWorld(seed), seed)).toEqual([]);
  });

  it('accepts interim data with fewer than ten years and flags it as interim', () => {
    const w = validWorld(seed, 5);
    expect(w.years).toEqual([2021, 2022, 2023, 2024, 2025]);
    expect(validateWorld(w, seed)).toEqual([]);
    expect(yearsNotice(w)).toMatch(/INTERIM DATA: 5 of 10 planned years/);
    expect(yearsNotice(validWorld(seed, 10))).toBeUndefined();
  });

  it('rejects a month whose number of year strings does not match the year list', () => {
    const w = validWorld(seed, 5);
    w.years = [2016, 2017, 2018, 2019, 2020, 2021];
    expect(validateWorld(w, seed)).toContainEqual(expect.stringMatching(/needs 6 year strings/));
  });

  it('rejects an empty or non-ascending year list', () => {
    const w = validWorld(seed, 3);
    w.years = [2023, 2022, 2024];
    expect(validateWorld(w, seed)).toContainEqual(expect.stringMatching(/strictly ascending/));
    w.years = [];
    expect(validateWorld(w, seed)).toContainEqual(expect.stringMatching(/strictly ascending/));
  });

  it('rejects a city missing from the world and one that is not in the seed', () => {
    const w = validWorld(seed);
    delete w.cities['asia-0'];
    w.cities['ghost'] = w.cities['asia-1']!;
    const errors = validateWorld(w, seed);
    expect(errors).toContainEqual('world: missing city asia-0');
    expect(errors).toContainEqual('world: city ghost is not in the seed list');
  });

  it('rejects wrong string lengths, including a 29-day February', () => {
    const w = validWorld(seed);
    w.cities['asia-0']!.d[1]![3] = 'p'.repeat(29);
    expect(validateWorld(w, seed)).toContainEqual(
      expect.stringMatching(/month 2 year 3: length 29, expected 28/),
    );
  });

  it('rejects characters outside p o r s h f', () => {
    const w = validWorld(seed);
    w.cities['asia-0']!.d[0]![0] = 'x' + 'p'.repeat(30);
    expect(validateWorld(w, seed)).toContainEqual(expect.stringMatching(/illegal character "x"/));
  });

  it('rejects a month with fewer than 10 years', () => {
    const w = validWorld(seed);
    w.cities['asia-0']!.d[4]!.pop();
    expect(validateWorld(w, seed)).toContainEqual(expect.stringMatching(/needs 10 year strings/));
  });

  it('rejects scout buckets that are not integers from 0 to 4', () => {
    const w = validWorld(seed);
    w.cities['asia-0']!.sp[0] = 5;
    w.cities['asia-1']!.sb[0] = 1.5;
    const errors = validateWorld(w, seed);
    expect(errors).toContainEqual(expect.stringMatching(/asia-0: sp must hold/));
    expect(errors).toContainEqual(expect.stringMatching(/asia-1: sb must hold/));
  });
});

describe('validateIndex', () => {
  it('accepts an index identical to the seed and rejects a stale one', () => {
    const seed = validSeed();
    expect(validateIndex(clone(seed), seed)).toEqual([]);
    expect(validateIndex(seed.slice(1), seed)).toHaveLength(1);
  });
});

describe('committed data', () => {
  const root = join(import.meta.dirname, '../..');
  const seedPath = join(root, 'data/cities.seed.json');
  const seed: unknown = JSON.parse(readFileSync(seedPath, 'utf8'));

  it('the curated city list passes every rule', () => {
    expect(validateSeed(seed)).toEqual([]);
  });

  it('has the planned 72 cities with a spread of archetypes', () => {
    const list = seed as SeedCity[];
    expect(list).toHaveLength(72);
    expect(new Set(list.map((c) => c.archetype)).size).toBe(10);
  });

  const worldPath = join(root, 'public/data/world.v1.json');
  it.skipIf(!existsSync(worldPath))('the generated world data passes every rule', () => {
    const world: unknown = JSON.parse(readFileSync(worldPath, 'utf8'));
    expect(validateWorld(world, seed)).toEqual([]);
  });
});
