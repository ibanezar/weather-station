// The 365-0 mark: a year of weather as a grid of tiles, with the "0" (no bad days) picked out in gold.
// Pure data, no DOM: the app (logo component), scripts/build-icons.ts and the share image all read it,
// so the logo is the same everywhere.

/** Brand colours. Fixed on purpose: the mark sits on its own dark tile, in light and dark themes alike. */
export const BRAND = {
  background: '#14202E',
  gold: '#FFB707',
  /** The other day-type colours (docs/tokens.md), used dimmed for the weather around the zero. */
  weather: ['#316EDC', '#B1BCC7', '#C082EB', '#EF512C', '#A2EDF6'],
} as const;

/** A slashed zero on a 5 by 7 dot-matrix: '#' is a gold tile. */
export const ZERO = ['.###.', '#...#', '#..##', '#.#.#', '##..#', '#...#', '.###.'] as const;

export const MARK_COLS = 5;
export const MARK_ROWS = 7;

/** How much of a weather colour is kept when it is mixed into the dark background. */
const DIM = 0.3;

function mix(hex: string, into: string, keep: number): string {
  const channel = (h: string, i: number): number => parseInt(h.slice(1 + i * 2, 3 + i * 2), 16);
  const out = [0, 1, 2].map((i) =>
    Math.round(channel(hex, i) * keep + channel(into, i) * (1 - keep))
      .toString(16)
      .padStart(2, '0'),
  );
  return `#${out.join('')}`;
}

export interface MarkTile {
  /** Position in the 100 by 100 box of the mark. */
  x: number;
  y: number;
  w: number;
  h: number;
  fill: string;
  gold: boolean;
}

/** Plate corner radius in the 100 box. */
export const MARK_RADIUS = 22;

/** The tiles of the mark in a 100 by 100 box (the plate is the full box). */
export function markTiles(): MarkTile[] {
  const inner = 70;
  const gapX = 3;
  const gapY = 2.6;
  const w = (inner - (MARK_COLS - 1) * gapX) / MARK_COLS;
  const h = (inner - (MARK_ROWS - 1) * gapY) / MARK_ROWS;
  const x0 = (100 - inner) / 2;
  const y0 = (100 - inner) / 2;
  const dimmed = BRAND.weather.map((c) => mix(c, BRAND.background, DIM));
  // A fixed pattern, so every build draws the same mark.
  const order = [0, 2, 1, 3, 0, 4, 1, 2, 0, 3, 1, 0, 2, 4, 1, 3];
  let n = 0;
  const tiles: MarkTile[] = [];
  ZERO.forEach((row, r) => {
    Array.from(row).forEach((cell, c) => {
      const gold = cell === '#';
      tiles.push({
        x: x0 + c * (w + gapX),
        y: y0 + r * (h + gapY),
        w,
        h,
        gold,
        fill: gold ? BRAND.gold : (dimmed[order[n++ % order.length] as number] as string),
      });
    });
  });
  return tiles;
}

const r = (n: number): string => String(Math.round(n * 100) / 100);

/** The mark as an SVG string: the plate, then the tiles. `plate: 'none'` leaves the background out. */
export function markSvg(
  options: { plate?: 'rounded' | 'bleed' | 'none'; size?: number } = {},
): string {
  const plate = options.plate ?? 'rounded';
  const size =
    options.size === undefined
      ? ''
      : ` width="${String(options.size)}" height="${String(options.size)}"`;
  const bg =
    plate === 'none'
      ? ''
      : `<rect width="100" height="100" rx="${plate === 'rounded' ? String(MARK_RADIUS) : '0'}" fill="${BRAND.background}"/>`;
  const tiles = markTiles()
    .map(
      (t) =>
        `<rect x="${r(t.x)}" y="${r(t.y)}" width="${r(t.w)}" height="${r(t.h)}" rx="2.2" fill="${t.fill}"/>`,
    )
    .join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"${size}>${bg}${tiles}</svg>`;
}
