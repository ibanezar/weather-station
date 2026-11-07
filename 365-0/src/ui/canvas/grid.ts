// The year grid: twelve month columns of up to 31 tiles, drawn on one canvas (SPEC 6.2 and 6.6).
// The same renderer serves the draft preview, the reveal, the result thumbnail and the share image.
import type { DayType } from '../../engine/thresholds.ts';

export const GRID_COLS = 12;
export const GRID_ROWS = 31;

/** One month column. `null` days draws the empty outline of a month that is not picked yet. */
export interface GridColumn {
  days: readonly DayType[] | null;
}

export interface GridPalette {
  /** Fill of each day type. */
  fill: Record<DayType, string>;
  /** Pattern line colour for the four loss types. */
  pattern: Record<'r' | 's' | 'h' | 'f', string>;
  /** Outline of an empty or unresolved tile. */
  outline: string;
}

export interface GridOptions {
  /** Draw patterns over the loss types (pattern mode). */
  pattern: boolean;
  /**
   * Tiles resolved so far, counted month by month and top to bottom. The fractional part is the flip of
   * the tile being resolved. Defaults to everything.
   */
  revealed?: number;
  /** Device pixel ratio; defaults to the window's. */
  dpr?: number;
}

export interface GridLayout {
  width: number;
  height: number;
  tileW: number;
  tileH: number;
  gap: number;
}

export function gridLayout(width: number, gap = 2): GridLayout {
  const tileW = (width - gap * (GRID_COLS - 1)) / GRID_COLS;
  const tileH = Math.max(6, Math.floor(tileW * 0.36));
  const height = GRID_ROWS * tileH + (GRID_ROWS - 1) * gap;
  return { width, height, tileW, tileH, gap };
}

/** Resolve the design tokens to colours a canvas understands, in the context of `el`. */
export function resolvePalette(el: Element): GridPalette {
  const probe = document.createElement('span');
  probe.style.position = 'absolute';
  probe.style.visibility = 'hidden';
  el.append(probe);
  const read = (name: string): string => {
    probe.style.color = `var(${name})`;
    return getComputedStyle(probe).color;
  };
  const palette: GridPalette = {
    fill: {
      p: read('--day-perfect'),
      o: read('--day-ok'),
      r: read('--day-rain'),
      s: read('--day-storm'),
      h: read('--day-heat'),
      f: read('--day-freeze'),
    },
    pattern: {
      r: read('--pattern-on-rain'),
      s: read('--pattern-on-storm'),
      h: read('--pattern-on-heat'),
      f: read('--pattern-on-freeze'),
    },
    outline: read('--on-well-muted'),
  };
  probe.remove();
  return palette;
}

/** Total tiles in the picked months (the columns with days). */
export function tileCount(columns: readonly GridColumn[]): number {
  return columns.reduce((n, c) => n + (c.days?.length ?? 0), 0);
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  ctx.beginPath();
  // roundRect is missing in older WebViews; fall back to a plain rectangle.
  if (typeof ctx.roundRect === 'function') ctx.roundRect(x, y, w, h, r);
  else ctx.rect(x, y, w, h);
}

function drawPattern(
  ctx: CanvasRenderingContext2D,
  type: 'r' | 's' | 'h' | 'f',
  x: number,
  y: number,
  w: number,
  h: number,
  color: string,
): void {
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 1.2;
  const step = 4;
  if (type === 'h') {
    for (let px = x + 2; px < x + w; px += step) {
      for (let py = y + 2; py < y + h; py += step) {
        ctx.beginPath();
        ctx.arc(px, py, 0.9, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  } else if (type === 'f') {
    ctx.beginPath();
    for (let px = x + 1; px < x + w; px += step) {
      ctx.moveTo(px, y);
      ctx.lineTo(px, y + h);
    }
    ctx.stroke();
  } else {
    ctx.beginPath();
    for (let k = -h; k < w + h; k += step) {
      ctx.moveTo(x + k, y + h);
      ctx.lineTo(x + k + h, y); // rain and storm: lines rising to the right
      if (type === 's') {
        ctx.moveTo(x + k, y);
        ctx.lineTo(x + k + h, y + h); // storm adds the other diagonal: crosshatch
      }
    }
    ctx.stroke();
  }
  ctx.restore();
}

/** Draw the grid. Sets the canvas pixel size from its CSS width and returns the layout used. */
export function drawGrid(
  canvas: HTMLCanvasElement,
  columns: readonly GridColumn[],
  palette: GridPalette,
  options: GridOptions,
): GridLayout {
  const cssWidth = canvas.clientWidth || canvas.width;
  const layout = gridLayout(cssWidth);
  const dpr = options.dpr ?? window.devicePixelRatio;
  canvas.width = Math.round(layout.width * dpr);
  canvas.height = Math.round(layout.height * dpr);
  canvas.style.height = `${String(layout.height)}px`;

  const ctx = canvas.getContext('2d');
  if (!ctx) return layout;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, layout.width, layout.height);

  const total = tileCount(columns);
  const revealed = options.revealed ?? total;
  const whole = Math.floor(revealed);
  const frac = revealed - whole;
  const { tileW, tileH, gap } = layout;
  const radius = 3;
  let index = 0;

  for (let col = 0; col < GRID_COLS; col++) {
    const days = columns[col]?.days ?? null;
    const x = col * (tileW + gap);
    if (days === null) {
      // A month that is not picked yet: empty outlines.
      ctx.strokeStyle = palette.outline;
      ctx.globalAlpha = 0.35;
      ctx.lineWidth = 1;
      for (let row = 0; row < GRID_ROWS; row++) {
        const y = row * (tileH + gap);
        roundRect(ctx, x + 0.5, y + 0.5, tileW - 1, tileH - 1, radius);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      continue;
    }
    for (let row = 0; row < days.length; row++, index++) {
      const type = days[row] as DayType;
      const y = row * (tileH + gap);
      if (index < whole) {
        ctx.fillStyle = palette.fill[type];
        roundRect(ctx, x, y, tileW, tileH, radius);
        ctx.fill();
        if (options.pattern && type !== 'p' && type !== 'o') {
          drawPattern(ctx, type, x, y, tileW, tileH, palette.pattern[type]);
        }
      } else if (index === whole && frac > 0) {
        // The tile being resolved: a short flip, scaling from the middle.
        const h = Math.max(1, tileH * frac);
        ctx.fillStyle = palette.fill[type];
        roundRect(ctx, x, y + (tileH - h) / 2, tileW, h, radius);
        ctx.fill();
      } else {
        // Waiting its turn.
        ctx.strokeStyle = palette.outline;
        ctx.globalAlpha = 0.25;
        ctx.lineWidth = 1;
        roundRect(ctx, x + 0.5, y + 0.5, tileW - 1, tileH - 1, radius);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
    }
  }
  return layout;
}
