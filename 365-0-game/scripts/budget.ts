// `npm run budget` (after `npm run build`): the size budgets of SPEC 10. Fails when the shipped
// JavaScript is over 150 KB gzipped (lazy-loaded data excluded) or the world data is over 120 KB.
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { gzipSync } from 'node:zlib';

const dist = join(import.meta.dirname, '../dist');
export const JS_BUDGET = 150_000;
export const WORLD_BUDGET = 120_000;

const gz = (file: string): number => gzipSync(readFileSync(file), { level: 9 }).length;

const assets = readdirSync(join(dist, 'assets')).filter((f) => f.endsWith('.js'));
const sizes = assets.map((f) => ({ file: f, bytes: gz(join(dist, 'assets', f)) }));
const jsTotal = sizes.reduce((a, s) => a + s.bytes, 0);
const world = gz(join(dist, 'data/world.v1.json'));

for (const s of sizes) console.log(`  ${s.file}: ${String(s.bytes)} bytes gzipped`);
console.log(`JavaScript total: ${String(jsTotal)} of ${String(JS_BUDGET)} bytes gzipped`);
console.log(`World data: ${String(world)} of ${String(WORLD_BUDGET)} bytes gzipped`);

const problems: string[] = [];
if (jsTotal > JS_BUDGET) problems.push('JavaScript is over its budget');
if (world > WORLD_BUDGET) problems.push('World data is over its budget');
if (problems.length > 0) {
  console.error(problems.join('; '));
  process.exit(1);
}
console.log('budget: ok');
