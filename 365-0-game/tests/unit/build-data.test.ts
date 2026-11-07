import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  buildWorld,
  combineYears,
  DAILY_VARIABLES,
  monthShare,
  parseYear,
  quintileBuckets,
  WET_LEVELS_MM,
  type ApiResponse,
} from '../../scripts/lib/build.ts';
import { buildUrl, classifyLimit } from '../../scripts/lib/fetch.ts';
import { distanceKm, EXPLAINED, findFlags } from '../../scripts/lib/report.ts';
import { DAYS_IN_MONTH, type SeedCity } from '../../src/data/types.ts';

type Day = Partial<Record<(typeof DAILY_VARIABLES)[number], number | null>>;

const GOOD: Required<Day> = {
  temperature_2m_max: 24,
  temperature_2m_min: 14,
  temperature_2m_mean: 19,
  precipitation_sum: 0,
  snowfall_sum: 0,
  wind_gusts_10m_max: 20,
  weather_code: 1,
  cloud_cover_mean: 30,
};

/** A full calendar year of API data; `at(date)` can override single days. */
function fakeYear(year: number, at: (date: string) => Day = () => ({})): ApiResponse {
  const leap = year % 4 === 0;
  const dim = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const time: string[] = [];
  dim.forEach((n, m) => {
    for (let d = 1; d <= n; d++) {
      time.push(`${String(year)}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`);
    }
  });
  const daily = { time } as ApiResponse['daily'];
  for (const key of DAILY_VARIABLES) {
    daily[key] = time.map((date) => {
      const v = { ...GOOD, ...at(date) }[key];
      return v;
    });
  }
  return { latitude: 0, longitude: 0, elevation: 0, daily };
}

describe('parseYear', () => {
  it('turns a year into twelve strings of the right length', () => {
    const y = parseYear(fakeYear(2017), 2017, 't');
    expect(y.months.map((s) => s.length)).toEqual([...DAYS_IN_MONTH]);
    expect(y.months.every((s) => /^p+$/.test(s))).toBe(true);
  });

  it('drops 29 February in a leap year so February stays at 28 days', () => {
    const y = parseYear(
      fakeYear(2016, (d) => (d.endsWith('-02-29') ? { precipitation_sum: 50 } : {})),
      2016,
      't',
    );
    expect(y.months[1]).toHaveLength(28);
    expect(y.months[1]).not.toContain('s');
  });

  it('classifies individual days into the right month position', () => {
    const y = parseYear(
      fakeYear(2018, (d) => {
        if (d === '2018-03-01') return { precipitation_sum: 5 };
        if (d === '2018-03-31') return { temperature_2m_max: 36 };
        if (d === '2018-07-04') return { weather_code: 95 };
        return {};
      }),
      2018,
      't',
    );
    expect(y.months[2]?.[0]).toBe('r');
    expect(y.months[2]?.[30]).toBe('h');
    expect(y.months[6]?.[3]).toBe('s');
  });

  it('averages daily mean temperature per month', () => {
    const y = parseYear(fakeYear(2018), 2018, 't');
    expect(y.tempSum[0]).toBeCloseTo(19 * 31);
  });

  it('skips the cloud condition for a day with no cloud value and counts it', () => {
    const y = parseYear(
      fakeYear(2018, (d) => (d === '2018-05-05' ? { cloud_cover_mean: null } : {})),
      2018,
      't',
    );
    expect(y.months[4]?.[4]).toBe('p');
    expect(y.cloudMissing).toBe(1);
  });

  it('counts wet days at each precipitation level and combines them into shares', () => {
    const rainfall: Record<string, number> = {
      '2018-03-01': 0.5,
      '2018-03-02': 1.5,
      '2018-03-03': 2.5,
      '2018-03-04': 6,
    };
    const y = parseYear(
      fakeYear(2018, (d) => (d in rainfall ? { precipitation_sum: rainfall[d] ?? 0 } : {})),
      2018,
      't',
    );
    expect(WET_LEVELS_MM).toEqual([1, 2, 3, 5]);
    expect(y.days).toBe(365);
    expect(y.wetDays).toEqual([3, 2, 1, 1]); // >=1mm: 1.5, 2.5, 6; >=2: 2.5, 6; >=3: 6; >=5: 6
    const city = combineYears([y, parseYear(fakeYear(2019), 2019, 't')]);
    expect(city.wetShare[0]).toBeCloseTo(3 / 730);
    expect(city.wetShare[3]).toBeCloseTo(1 / 730);
  });

  it('throws on a missing required value', () => {
    const resp = fakeYear(2018, (d) => (d === '2018-05-05' ? { temperature_2m_max: null } : {}));
    expect(() => parseYear(resp, 2018, 'x')).toThrow(/temperature_2m_max is missing on 2018-05-05/);
  });

  it('throws when a day is missing from a month', () => {
    const resp = fakeYear(2018);
    for (const key of [...DAILY_VARIABLES, 'time'] as const) resp.daily[key].splice(10, 1);
    expect(() => parseYear(resp, 2018, 'x')).toThrow(/month 1 has 30 days/);
  });

  it('throws when the data belongs to another year', () => {
    expect(() => parseYear(fakeYear(2019), 2018, 'x')).toThrow(/outside 2018/);
  });
});

describe('quintileBuckets', () => {
  it('spreads distinct values evenly over 0 to 4', () => {
    const buckets = quintileBuckets(Array.from({ length: 10 }, (_, i) => i));
    expect(buckets).toEqual([0, 0, 1, 1, 2, 2, 3, 3, 4, 4]);
  });

  it('gives equal values the same bucket', () => {
    const buckets = quintileBuckets([0, 0, 0, 0, 0, 0, 0, 0, 5, 9]);
    expect(new Set(buckets.slice(0, 8)).size).toBe(1);
    expect(buckets[9]).toBe(4);
  });

  it('keeps every bucket inside 0 to 4', () => {
    for (const b of quintileBuckets([3, 3, 3])) expect(b).toBeGreaterThanOrEqual(0);
    for (const b of quintileBuckets([1, 2, 3, 4, 5, 6, 7])) expect(b).toBeLessThanOrEqual(4);
  });
});

describe('monthShare', () => {
  it('counts the share of matching days across all years', () => {
    expect(monthShare(['pppp', 'oooo'], (t) => t === 'p')).toBe(0.5);
    expect(monthShare([], () => true)).toBe(0);
  });
});

describe('buildWorld', () => {
  const mk = (id: string): SeedCity => ({
    id,
    name: { en: id },
    country: 'SI',
    continent: 'europe',
    lat: 46,
    lon: 14,
    archetype: 'continental',
    tags: ['continental'],
  });

  it('gives sunnier cities higher perfect buckets and rainier ones higher bad buckets', () => {
    const seed = ['a', 'b', 'c', 'd', 'e'].map(mk);
    const cities: Record<string, ReturnType<typeof combineYears>> = {};
    seed.forEach((c, i) => {
      const wet = i; // 0 = no rain at all, 4 = very wet
      const years = [2017, 2018].map((y) =>
        parseYear(
          fakeYear(y, (d) => (Number(d.slice(8, 10)) <= wet * 5 ? { precipitation_sum: 3 } : {})),
          y,
          c.id,
        ),
      );
      cities[c.id] = combineYears(years);
    });
    const world = buildWorld(seed, cities, [2017, 2018]);
    const jan = (id: string, key: 'sp' | 'sb'): number => world.cities[id]?.[key][0] ?? -1;
    expect(jan('a', 'sp')).toBeGreaterThan(jan('e', 'sp'));
    expect(jan('e', 'sb')).toBeGreaterThan(jan('a', 'sb'));
    expect(world.v).toBe(1);
    expect(world.cities['a']?.t).toHaveLength(12);
    expect(world.cities['a']?.t[0]).toBe(19);
  });
});

describe('fetch helpers', () => {
  it('classifies the limit messages the API sends', () => {
    expect(classifyLimit('Daily API request limit exceeded. Please try again tomorrow.')).toBe(
      'daily',
    );
    expect(
      classifyLimit('Hourly API request limit exceeded. Please try again in the next hour.'),
    ).toBe('hourly');
    expect(
      classifyLimit('Minutely API request limit exceeded. Please try again in one minute.'),
    ).toBe('minutely');
    expect(classifyLimit('Something else')).toBe('other');
  });

  it('builds a request for one calendar year with all variables and the ERA5 model', () => {
    const url = new URL(buildUrl({ lat: 46.057, lon: 14.506 }, 2020));
    expect(url.hostname).toBe('archive-api.open-meteo.com');
    expect(url.searchParams.get('start_date')).toBe('2020-01-01');
    expect(url.searchParams.get('end_date')).toBe('2020-12-31');
    expect(url.searchParams.get('models')).toBe('era5');
    expect(url.searchParams.get('timezone')).toBe('auto');
    expect(url.searchParams.get('daily')?.split(',')).toEqual([...DAILY_VARIABLES]);
  });
});

describe('report helpers', () => {
  it('only explains cities that exist in the seed list', () => {
    const ids = new Set(
      (
        JSON.parse(
          readFileSync(join(import.meta.dirname, '../../data/cities.seed.json'), 'utf8'),
        ) as SeedCity[]
      ).map((c) => c.id),
    );
    for (const id of Object.keys(EXPLAINED)) expect(ids.has(id), id).toBe(true);
  });

  it('measures distance in kilometres', () => {
    expect(distanceKm(46, 14, 46, 14)).toBe(0);
    expect(distanceKm(0, 0, 0, 1)).toBeCloseTo(111.2, 0);
  });

  it('flags a city with no perfect days and a distant grid point', () => {
    const seed: SeedCity[] = [
      {
        id: 'cold',
        name: { en: 'Cold' },
        country: 'AQ',
        continent: 'oceania',
        lat: -77,
        lon: 166,
        archetype: 'polar',
        tags: ['polar'],
      },
    ];
    const d = Array.from({ length: 12 }, (_, m) => ['f'.repeat(DAYS_IN_MONTH[m] ?? 0)]);
    const world = {
      v: 1 as const,
      years: [2020],
      cities: {
        cold: {
          t: Array<number>(12).fill(-20),
          sp: Array<number>(12).fill(0),
          sb: Array<number>(12).fill(4),
          d,
        },
      },
    };
    const flags = findFlags({
      seed,
      world,
      meta: { cold: { gridLat: -77, gridLon: 170, elevation: 10 } },
      rawBytes: 0,
      gzBytes: 0,
      generated: 'x',
    });
    expect(flags.map((f) => f.rule)).toEqual([
      'no perfect days in any month',
      expect.stringMatching(/km from the city/),
    ]);
  });
});
