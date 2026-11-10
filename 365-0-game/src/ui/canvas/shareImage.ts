// The share image (SPEC 6.8): the year grid, the record, the grade, the date and mode, and the game
// address. 1080 x 1350 (4:5) for feeds and 1080 x 1920 for stories. Always drawn as a dark scoreboard,
// whatever theme the player uses, so it looks the same wherever it is posted.
import type { ShareImageModel } from '../../engine/share.ts';
import { formatRecord } from '../../engine/share.ts';
import { drawGrid, GRID_COLS, GRID_ROWS, resolvePalette, type GridColumn } from './grid.ts';

export type ShareFormat = 'feed' | 'story';

export const SHARE_SIZES: Record<ShareFormat, { width: number; height: number }> = {
  feed: { width: 1080, height: 1350 },
  story: { width: 1080, height: 1920 },
};

export interface ShareImageText {
  title: string;
  /** "daily 2026-11-06" or "endless". */
  subtitle: string;
  gradeTitle: string;
  bestLine: string;
  contractLine?: string;
  youLine: string;
  /** Three letters per month column. */
  abbreviations: readonly string[];
  /** The game address shown at the bottom. */
  url: string;
}

export interface ShareLayout {
  width: number;
  height: number;
  margin: number;
  /** Baselines and boxes, in pixels. */
  titleY: number;
  recordY: number;
  /** Largest font size of the record; it shrinks to fit when the record is long. */
  recordSize: number;
  recordMaxWidth: number;
  gradeY: number;
  bestY: number;
  labelsY: number;
  grid: { x: number; y: number; width: number; tileH: number; gap: number; height: number };
  urlY: number;
}

/** Pure layout, so it can be tested without a canvas. */
export function shareLayout(format: ShareFormat): ShareLayout {
  const { width, height } = SHARE_SIZES[format];
  const margin = 60;
  const gridWidth = width - margin * 2;
  const gap = 4;
  const story = format === 'story';
  // Spread the grid over the space left below the text.
  const gridTop = story ? 760 : 640;
  const gridBottom = height - (story ? 220 : 110);
  const rows = GRID_ROWS;
  const tileH = Math.floor((gridBottom - gridTop - gap * (rows - 1)) / rows);
  const gridHeight = rows * tileH + (rows - 1) * gap;
  return {
    width,
    height,
    margin,
    titleY: story ? 150 : 110,
    recordY: story ? 450 : 350,
    recordSize: story ? 260 : 236,
    recordMaxWidth: gridWidth,
    gradeY: story ? 580 : 480,
    bestY: story ? 660 : 548,
    labelsY: gridTop - 14,
    grid: { x: margin, y: gridTop, width: gridWidth, tileH, gap, height: gridHeight },
    urlY: height - (story ? 110 : 50),
  };
}

/** Make sure the display and UI fonts are ready for canvas text (they load lazily by unicode range). */
async function loadFonts(sample: string): Promise<void> {
  await Promise.all([
    document.fonts.load('900 100px "Big Shoulders Display Variable"', sample),
    document.fonts.load('800 100px "Big Shoulders Display Variable"', sample),
    document.fonts.load('600 40px "Instrument Sans Variable"', sample),
  ]);
}

function fitFont(
  ctx: CanvasRenderingContext2D,
  text: string,
  weight: number,
  family: string,
  size: number,
  maxWidth: number,
): number {
  let px = size;
  for (; px > 20; px -= 4) {
    ctx.font = `${String(weight)} ${String(px)}px ${family}`;
    if (ctx.measureText(text).width <= maxWidth) break;
  }
  return px;
}

const DISPLAY = '"Big Shoulders Display Variable", "Arial Narrow", sans-serif';
const UI = '"Instrument Sans Variable", system-ui, sans-serif';

/** Draw the share image. `patterns` follows the player's pattern-mode setting. */
export async function renderShareImage(
  model: ShareImageModel,
  text: ShareImageText,
  format: ShareFormat,
  patterns: boolean,
): Promise<HTMLCanvasElement> {
  const L = shareLayout(format);
  await loadFonts(
    `${text.title} ${text.subtitle} ${formatRecord(model.record)} ${text.gradeTitle} ${text.bestLine} ${text.contractLine ?? ''}`,
  );

  const canvas = document.createElement('canvas');
  canvas.width = L.width;
  canvas.height = L.height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas is not available');

  // Colours come from the design tokens, so the image matches the app.
  const probe = document.createElement('div');
  probe.className = 'well';
  probe.style.position = 'absolute';
  probe.style.visibility = 'hidden';
  document.body.append(probe);
  const style = getComputedStyle(probe);
  const wellColor = style.backgroundColor;
  const textColor = style.color;
  const palette = resolvePalette(probe);
  probe.remove();

  ctx.fillStyle = wellColor;
  ctx.fillRect(0, 0, L.width, L.height);
  ctx.textBaseline = 'alphabetic';

  // Title and subtitle.
  ctx.fillStyle = textColor;
  ctx.font = `800 72px ${DISPLAY}`;
  ctx.textAlign = 'left';
  ctx.fillText(text.title, L.margin, L.titleY);
  ctx.font = `600 36px ${UI}`;
  ctx.fillStyle = palette.outline;
  ctx.textAlign = 'right';
  ctx.fillText(text.subtitle, L.width - L.margin, L.titleY - 8);

  // The record.
  const record = formatRecord(model.record);
  ctx.textAlign = 'left';
  ctx.fillStyle = textColor;
  const recordPx = fitFont(ctx, record, 900, DISPLAY, L.recordSize, L.recordMaxWidth);
  ctx.font = `900 ${String(recordPx)}px ${DISPLAY}`;
  ctx.fillText(record, L.margin, L.recordY);

  // Grade and best possible.
  const gradePx = fitFont(ctx, text.gradeTitle, 800, DISPLAY, 104, L.recordMaxWidth);
  ctx.font = `800 ${String(gradePx)}px ${DISPLAY}`;
  ctx.fillText(text.gradeTitle, L.margin, L.gradeY);
  ctx.font = `600 38px ${UI}`;
  ctx.fillStyle = textColor;
  ctx.fillText(text.bestLine, L.margin, L.bestY);
  const bestWidth = ctx.measureText(`${text.bestLine}   `).width;
  ctx.fillStyle = palette.outline;
  ctx.fillText(text.youLine, L.margin + bestWidth, L.bestY);
  if (text.contractLine) {
    const contractPx = fitFont(ctx, text.contractLine, 600, UI, 32, L.recordMaxWidth);
    ctx.font = `600 ${String(contractPx)}px ${UI}`;
    ctx.fillStyle = palette.outline;
    ctx.fillText(text.contractLine, L.margin, L.bestY + 48);
  }

  // The grid, drawn on its own canvas with the same renderer as the app.
  const columns: GridColumn[] = model.months.map((m) => ({ days: m.days }));
  const gridCanvas = document.createElement('canvas');
  gridCanvas.width = L.grid.width;
  drawGrid(gridCanvas, columns, palette, {
    pattern: patterns,
    dpr: 1,
    metrics: { tileH: L.grid.tileH, gap: L.grid.gap },
  });
  ctx.drawImage(gridCanvas, L.grid.x, L.grid.y);

  // Column labels above the grid.
  ctx.font = `700 30px ${DISPLAY}`;
  ctx.fillStyle = palette.outline;
  ctx.textAlign = 'center';
  const colW = (L.grid.width - L.grid.gap * (GRID_COLS - 1)) / GRID_COLS;
  text.abbreviations.forEach((a, i) => {
    ctx.fillText(a, L.grid.x + i * (colW + L.grid.gap) + colW / 2, L.labelsY);
  });

  // The address.
  ctx.font = `600 34px ${UI}`;
  ctx.fillStyle = textColor;
  ctx.textAlign = 'left';
  ctx.fillText(text.url, L.margin, L.urlY);
  return canvas;
}

/**
 * Encode the canvas as a PNG. This deliberately uses the synchronous toDataURL: canvas.toBlob is
 * scheduled as an idle-time task in Chromium and measured 6.7 s to call back on a busy page, which
 * is far too long after a tap. toDataURL blocks the main thread for a short, bounded moment instead.
 */
export function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  const url = canvas.toDataURL('image/png');
  const binary = atob(url.slice(url.indexOf(',') + 1));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return Promise.resolve(new Blob([bytes], { type: 'image/png' }));
}
