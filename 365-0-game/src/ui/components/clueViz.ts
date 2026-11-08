// Pictures for the clues of the daily mystery. They sit beside the written values (which stay, for screen
// readers and for exact numbers), so they are hidden from assistive technology.
import { h, svg } from '../dom.ts';

/** The temperature scale the range bar covers, in °C. */
export const TEMP_MIN = -40;
export const TEMP_MAX = 50;

const pct = (n: number): string => `${String(Math.round(n * 10) / 10)}%`;
const frac = (v: number, lo: number, hi: number): number =>
  Math.min(1, Math.max(0, (v - lo) / (hi - lo)));

/** A bar from the day's low to its high on a -40 to 50 °C scale, with a mark at freezing. */
export function rangeBar(low: number, high: number): HTMLElement {
  const left = frac(low, TEMP_MIN, TEMP_MAX) * 100;
  const right = frac(high, TEMP_MIN, TEMP_MAX) * 100;
  return h(
    'span',
    { class: 'viz viz--range', 'aria-hidden': 'true' },
    h('span', {
      class: 'viz__fill viz__fill--temp',
      style: `left:${pct(left)};width:${pct(Math.max(2, right - left))}`,
    }),
    h('span', { class: 'viz__zero', style: `left:${pct(frac(0, TEMP_MIN, TEMP_MAX) * 100)}` }),
  );
}

export type FillKind = 'cloud' | 'rain' | 'snow' | 'wind';

/** A bar filled to `value` out of `max` (the scale is the tool's, not the day's). */
export function fillBar(kind: FillKind, value: number, max: number): HTMLElement {
  return h(
    'span',
    { class: 'viz viz--fill', 'aria-hidden': 'true' },
    h('span', {
      class: `viz__fill viz__fill--${kind}`,
      style: `left:0;width:${pct(Math.max(value > 0 ? 2 : 0, frac(value, 0, max) * 100))}`,
    }),
  );
}

/**
 * The 24 hours as a ring: the daylight part in gold, centred on noon at the top, the night part dark.
 * `minutes` is the length of the day.
 */
export function dayDial(minutes: number): SVGElement {
  const r = 26;
  const c = 2 * Math.PI * r;
  const share = Math.min(1, Math.max(0, minutes / 1440));
  const start = -90 - share * 180; // the arc runs clockwise from here, so it is centred on 12 o'clock
  return svg(
    'svg',
    { class: 'viz viz--dial', viewBox: '0 0 64 64', width: 64, height: 64, 'aria-hidden': 'true' },
    svg('circle', { class: 'viz__night', cx: 32, cy: 32, r, fill: 'none', 'stroke-width': 9 }),
    share > 0
      ? svg('circle', {
          class: 'viz__day',
          cx: 32,
          cy: 32,
          r,
          fill: 'none',
          'stroke-width': 9,
          'stroke-dasharray': `${String(share * c)} ${String(c)}`,
          transform: `rotate(${String(start)} 32 32)`,
        })
      : null,
    svg('path', { class: 'viz__tick', d: 'M32 17v-6', 'stroke-width': 2 }),
  );
}
