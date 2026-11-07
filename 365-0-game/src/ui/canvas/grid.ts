// The year grid: twelve month columns of up to 31 tiles, drawn on one canvas (SPEC 6.2 and 6.6).
// The same renderer serves the draft preview, the reveal, the result thumbnail and the share image.
import type { DayType } from '../../engine/thresholds.ts';

export const GRID_COLS = 12;
export const GRID_ROWS = 31;

/** One month column. `null` days draws the empty outline of a month that is not picked yet. */
export interface GridColumn {
  days: readonly DayType[] | null;
  /**
   * A month the player has picked during the draft: its tiles are drawn as neutral blocks, so the
   * draft preview shows what is claimed without revealing the weather before the reveal.
   */
  claimed?: boolean;
}

export interface GridPalette {
  /** Fill of each day type. */
  fill: Record<DayType, string>;
  /** Pattern line colour for the four loss types. */
  pattern: Record<'r' | 's' | 'h' | 'f', string>;
  /** Outline of an empty or unresolved tile. */
  outline: string;
  /** Neutral fill of a claimed month in the draft preview. */
  claimed: string;
}

export interface GridOptions {
  /** Draw patterns over the loss types (pattern mode). */
  pattern: boolean;
  /**
   * Tiles resolved so far, counted month by month and top to bottom. The fractional part is the flip of
   * the tile being resolved. Defaults to everything.
   */
  revealed?: number;
  /**
   * Progress of each tile: 0 waiting, 0 to 1 flipping, 1 resolved. A value from 1 to 2 means resolved
   * with a gold flash still fading (flash strength is 2 minus the value). Overrides `revealed`.
   */
  tileProgress?: (index: number) => number;
  /** A column to highlight (the others are dimmed), e.g. the month tapped in the result list. */
  highlightColumn?: number | null;
  /** Opacity of a claimed column, for the quick fade-in when a pick lands. */
  claimedAlpha?: (column: number) => number;
  /** A short grid for the draft preview. */
  compact?: boolean;
  /** Explicit tile height and gap in CSS pixels (the share image uses its own). */
  metrics?: { tileH: number; gap: number };
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

export function gridLayout(
  width: number,
  compact = false,
  metrics?: { tileH: number; gap: number },
): GridLayout {
  const gap = metrics?.gap ?? (compact ? 1.5 : 2);
  const tileW = (width - gap * (GRID_COLS - 1)) / GRID_COLS;
  // The compact preview (draft screen) keeps the grid short so the city cards stay in the thumb zone.
  const tileH = metrics?.tileH ?? (compact ? 3.5 : Math.max(6, Math.floor(tileW * 0.36)));
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
    claimed: read('--on-well-muted'),
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
  const layout = gridLayout(cssWidth, options.compact === true, options.metrics);
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
  const progressOf =
    options.tileProgress ??
    ((i: number): number => (i < whole ? 1 : i === whole && frac > 0 ? frac : 0));
  const { tileW, tileH, gap } = layout;
  const radius = 3;
  const highlight = options.highlightColumn ?? null;
  let index = 0;

  for (let col = 0; col < GRID_COLS; col++) {
    const column = columns[col];
    const days = column?.days ?? null;
    const x = col * (tileW + gap);
    const dim = highlight !== null && highlight !== col;

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

    if (column?.claimed) {
      // Picked, weather not revealed yet: neutral blocks.
      ctx.fillStyle = palette.claimed;
      ctx.globalAlpha = 0.55 * (options.claimedAlpha ? options.claimedAlpha(col) : 1);
      for (let row = 0; row < days.length; row++, index++) {
        roundRect(ctx, x, row * (tileH + gap), tileW, tileH, radius);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      continue;
    }

    ctx.globalAlpha = dim ? 0.3 : 1;
    for (let row = 0; row < days.length; row++, index++) {
      const type = days[row] as DayType;
      const y = row * (tileH + gap);
      const p = progressOf(index);
      if (p >= 1) {
        ctx.fillStyle = palette.fill[type];
        roundRect(ctx, x, y, tileW, tileH, radius);
        ctx.fill();
        if (options.pattern && type !== 'p' && type !== 'o') {
          drawPattern(ctx, type, x, y, tileW, tileH, palette.pattern[type]);
        }
        if (p > 1 && p < 2 && type === 'p') {
          // A short gold flash on a perfect tile as it lands.
          ctx.fillStyle = '#ffffff';
          ctx.globalAlpha = (dim ? 0.3 : 1) * 0.6 * (2 - p);
          roundRect(ctx, x, y, tileW, tileH, radius);
          ctx.fill();
          ctx.globalAlpha = dim ? 0.3 : 1;
        }
      } else if (p > 0) {
        // The tile being resolved: a short flip, scaling from the middle.
        const h = Math.max(1, tileH * p);
        ctx.fillStyle = palette.fill[type];
        roundRect(ctx, x, y + (tileH - h) / 2, tileW, h, radius);
        ctx.fill();
      } else {
        // Waiting its turn.
        ctx.strokeStyle = palette.outline;
        ctx.globalAlpha = dim ? 0.1 : 0.25;
        ctx.lineWidth = 1;
        roundRect(ctx, x + 0.5, y + 0.5, tileW - 1, tileH - 1, radius);
        ctx.stroke();
        ctx.globalAlpha = dim ? 0.3 : 1;
      }
    }
    ctx.globalAlpha = 1;
  }
  return layout;
}
