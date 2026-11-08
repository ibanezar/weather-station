// Draws the dot map of the daily mystery: land as small dots, the three cities as numbered markers, the
// right one in the accent colour. Colours come from the design tokens, so both themes work.
import { isLand, project, type WorldMask } from '../../engine/worldmap.ts';

export interface MapMarker {
  latitude: number;
  longitude: number;
  /** 1, 2, 3: the number shown on the marker and in the list beside the map. */
  n: number;
  answer: boolean;
}

interface MapPalette {
  land: string;
  marker: string;
  onMarker: string;
  answer: string;
  onAnswer: string;
}

function resolve(el: Element): MapPalette {
  const probe = document.createElement('span');
  probe.style.position = 'absolute';
  probe.style.visibility = 'hidden';
  el.append(probe);
  const read = (name: string): string => {
    probe.style.color = `var(${name})`;
    return getComputedStyle(probe).color;
  };
  const palette = {
    land: read('--on-well-muted'),
    marker: read('--on-well'),
    onMarker: read('--well'),
    answer: read('--accent'),
    onAnswer: read('--on-accent'),
  };
  probe.remove();
  return palette;
}

/** Size the canvas to its box and paint the map. Call again when the box changes size or the theme does. */
export function drawWorldMap(
  canvas: HTMLCanvasElement,
  mask: WorldMask,
  markers: readonly MapMarker[],
): void {
  const width = canvas.clientWidth;
  const rows = mask.rows.length;
  const height = Math.round((width * rows) / mask.cols);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.height = `${String(height)}px`;
  const ctx = canvas.getContext('2d');
  if (!ctx || width === 0) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  const p = resolve(canvas);

  const cell = width / mask.cols;
  ctx.fillStyle = p.land;
  ctx.globalAlpha = 0.55;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < mask.cols; c++) {
      if (!isLand(mask, c, r)) continue;
      ctx.beginPath();
      ctx.arc((c + 0.5) * cell, (r + 0.5) * cell, cell * 0.34, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;

  // The wrong cities first, so the right one is never hidden under them.
  const ordered = [...markers].sort((a, b) => Number(a.answer) - Number(b.answer));
  const radius = Math.max(9, cell * 3.2);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = `700 ${String(Math.round(radius * 1.15))}px ${getComputedStyle(canvas).fontFamily}`;
  for (const m of ordered) {
    const { x, y } = project(mask, m.latitude, m.longitude);
    // Keep the whole marker on the canvas for places near an edge.
    const cx = Math.min(width - radius, Math.max(radius, x * width));
    const cy = Math.min(height - radius, Math.max(radius, y * height));
    ctx.beginPath();
    ctx.arc(cx, cy, m.answer ? radius * 1.12 : radius, 0, Math.PI * 2);
    ctx.fillStyle = m.answer ? p.answer : p.marker;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = p.onMarker;
    ctx.stroke();
    ctx.fillStyle = m.answer ? p.onAnswer : p.onMarker;
    ctx.fillText(String(m.n), cx, cy + 1);
  }
}
