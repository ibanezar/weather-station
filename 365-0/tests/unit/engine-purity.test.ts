import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const ENGINE_DIR = join(import.meta.dirname, '../../src/engine');
const FORBIDDEN = [
  /\bdocument\b/,
  /\bwindow\b/,
  /\bnavigator\b/,
  /\blocalStorage\b/,
  /\bMath\.random\b/,
  /\bDate\.now\b/,
  /\bnew Date\(\s*\)/,
];

function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
}

describe('engine purity', () => {
  const files = readdirSync(ENGINE_DIR).filter((f) => f.endsWith('.ts'));

  it('finds no DOM, clock or ambient randomness in src/engine', () => {
    for (const file of files) {
      const source = stripComments(readFileSync(join(ENGINE_DIR, file), 'utf8'));
      for (const pattern of FORBIDDEN) {
        expect(source, `${file} matches ${pattern.source}`).not.toMatch(pattern);
      }
    }
  });
});
