// One-off analysis for tuning the day-type thresholds (SPEC 1.4 says "tune after reviewing the data").
// Reads the cached API responses and prints, for each candidate threshold set, the share of perfect, ok
// and bad days over the whole world and how evenly perfect days are spread over city-months.
// Run: node scripts/tune.ts   (needs scripts/.cache; changes no files)
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { SeedCity } from '../src/data/types.ts';
import { DAILY_VARIABLES, type ApiResponse } from './lib/build.ts';
import { readCache } from './lib/fetch.ts';
import {
  classifyDay,
  THRESHOLDS,
  type DailyWeather,
  type DayType,
  type Thresholds,
} from '../src/engine/thresholds.ts';

const root = join(import.meta.dirname, '..');
const cities = JSON.parse(readFileSync(join(root, 'data/cities.seed.json'), 'utf8')) as SeedCity[];
const YEARS = Array.from({ length: 10 }, (_, i) => 2016 + i);

const base: Thresholds = THRESHOLDS;
const candidates: Record<string, Thresholds> = {
  'current (rain 1, tmin 9, 19-28, cloud 65)': base,
  'A: rain 2, tmin 7, 18-30, gust 45, cloud 75': {
    ...base,
    rain: { precipMmMin: 2 },
    perfect: {
      ...base.perfect,
      tminCMin: 7,
      tmaxCMin: 18,
      tmaxCMax: 30,
      gustKmhMax: 45,
      cloudPctMax: 75,
    },
  },
  'B: rain 3, tmin 6, 17-30, gust 45, cloud 80': {
    ...base,
    rain: { precipMmMin: 3 },
    perfect: {
      ...base.perfect,
      tminCMin: 6,
      tmaxCMin: 17,
      tmaxCMax: 30,
      gustKmhMax: 45,
      cloudPctMax: 80,
    },
  },
  'C: rain 3, tmin 5, 16-30, gust 50, cloud 85': {
    ...base,
    rain: { precipMmMin: 3 },
    perfect: {
      ...base.perfect,
      tminCMin: 5,
      tmaxCMin: 16,
      tmaxCMax: 30,
      gustKmhMax: 50,
      cloudPctMax: 85,
    },
  },
  'D: rain 4, tmin 5, 16-31, gust 50, cloud 85': {
    ...base,
    rain: { precipMmMin: 4 },
    perfect: {
      ...base.perfect,
      tminCMin: 5,
      tmaxCMin: 16,
      tmaxCMax: 31,
      gustKmhMax: 50,
      cloudPctMax: 85,
    },
  },
};

// Load every cached city-year once.
const loaded = cities.map((city) => {
  const years = YEARS.map((y) => readCache(join(root, 'scripts/.cache'), city.id, y));
  return { city, years };
});
const missing = loaded.reduce((n, c) => n + c.years.filter((y) => !y).length, 0);
console.log(`cities ${String(cities.length)}, missing city-years ${String(missing)}`);

function days(resp: ApiResponse): { month: number; day: DailyWeather }[] {
  const { daily } = resp;
  const out: { month: number; day: DailyWeather }[] = [];
  daily.time.forEach((date, i) => {
    const month = Number(date.slice(5, 7)) - 1;
    if (month === 1 && date.slice(8, 10) === '29') return;
    const v = (k: (typeof DAILY_VARIABLES)[number]): number => daily[k][i] as number;
    const cloud = daily.cloud_cover_mean[i];
    out.push({
      month,
      day: {
        tmax: v('temperature_2m_max'),
        tmin: v('temperature_2m_min'),
        precip: v('precipitation_sum'),
        snow: v('snowfall_sum'),
        gust: v('wind_gusts_10m_max'),
        code: v('weather_code'),
        cloud: cloud === null || cloud === undefined ? undefined : cloud,
      },
    });
  });
  return out;
}
const flat = loaded.map((c) => ({
  city: c.city,
  years: c.years.map((y) => (y ? days(y) : [])),
}));

const q = (a: number[], p: number): number =>
  [...a].sort((x, y) => x - y)[Math.floor(a.length * p)] as number;
const pct = (x: number): string => `${(x * 100).toFixed(1)}%`;
const watch = [
  'london',
  'ljubljana',
  'tokyo',
  'sydney',
  'singapore',
  'reykjavik',
  'cairo',
  'new-york',
];

for (const [name, t] of Object.entries(candidates)) {
  const tot: Record<string, number> = { p: 0, o: 0, l: 0 };
  const meanWins: number[] = [];
  const sdWins: number[] = [];
  const perCity: string[] = [];
  for (const c of flat) {
    const cityTot = { p: 0, o: 0, l: 0 };
    for (let m = 0; m < 12; m++) {
      const wins: number[] = [];
      for (const yr of c.years) {
        let w = 0;
        for (const d of yr) {
          if (d.month !== m) continue;
          const type: DayType = classifyDay(d.day, t);
          const key = type === 'p' ? 'p' : type === 'o' ? 'o' : 'l';
          tot[key] = (tot[key] ?? 0) + 1;
          cityTot[key] += 1;
          if (type === 'p') w += 1;
        }
        wins.push(w);
      }
      const mean = wins.reduce((a, b) => a + b, 0) / wins.length;
      meanWins.push(mean);
      sdWins.push(Math.sqrt(wins.reduce((a, b) => a + (b - mean) ** 2, 0) / wins.length));
    }
    if (watch.includes(c.city.id)) {
      const n = cityTot.p + cityTot.o + cityTot.l;
      perCity.push(
        `${c.city.id} ${pct(cityTot.p / n)}/${pct(cityTot.o / n)}/${pct(cityTot.l / n)}`,
      );
    }
  }
  const n = (tot['p'] ?? 0) + (tot['o'] ?? 0) + (tot['l'] ?? 0);
  const dead = meanWins.filter((m) => m < 1).length / meanWins.length;
  console.log(`\n== ${name}`);
  console.log(
    `perfect ${pct((tot['p'] ?? 0) / n)}  ok ${pct((tot['o'] ?? 0) / n)}  bad ${pct((tot['l'] ?? 0) / n)}`,
  );
  console.log(
    `mean perfect days per city-month  p25 ${q(meanWins, 0.25).toFixed(1)}  median ${q(meanWins, 0.5).toFixed(1)}  p75 ${q(meanWins, 0.75).toFixed(1)}  p90 ${q(meanWins, 0.9).toFixed(1)}   months with <1 on average: ${pct(dead)}`,
  );
  console.log(
    `spread (sd of perfect days over the 10 years)  median ${q(sdWins, 0.5).toFixed(1)}  p75 ${q(sdWins, 0.75).toFixed(1)}  p90 ${q(sdWins, 0.9).toFixed(1)}`,
  );
  console.log(`p/o/l by city: ${perCity.join(' | ')}`);
}
