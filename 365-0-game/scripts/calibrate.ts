// `npm run calibrate`: simulate random-pick runs and print the grade distribution (SPEC 1.8).
//
//   node scripts/calibrate.ts [--runs=50000]
//
// A random player should land mostly in the bottom three tiers, and the top tier should be rare but
// reachable. Two more strategies (temperature only, and fully scouted) show how a player with some
// geography or scouting would grade. Tiers live in src/engine/grades.ts.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { SeedCity, World } from '../src/data/types.ts';
import { generateDraft } from '../src/engine/draft.ts';
import { GRADE_IDS, gradeFor, ratio, type GradeId } from '../src/engine/grades.ts';
import { makeRng, randInt } from '../src/engine/rng.ts';
import { bestPossible } from '../src/engine/score.ts';
import type { EngineData, WorldEvent } from '../src/engine/types.ts';

const root = join(import.meta.dirname, '..');
const read = (path: string): unknown => JSON.parse(readFileSync(join(root, path), 'utf8'));
const data: EngineData = {
  cities: read('data/cities.seed.json') as SeedCity[],
  world: read('public/data/world.v1.json') as World,
  events: read('data/events.json') as WorldEvent[],
};

const runsArg = process.argv.find((a) => a.startsWith('--runs='))?.slice('--runs='.length);
const runs = Number(runsArg ?? 50000);

type Strategy = 'random' | 'temperature' | 'scouted';

/** The middle of the 19 to 28 °C perfect band: a player with some geography picks close to it. */
const COMFORT_C = 23.5;

const results: Record<Strategy, { counts: Map<GradeId, number>; ratios: number[] }> = {
  random: { counts: new Map(GRADE_IDS.map((g) => [g, 0])), ratios: [] },
  temperature: { counts: new Map(GRADE_IDS.map((g) => [g, 0])), ratios: [] },
  scouted: { counts: new Map(GRADE_IDS.map((g) => [g, 0])), ratios: [] },
};
const bestWins: number[] = [];

for (let n = 0; n < runs; n++) {
  const seed = `calibrate:${String(n)}`;
  const draft = generateDraft(seed, data);
  const best = bestPossible(data, seed, draft);
  bestWins.push(best.record.w);
  const chooser = makeRng(seed, 'random-player');

  const wins: Record<Strategy, number> = { random: 0, temperature: 0, scouted: 0 };
  best.rounds.forEach((round, i) => {
    const month = draft[i]?.month ?? 0;
    const info = round.options.map((o) => {
      const c = data.world.cities[o.cityId];
      return {
        option: o,
        distance: Math.abs((c?.t[month] ?? 0) - COMFORT_C),
        scout: (c?.sp[month] ?? 0) - (c?.sb[month] ?? 0),
      };
    });
    wins.random += (round.options[randInt(chooser, 3)] ?? round.best).record.w;
    // Uses only what every card shows: the average temperature of the month.
    const byTemp = info.reduce((a, b) => (b.distance < a.distance ? b : a));
    wins.temperature += byTemp.option.record.w;
    // Uses all three scouts every round (more than the game allows): bars first, temperature second.
    const byScout = info.reduce((a, b) =>
      b.scout > a.scout || (b.scout === a.scout && b.distance < a.distance) ? b : a,
    );
    wins.scouted += byScout.option.record.w;
  });

  for (const strategy of Object.keys(results) as Strategy[]) {
    const r = ratio(wins[strategy], best.record.w);
    const res = results[strategy];
    res.ratios.push(r);
    const g = gradeFor(r);
    res.counts.set(g, (res.counts.get(g) ?? 0) + 1);
  }
}

const pct = (x: number): string => `${(x * 100).toFixed(2)}%`;
const quantile = (xs: number[], q: number): number => {
  const sorted = [...xs].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))] ?? 0;
};

const labels: Record<Strategy, string> = {
  random: 'Random picks',
  temperature: 'Picks the card closest to a comfortable temperature (no scouts)',
  scouted: 'Scouts every round (the game allows only 3), then temperature',
};
console.log(`Runs per strategy: ${String(runs)}\n`);
for (const strategy of Object.keys(results) as Strategy[]) {
  const { counts, ratios } = results[strategy];
  console.log(`### ${labels[strategy]}\n`);
  console.log('| grade | runs | share |');
  console.log('| --- | --- | --- |');
  for (const g of GRADE_IDS) {
    const c = counts.get(g) ?? 0;
    console.log(`| ${g} | ${String(c)} | ${pct(c / runs)} |`);
  }
  const bottom3 = (['stormbound', 'umbrella-carrier', 'drizzle-dodger'] as const).reduce(
    (a, g) => a + (counts.get(g) ?? 0),
    0,
  );
  console.log(
    `\nBottom three tiers: ${pct(bottom3 / runs)}. Ratio to best possible: median ` +
      `${quantile(ratios, 0.5).toFixed(3)}, p5 ${quantile(ratios, 0.05).toFixed(3)}, ` +
      `p95 ${quantile(ratios, 0.95).toFixed(3)}\n`,
  );
}
console.log(
  `Best possible perfect days: median ${String(quantile(bestWins, 0.5))}, ` +
    `min ${String(Math.min(...bestWins))}, max ${String(Math.max(...bestWins))}`,
);
