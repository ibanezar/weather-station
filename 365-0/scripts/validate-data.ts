// `npm run data:validate`: fails if the curated list or the generated data break any rule in SPEC 2.3.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { validateIndex, validateSeed, validateWorld } from './lib/validate.ts';

const root = join(import.meta.dirname, '..');
const paths = {
  seed: join(root, 'data/cities.seed.json'),
  world: join(root, 'public/data/world.v1.json'),
  index: join(root, 'src/data/cities.index.json'),
};

function load(path: string): unknown {
  return JSON.parse(readFileSync(path, 'utf8'));
}

const errors: string[] = [];

if (!existsSync(paths.seed)) {
  errors.push('data/cities.seed.json is missing');
} else {
  const seed = load(paths.seed);
  errors.push(...validateSeed(seed));

  for (const [label, path] of [
    ['world', paths.world],
    ['index', paths.index],
  ] as const) {
    if (!existsSync(path)) {
      errors.push(`${label} data is missing (${path}); run npm run data`);
    } else if (label === 'world') {
      errors.push(...validateWorld(load(path), seed));
    } else {
      errors.push(...validateIndex(load(path), seed));
    }
  }
}

if (errors.length > 0) {
  console.error(`data:validate: ${String(errors.length)} problem(s)`);
  for (const e of errors.slice(0, 50)) console.error(`  - ${e}`);
  if (errors.length > 50) console.error(`  ... and ${String(errors.length - 50)} more`);
  process.exit(1);
}
console.log('data:validate: ok');
