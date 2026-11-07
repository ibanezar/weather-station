// Data validation entry point. Phase 0: no data exists yet, so this passes with a notice.
// Phase 1 replaces this with the full checks from SPEC 2.3 and fails on any violation.
import { existsSync } from 'node:fs';
import { join } from 'node:path';

const root = join(import.meta.dirname, '..');
const worldPath = join(root, 'public/data/world.v1.json');

if (!existsSync(worldPath)) {
  console.log('data:validate: no world data yet (expected before phase 1), nothing to check.');
} else {
  console.error('data:validate: world data exists but validation is not implemented yet.');
  process.exit(1);
}
