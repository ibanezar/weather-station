// Pure data-building logic: API response in, classified day strings and scout buckets out.
import {
  DAYS_IN_MONTH,
  MONTHS_PER_YEAR,
  type SeedCity,
  type World,
  type WorldCity,
} from '../../src/data/types.ts';
import {
  classifyDay,
  isLoss,
  type DailyWeather,
  type DayType,
} from '../../src/engine/thresholds.ts';

/** Daily variables requested from the archive API (SPEC 2.2, plus the daily mean for the card). */
export const DAILY_VARIABLES = [
  'temperature_2m_max',
  'temperature_2m_min',
  'temperature_2m_mean',
  'precipitation_sum',
  'snowfall_sum',
  'wind_gusts_10m_max',
  'weather_code',
  'cloud_cover_mean',
] as const;
export type DailyVariable = (typeof DAILY_VARIABLES)[number];

export interface ApiResponse {
  latitude: number;
  longitude: number;
  elevation: number;
  timezone?: string;
  daily: { time: string[] } & Record<DailyVariable, (number | null)[]>;
}

export interface ParsedYear {
  /** One string per month, one character per day, 29 February dropped. */
  months: string[];
  /** Sum of daily mean temperature per month. */
  tempSum: number[];
  /** Days with a cloud-cover value missing (the cloud condition was skipped for those). */
  cloudMissing: number;
}

function fail(where: string, msg: string): never {
  throw new Error(`${where}: ${msg}`);
}

/** Classify one year of API data into twelve month strings. */
export function parseYear(resp: ApiResponse, year: number, where: string): ParsedYear {
  const { daily } = resp;
  const n = daily.time.length;
  for (const key of DAILY_VARIABLES) {
    if (daily[key].length !== n)
      fail(where, `${key} has ${String(daily[key].length)} values, expected ${String(n)}`);
  }

  const months: string[] = Array.from({ length: MONTHS_PER_YEAR }, () => '');
  const tempSum: number[] = Array.from({ length: MONTHS_PER_YEAR }, () => 0);
  let cloudMissing = 0;

  daily.time.forEach((date, i) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) fail(where, `bad date ${date}`);
    if (Number(date.slice(0, 4)) !== year) fail(where, `date ${date} is outside ${String(year)}`);
    const month = Number(date.slice(5, 7)) - 1;
    const dom = Number(date.slice(8, 10));
    if (month === 1 && dom === 29) return; // drop 29 February so February is always 28 days

    const need = (key: DailyVariable): number => {
      const v = daily[key][i];
      if (v === null || v === undefined || !Number.isFinite(v)) {
        return fail(where, `${key} is missing on ${date}`);
      }
      return v;
    };
    const cloud = daily.cloud_cover_mean[i];
    const hasCloud = cloud !== null && cloud !== undefined && Number.isFinite(cloud);
    if (!hasCloud) cloudMissing += 1;

    const day: DailyWeather = {
      tmax: need('temperature_2m_max'),
      tmin: need('temperature_2m_min'),
      precip: need('precipitation_sum'),
      snow: need('snowfall_sum'),
      gust: need('wind_gusts_10m_max'),
      code: need('weather_code'),
      cloud: hasCloud ? cloud : undefined,
    };
    months[month] = (months[month] ?? '') + classifyDay(day);
    tempSum[month] = (tempSum[month] ?? 0) + need('temperature_2m_mean');
  });

  months.forEach((s, m) => {
    const expected = DAYS_IN_MONTH[m] ?? 0;
    if (s.length !== expected) {
      fail(
        where,
        `month ${String(m + 1)} has ${String(s.length)} days, expected ${String(expected)}`,
      );
    }
  });
  return { months, tempSum, cloudMissing };
}

export interface CityDays {
  /** d[month][yearIndex] */
  d: string[][];
  /** Mean temperature per month in °C, one decimal. */
  t: number[];
}

/** Combine the parsed years (in year order) into one city's day strings and mean temperatures. */
export function combineYears(years: ParsedYear[]): CityDays {
  const d: string[][] = [];
  const t: number[] = [];
  for (let m = 0; m < MONTHS_PER_YEAR; m++) {
    d.push(years.map((y) => y.months[m] ?? ''));
    const sum = years.reduce((acc, y) => acc + (y.tempSum[m] ?? 0), 0);
    const days = years.length * (DAYS_IN_MONTH[m] ?? 1);
    t.push(Math.round((sum / days) * 10) / 10);
  }
  return { d, t };
}

/** Share of the days in one city-month (all years) that satisfy `pick`. */
export function monthShare(strings: string[], pick: (t: DayType) => boolean): number {
  let hit = 0;
  let total = 0;
  for (const s of strings) {
    for (const ch of s) {
      total += 1;
      if (pick(ch as DayType)) hit += 1;
    }
  }
  return total === 0 ? 0 : hit / total;
}

/**
 * Quintile bucket (0-4) of each value among all values, using midranks so equal values always share
 * a bucket. Higher value, higher bucket.
 */
export function quintileBuckets(values: number[]): number[] {
  const n = values.length;
  return values.map((v) => {
    let less = 0;
    let equal = 0;
    for (const x of values) {
      if (x < v) less += 1;
      else if (x === v) equal += 1;
    }
    const fraction = (less + equal / 2) / n;
    return Math.min(4, Math.floor(fraction * 5));
  });
}

/** Assemble the world file. `cities` must hold every seed city. */
export function buildWorld(
  seed: SeedCity[],
  cities: Record<string, CityDays>,
  years: number[],
): World {
  const out: Record<string, WorldCity> = {};
  for (const c of seed) {
    const data = cities[c.id];
    if (!data) fail(c.id, 'no data');
    out[c.id] = { t: data.t, sp: [], sb: [], d: data.d };
  }

  for (let m = 0; m < MONTHS_PER_YEAR; m++) {
    const perfect = seed.map((c) => monthShare(cities[c.id]?.d[m] ?? [], (t) => t === 'p'));
    const bad = seed.map((c) => monthShare(cities[c.id]?.d[m] ?? [], isLoss));
    const pb = quintileBuckets(perfect);
    const bb = quintileBuckets(bad);
    seed.forEach((c, i) => {
      const city = out[c.id];
      if (city) {
        city.sp.push(pb[i] ?? 0);
        city.sb.push(bb[i] ?? 0);
      }
    });
  }
  return { v: 1, years, cities: out };
}
