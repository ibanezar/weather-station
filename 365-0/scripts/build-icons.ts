// `node scripts/build-icons.ts`: renders the app icons from one small year-grid mark.
// Run by hand when the mark changes; the PNGs are committed. Uses the Playwright Chromium
// (set PW_CHROMIUM_PATH to a system Chromium when the Playwright download is not installed).
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from '@playwright/test';
import { makeRng, randInt } from '../src/engine/rng.ts';

const root = join(import.meta.dirname, '..');
const out = join(root, 'public/icons');
mkdirSync(out, { recursive: true });

// The six day-type colours (docs/tokens.md) and the scoreboard background.
const COLORS = ['#FFB707', '#B1BCC7', '#316EDC', '#C082EB', '#EF512C', '#A2EDF6'];
const WEIGHTED = [0, 0, 0, 1, 1, 2, 2, 3, 4, 5]; // mostly gold, grey and blue, like a real year
const BACKGROUND = '#14202E';

/** A grid of tiles centred in a 512 box, kept inside the 80 percent maskable safe zone. */
function mark(): string {
  const cols = 5;
  const rows = 6;
  const tileW = 54;
  const tileH = 38;
  const gap = 12;
  const width = cols * tileW + (cols - 1) * gap;
  const height = rows * tileH + (rows - 1) * gap;
  const x0 = (512 - width) / 2;
  const y0 = (512 - height) / 2;
  const rng = makeRng('app-icon');
  const tiles: string[] = [];
  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) {
      const color = COLORS[WEIGHTED[randInt(rng, WEIGHTED.length)] as number] as string;
      tiles.push(
        `<rect x="${String(x0 + c * (tileW + gap))}" y="${String(y0 + r * (tileH + gap))}" width="${String(tileW)}" height="${String(tileH)}" rx="9" fill="${color}"/>`,
      );
    }
  }
  return tiles.join('');
}

const svg = (background: string): string =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">${background}${mark()}</svg>`;

// "any": rounded square. "maskable" and Apple: full bleed, the platform applies its own mask.
const rounded = svg(`<rect width="512" height="512" rx="112" fill="${BACKGROUND}"/>`);
const bleed = svg(`<rect width="512" height="512" fill="${BACKGROUND}"/>`);

writeFileSync(join(out, 'icon.svg'), rounded);

const browser = await chromium.launch({
  args: ['--no-sandbox'],
  ...(process.env['PW_CHROMIUM_PATH'] ? { executablePath: process.env['PW_CHROMIUM_PATH'] } : {}),
});
const page = await browser.newPage();
const render = async (source: string, size: number, file: string): Promise<void> => {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(
    `<style>html,body{margin:0;background:transparent}svg{display:block;width:${String(size)}px;height:${String(size)}px}</style>${source}`,
  );
  await page.screenshot({ path: join(out, file), omitBackground: true });
};
await render(rounded, 192, 'icon-192.png');
await render(rounded, 512, 'icon-512.png');
await render(bleed, 512, 'icon-maskable-512.png');
await render(bleed, 180, 'apple-touch-icon.png');
await render(rounded, 32, 'favicon-32.png');
await browser.close();
console.log('icons written to public/icons');
