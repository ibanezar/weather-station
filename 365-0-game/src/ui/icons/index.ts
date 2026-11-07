// Custom icon set (SPEC 6.4): 24 px grid, 2 px rounded strokes, currentColor. No emoji.
import { svg } from '../dom.ts';

type Shape = [tag: 'path' | 'circle' | 'line', attrs: Record<string, string | number>];

const p = (d: string): Shape => ['path', { d }];
const circle = (cx: number, cy: number, r: number): Shape => ['circle', { cx, cy, r }];

const CLOUD = 'M17.5 18H7a4 4 0 0 1-.6-7.96A5.5 5.5 0 0 1 17 9.5 4.25 4.25 0 0 1 17.5 18z';
const CLOUD_HIGH = 'M17.5 14H7a4 4 0 0 1-.6-7.96A5.5 5.5 0 0 1 17 5.5 4.25 4.25 0 0 1 17.5 14z';

export const ICONS = {
  // The six day types.
  perfect: [
    circle(12, 12, 4),
    p(
      'M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
    ),
  ],
  ok: [p(CLOUD)],
  rain: [p(CLOUD_HIGH), p('M8 17l-1 3M12 17l-1 3M16 17l-1 3')],
  storm: [p(CLOUD_HIGH), p('M12.5 12.5l-2.5 4h4l-2.5 4')],
  heat: [p('M10 13.2V5a2 2 0 1 1 4 0v8.2a4.5 4.5 0 1 1-4 0z'), p('M12 9v7')],
  freeze: [
    p('M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9M9.5 4.5 12 7l2.5-2.5M9.5 19.5 12 17l2.5 2.5'),
  ],

  // Climate archetypes.
  desert: [p('M12 21V6M12 15H8a2 2 0 0 1-2-2V9M12 12h4a2 2 0 0 0 2-2V7M7 21h10')],
  monsoon: [p('M4 12a8 8 0 0 1 16 0z'), p('M12 12v6a2 2 0 0 1-4 0')],
  tropical: [p('M5 19C5 10 11 4 20 4c0 9-6 15-15 15z'), p('M5 19 14 10')],
  mediterranean: [
    p('M5 14a7 7 0 0 1 14 0'),
    p('M12 4v2M5 7l1.4 1.4M19 7l-1.4 1.4'),
    p('M3 18c2 0 2-1.5 4.5-1.5S10 18 12 18s2.5-1.5 4.5-1.5S19 18 21 18'),
  ],
  oceanic: [
    p('M2 8c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2'),
    p('M2 13c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2'),
    p('M2 18c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2'),
  ],
  continental: [
    p('M12 22V7M12 7V3'),
    p('M12 11c-2.5 0-4-1.5-4-4 2.5 0 4 1.5 4 4zM12 11c2.5 0 4-1.5 4-4-2.5 0-4 1.5-4 4z'),
    p('M12 17c-2.5 0-4-1.5-4-4 2.5 0 4 1.5 4 4zM12 17c2.5 0 4-1.5 4-4-2.5 0-4 1.5-4 4z'),
  ],
  subarctic: [p('M12 3l5 7h-3l4 6H6l4-6H7z'), p('M12 16v5')],
  polar: [p('M12 3l4 6 3 7H5l3-7z'), p('M12 3v13'), p('M2 19.5h20')],
  highland: [p('M2 20l7-12 4 7 3-4 6 9z')],
  island: [
    p('M5 19c1-3 3-4 7-4s6 1 7 4'),
    p('M12 15c0-3 0-5 1-8M13 7c-2-2-4-2-6-1M13 7c2-2 4-2 6-1'),
    p('M3 21.5h18'),
  ],

  // Interface.
  scout: [circle(11, 11, 6), p('M16 16l5 5')],
  undo: [p('M9 14 4 9l5-5'), p('M4 9h10a6 6 0 0 1 0 12h-3')],
  share: [p('M12 3v12M7 8l5-5 5 5'), p('M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5')],
  settings: [
    p('M4 6h8M18 6h2M4 12h2M12 12h8M4 18h10M20 18h0'),
    circle(15, 6, 2),
    circle(9, 12, 2),
    circle(17, 18, 2),
  ],
  check: [p('M5 12.5 9.5 17 19 7.5')],
  streak: [p('M12 3c1 3 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 .3 1.2 1 2 2 2 0-3-1-5 1-8z')],
  close: [p('M6 6l12 12M18 6 6 18')],
  refresh: [p('M20 11a8 8 0 0 0-14.5-4M4 4v4h4'), p('M4 13a8 8 0 0 0 14.5 4M20 20v-4h-4')],
  back: [p('M15 5l-7 7 7 7')],
  info: [circle(12, 12, 9), p('M12 11v5M12 7.5v.01')],
} satisfies Record<string, Shape[]>;

export type IconName = keyof typeof ICONS;

export const DAY_ICONS = ['perfect', 'ok', 'rain', 'storm', 'heat', 'freeze'] as const;
export const ARCHETYPE_ICONS = [
  'desert',
  'monsoon',
  'tropical',
  'mediterranean',
  'oceanic',
  'continental',
  'subarctic',
  'polar',
  'highland',
  'island',
] as const satisfies readonly IconName[];

export interface IconOptions {
  /** Accessible name. Omit for a decorative icon that sits next to visible text. */
  label?: string;
  size?: number;
}

export function icon(name: IconName, options: IconOptions = {}): SVGSVGElement {
  const size = options.size ?? 24;
  const el = svg('svg', {
    class: 'icon',
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    'stroke-width': 2,
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round',
    ...(options.label !== undefined
      ? { role: 'img', 'aria-label': options.label }
      : { 'aria-hidden': 'true', focusable: 'false' }),
  });
  for (const [tag, attrs] of ICONS[name]) {
    const child = svg(tag, null);
    for (const [k, v] of Object.entries(attrs)) child.setAttribute(k, String(v));
    el.append(child);
  }
  return el;
}
