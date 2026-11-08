// Reads src/styles/tokens.css and checks the colour pairs that matter (SPEC 6.3).
import {
  contrast,
  deltaE,
  oklchToRgb,
  parseOklch,
  rgbToHex,
  rgbToOklch,
  simulate,
  type Cvd,
  type Rgb,
} from './color.ts';

export type Theme = 'light' | 'dark';

/** The day-type token names, in the order the game lists them. */
export const DAY_TOKENS = [
  '--day-perfect',
  '--day-ok',
  '--day-rain',
  '--day-storm',
  '--day-heat',
  '--day-freeze',
] as const;

/** Text needs 4.5:1; graphical objects and large text need 3:1 (WCAG 2.2 AA). */
export const TEXT_MIN = 4.5;
export const GRAPHIC_MIN = 3;
/** Any two day-type colours must stay at least this far apart (OKLab) under every simulation. */
export const CVD_MIN_DELTA_E = 0.1;

/** [foreground, background, minimum ratio, what it is]. */
export const PAIRS: readonly (readonly [string, string, number, string])[] = [
  ['--ink', '--surface', TEXT_MIN, 'body text on the page'],
  ['--ink', '--raised', TEXT_MIN, 'text on cards'],
  ['--ink-muted', '--surface', TEXT_MIN, 'secondary text on the page'],
  ['--ink-muted', '--raised', TEXT_MIN, 'secondary text on cards'],
  ['--on-accent', '--accent', TEXT_MIN, 'label on the gold button'],
  ...(['perfect', 'freeze', 'rain', 'storm', 'heat'] as const).map(
    (t) => [`--on-day-${t}`, `--day-${t}`, TEXT_MIN, `label on the ${t} chase button`] as const,
  ),
  ['--surface', '--ink', TEXT_MIN, 'text on the inverted toast'],
  ['--on-well', '--well', TEXT_MIN, 'labels on the grid panel'],
  ['--on-well-muted', '--well', TEXT_MIN, 'month names on the grid panel'],
  ['--ink', '--surface', GRAPHIC_MIN, 'focus ring on the page'],
  ['--ink', '--raised', GRAPHIC_MIN, 'focus ring on cards'],
  ['--on-well', '--well', GRAPHIC_MIN, 'focus ring on the grid panel'],
  ['--ink-muted', '--raised', GRAPHIC_MIN, 'step outlines and icons on cards'],
  ...DAY_TOKENS.map(
    (t) => [t, '--well', GRAPHIC_MIN, `${t.slice(6)} tiles on the grid panel`] as const,
  ),
];

export interface ParsedTokens {
  /** Raw value per custom property from the first :root block. */
  raw: Map<string, string>;
}

export function parseTokens(css: string): ParsedTokens {
  const raw = new Map<string, string>();
  const block = /:root\s*\{([\s\S]*?)\n\}/.exec(css);
  if (!block?.[1]) throw new Error('no :root block found in tokens.css');
  for (const m of block[1].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    if (m[1] && m[2]) raw.set(m[1], m[2].trim().replace(/\s+/g, ' '));
  }
  return { raw };
}

/** Resolve a token to an sRGB colour for a theme, following var() and light-dark(). */
export function resolveColor(tokens: ParsedTokens, name: string, theme: Theme, depth = 0): Rgb {
  if (depth > 8) throw new Error(`token loop at ${name}`);
  const value = tokens.raw.get(name);
  if (value === undefined) throw new Error(`unknown token ${name}`);
  const v = /^var\((--[\w-]+)\)$/.exec(value);
  if (v?.[1]) return resolveColor(tokens, v[1], theme, depth + 1);
  const ld = /^light-dark\(\s*(oklch\([^)]*\))\s*,\s*(oklch\([^)]*\))\s*\)$/.exec(value);
  if (ld?.[1] && ld[2]) return oklchToRgb(parseOklch(theme === 'light' ? ld[1] : ld[2]));
  return oklchToRgb(parseOklch(value));
}

export interface PairResult {
  fg: string;
  bg: string;
  theme: Theme;
  min: number;
  what: string;
  ratio: number;
  ok: boolean;
}

export function checkPairs(tokens: ParsedTokens): PairResult[] {
  const out: PairResult[] = [];
  for (const theme of ['light', 'dark'] as const) {
    for (const [fg, bg, min, what] of PAIRS) {
      const ratio = contrast(resolveColor(tokens, fg, theme), resolveColor(tokens, bg, theme));
      out.push({ fg, bg, theme, min, what, ratio, ok: ratio >= min });
    }
  }
  return out;
}

export interface CvdResult {
  vision: 'normal' | Cvd;
  a: string;
  b: string;
  distance: number;
  ok: boolean;
}

export const VISIONS: readonly ('normal' | Cvd)[] = [
  'normal',
  'protanopia',
  'deuteranopia',
  'tritanopia',
];

export function checkCvd(tokens: ParsedTokens): CvdResult[] {
  // Day types are the same in both themes (the grid panel is dark in both), so check the light set.
  const colors = DAY_TOKENS.map((t) => [t, resolveColor(tokens, t, 'light')] as const);
  const out: CvdResult[] = [];
  for (const vision of VISIONS) {
    for (let i = 0; i < colors.length; i++) {
      for (let j = i + 1; j < colors.length; j++) {
        const [an, ac] = colors[i] as readonly [string, Rgb];
        const [bn, bc] = colors[j] as readonly [string, Rgb];
        const distance =
          vision === 'normal' ? deltaE(ac, bc) : deltaE(simulate(ac, vision), simulate(bc, vision));
        out.push({ vision, a: an, b: bn, distance, ok: distance >= CVD_MIN_DELTA_E });
      }
    }
  }
  return out;
}

export function hex(tokens: ParsedTokens, name: string, theme: Theme): string {
  return rgbToHex(resolveColor(tokens, name, theme));
}

export function oklchText(tokens: ParsedTokens, name: string, theme: Theme): string {
  const { l, c, h } = rgbToOklch(resolveColor(tokens, name, theme));
  return `oklch(${l.toFixed(3)} ${c.toFixed(3)} ${h.toFixed(0)})`;
}
