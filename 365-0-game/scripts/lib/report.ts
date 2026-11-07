// Quality report for the generated data (SPEC 2.2 step 7), written to docs/data-report.md.
import { DAY_TYPE_CHARS, isLoss, type DayType } from '../../src/engine/thresholds.ts';
import { MONTHS_PER_YEAR, type SeedCity, type World } from '../../src/data/types.ts';
import { monthShare, WET_LEVELS_MM } from './build.ts';
import { PLANNED_YEARS } from './validate.ts';

export const SIZE_BUDGET_GZ = 120_000;
/** A city whose weather grid point is further than this from the real place is flagged. */
export const GRID_DISTANCE_WARN_KM = 30;
/** "More than 40 percent perfect days in every month" is suspicious (SPEC 2.2). */
export const ALWAYS_PERFECT_SHARE = 0.4;

export interface GridMeta {
  gridLat: number;
  gridLon: number;
  /** Height of the weather model's grid cell in metres. */
  elevation: number;
}

/**
 * Cities that are flagged by a rule but are correct, with the reason. Anything flagged and not
 * listed here is reported as unexplained.
 */
export const EXPLAINED: Record<string, string> = {
  singapore:
    'Mean temperature 26-28 °C all year, so daily highs (about 30-31 °C) sit above the 28 °C ceiling of a perfect day. Expected for the equator.',
  colombo:
    'Mean temperature 27-29 °C all year, so daily highs sit above the 28 °C ceiling of a perfect day. Expected for the tropics.',
  'la-paz':
    'About 3,700 m up: mean temperature 8-12 °C, so daily highs stay below the 19 °C floor of a perfect day. Expected.',
  ushuaia: 'Cold southern climate: mean temperature 1-11 °C, highs stay below 19 °C. Expected.',
  longyearbyen: 'Arctic: mean temperature -12 to 8 °C, highs stay below 19 °C. Expected.',
  'mcmurdo-station':
    'Antarctica: mean temperature -33 to -6 °C, almost every day is a freeze. Expected.',
};

export function distanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rad = Math.PI / 180;
  const a =
    Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
}

const pct = (x: number, digits = 0): string => (x * 100).toFixed(digits);

export interface Flag {
  id: string;
  rule: string;
  explained: string | undefined;
}

export interface ReportInput {
  seed: SeedCity[];
  world: World;
  meta: Record<string, GridMeta>;
  rawBytes: number;
  gzBytes: number;
  generated: string;
  /** Per city: share of days at or above each WET_LEVELS_MM level. Optional. */
  wetShare?: Record<string, number[]>;
}

export function findFlags(input: ReportInput): Flag[] {
  const flags: Flag[] = [];
  const add = (id: string, rule: string): void => {
    flags.push({ id, rule, explained: EXPLAINED[id] });
  };
  for (const c of input.seed) {
    const city = input.world.cities[c.id];
    if (!city) continue;
    const perfect = Array.from({ length: MONTHS_PER_YEAR }, (_, m) =>
      monthShare(city.d[m] ?? [], (t) => t === 'p'),
    );
    if (perfect.every((s) => s === 0)) add(c.id, 'no perfect days in any month');
    if (perfect.every((s) => s > ALWAYS_PERFECT_SHARE)) {
      add(c.id, `more than ${pct(ALWAYS_PERFECT_SHARE)}% perfect days in every month`);
    }
    const m = input.meta[c.id];
    if (m) {
      const km = distanceKm(c.lat, c.lon, m.gridLat, m.gridLon);
      if (km > GRID_DISTANCE_WARN_KM) {
        add(c.id, `weather grid point is ${km.toFixed(0)} km from the city`);
      }
    }
  }
  return flags;
}

export function renderReport(input: ReportInput): string {
  const { seed, world, meta } = input;
  const flags = findFlags(input);
  const unexplained = flags.filter((f) => f.explained === undefined);
  const lines: string[] = [];
  const out = (s = ''): void => {
    lines.push(s);
  };

  out('# World data report');
  out();
  out(
    `Generated ${input.generated} by \`npm run data\`. Source: Open-Meteo archive API, model ERA5 (0.25°).`,
  );
  out(`Years: ${world.years.join(', ')}. Cities: ${String(seed.length)}.`);
  if (world.years.length < PLANNED_YEARS) {
    out();
    out(
      `> **Interim data:** ${String(world.years.length)} of ${String(PLANNED_YEARS)} planned years. Statistics below are less stable until the remaining years are fetched.`,
    );
  }
  out();
  out('## Size');
  out();
  out(
    `world.v1.json: ${String(input.rawBytes)} bytes raw, ${String(input.gzBytes)} bytes gzipped ` +
      `(budget ${String(SIZE_BUDGET_GZ)}): ${input.gzBytes <= SIZE_BUDGET_GZ ? 'within budget' : 'OVER BUDGET'}.`,
  );
  out();

  // Overall day-type mix.
  const totals: Record<DayType, number> = { p: 0, o: 0, r: 0, s: 0, h: 0, f: 0 };
  let all = 0;
  for (const city of Object.values(world.cities)) {
    for (const month of city.d) {
      for (const s of month) {
        for (const ch of s) {
          totals[ch as DayType] += 1;
          all += 1;
        }
      }
    }
  }
  out('## Day-type mix, all cities and years');
  out();
  out('| type | share |');
  out('| --- | --- |');
  const names: Record<DayType, string> = {
    p: 'perfect',
    o: 'ok',
    r: 'rain',
    s: 'storm',
    h: 'heat',
    f: 'freeze',
  };
  for (const t of DAY_TYPE_CHARS) out(`| ${names[t]} | ${pct(totals[t] / all, 1)}% |`);
  const lossShare = DAY_TYPE_CHARS.filter(isLoss).reduce((a, t) => a + totals[t], 0) / all;
  out();
  out(
    `Wins ${pct(totals.p / all, 1)}%, draws ${pct(totals.o / all, 1)}%, losses ${pct(lossShare, 1)}%.`,
  );
  out();

  out('## Flags');
  out();
  if (flags.length === 0) {
    out('No suspicious cities.');
  } else {
    out('| city | rule | status |');
    out('| --- | --- | --- |');
    for (const f of flags) out(`| ${f.id} | ${f.rule} | ${f.explained ?? '**UNEXPLAINED**'} |`);
  }
  out();
  out(`${String(unexplained.length)} unexplained flag(s).`);
  out();

  out('## Scout buckets per month (cities per bucket 0 to 4)');
  out();
  out(
    'Perfect-day buckets, then bad-day buckets. Ties share a bucket, so a month with many equal values is lumpy.',
  );
  out();
  out('| month | perfect 0 / 1 / 2 / 3 / 4 | bad 0 / 1 / 2 / 3 / 4 |');
  out('| --- | --- | --- |');
  for (let m = 0; m < MONTHS_PER_YEAR; m++) {
    const count = (key: 'sp' | 'sb'): string => {
      const c = [0, 0, 0, 0, 0];
      for (const city of Object.values(world.cities))
        c[city[key][m] ?? 0] = (c[city[key][m] ?? 0] ?? 0) + 1;
      return c.join(' / ');
    };
    out(`| ${String(m + 1)} | ${count('sp')} | ${count('sb')} |`);
  }
  out();

  if (input.wetShare) {
    const levels = WET_LEVELS_MM.map((l) => `>= ${String(l)} mm`);
    out('## Rain threshold sensitivity');
    out();
    out(
      'Share of days with precipitation at or above each level. The current rain threshold is 1 mm. ' +
        'ERA5 is known to produce many light-rain days (drizzle), which can overstate how often it rains in the tropics; ' +
        'compare these columns to judge whether a higher threshold is needed.',
    );
    out();
    const all = Object.values(input.wetShare);
    const mean = WET_LEVELS_MM.map(
      (_, k) => all.reduce((a, w) => a + (w[k] ?? 0), 0) / Math.max(1, all.length),
    );
    out(`| city | ${levels.join(' | ')} |`);
    out(`| --- | ${levels.map(() => '---').join(' | ')} |`);
    out(`| **all cities (mean)** | ${mean.map((x) => pct(x)).join('% | ')}% |`);
    for (const c of seed) {
      const w = input.wetShare[c.id];
      if (w) out(`| ${c.id} | ${w.map((x) => pct(x)).join('% | ')}% |`);
    }
    out();
  }

  out('## Per city');
  out();
  out(
    'Grid: kilometres from the city to the model grid point, and the grid cell height in metres. ' +
      'Type columns are the share of days of each type over all fetched years: perfect / ok / rain / storm / heat / freeze, in percent. ' +
      'Months are the perfect-day share per month, in percent.',
  );
  out();
  out(
    '| city | grid km | grid m | perfect | ok | rain | storm | heat | freeze | ' +
      Array.from({ length: MONTHS_PER_YEAR }, (_, i) => `m${String(i + 1)}`).join(' | ') +
      ' |',
  );
  out(
    '| --- | --- | --- | --- | --- | --- | --- | --- | --- | ' + '--- | '.repeat(MONTHS_PER_YEAR),
  );
  for (const c of seed) {
    const city = world.cities[c.id];
    if (!city) continue;
    const mix: Record<DayType, number> = { p: 0, o: 0, r: 0, s: 0, h: 0, f: 0 };
    let n = 0;
    for (const month of city.d)
      for (const s of month)
        for (const ch of s) {
          mix[ch as DayType] += 1;
          n += 1;
        }
    const g = meta[c.id];
    const km = g ? distanceKm(c.lat, c.lon, g.gridLat, g.gridLon).toFixed(0) : '?';
    const elev = g ? g.elevation.toFixed(0) : '?';
    const months = Array.from({ length: MONTHS_PER_YEAR }, (_, m) =>
      pct(monthShare(city.d[m] ?? [], (t) => t === 'p')),
    );
    out(
      `| ${c.id} | ${km} | ${elev} | ${DAY_TYPE_CHARS.map((t) => pct(mix[t] / n)).join(' | ')} | ${months.join(' | ')} |`,
    );
  }
  out();
  return lines.join('\n');
}
