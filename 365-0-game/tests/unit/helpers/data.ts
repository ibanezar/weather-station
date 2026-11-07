// Loads the committed game data for engine tests.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { SeedCity, World } from '../../../src/data/types.ts';
import type { EngineData, WorldEvent } from '../../../src/engine/types.ts';

const root = join(import.meta.dirname, '../../..');
const read = (path: string): unknown => JSON.parse(readFileSync(join(root, path), 'utf8'));

export const data: EngineData = {
  cities: read('data/cities.seed.json') as SeedCity[],
  world: read('public/data/world.v1.json') as World,
  events: read('data/events.json') as WorldEvent[],
};

/** Deterministic test seeds. */
export const seeds = (n: number, prefix = 'test'): string[] =>
  Array.from({ length: n }, (_, i) => `${prefix}:${String(i)}`);
