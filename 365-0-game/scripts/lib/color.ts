// Colour maths for the design tokens: hex and OKLCH conversion, WCAG contrast, colour-blindness
// simulation and a perceptual distance. Used by scripts/contrast.ts and its tests.

export type Rgb = [number, number, number]; // sRGB, each 0 to 1
export interface Oklch {
  l: number;
  c: number;
  h: number;
}

export function hexToRgb(hex: string): Rgb {
  const m = /^#([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m?.[1]) throw new Error(`bad hex colour ${hex}`);
  const n = parseInt(m[1], 16);
  return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

export function rgbToHex(rgb: Rgb): string {
  const to = (v: number): string =>
    Math.round(Math.min(1, Math.max(0, v)) * 255)
      .toString(16)
      .padStart(2, '0');
  return `#${to(rgb[0])}${to(rgb[1])}${to(rgb[2])}`.toUpperCase();
}

const toLinear = (v: number): number => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
const toGamma = (v: number): number =>
  v <= 0.0031308 ? 12.92 * v : 1.055 * Math.max(0, v) ** (1 / 2.4) - 0.055;

export function rgbToLinear(rgb: Rgb): Rgb {
  return [toLinear(rgb[0]), toLinear(rgb[1]), toLinear(rgb[2])];
}
export function linearToRgb(lin: Rgb): Rgb {
  return [toGamma(lin[0]), toGamma(lin[1]), toGamma(lin[2])];
}

export type Oklab = [number, number, number];

export function linearToOklab([r, g, b]: Rgb): Oklab {
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

export function oklabToLinear([L, a, b]: Oklab): Rgb {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
}

export function rgbToOklch(rgb: Rgb): Oklch {
  const [L, a, b] = linearToOklab(rgbToLinear(rgb));
  const c = Math.hypot(a, b);
  const h = c < 1e-4 ? 0 : ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360;
  return { l: L, c, h };
}

export function oklchToRgb({ l, c, h }: Oklch): Rgb {
  const rad = (h * Math.PI) / 180;
  const lin = oklabToLinear([l, c * Math.cos(rad), c * Math.sin(rad)]);
  return linearToRgb(lin);
}

/** True when the colour fits inside the sRGB gamut (so the hex is exact). */
export function inGamut(o: Oklch): boolean {
  const rad = (o.h * Math.PI) / 180;
  const lin = oklabToLinear([o.l, o.c * Math.cos(rad), o.c * Math.sin(rad)]);
  return lin.every((v) => v >= -0.0005 && v <= 1.0005);
}

export const hexToOklch = (hex: string): Oklch => rgbToOklch(hexToRgb(hex));

/** CSS text for an OKLCH colour, e.g. oklch(0.84 0.17 80). */
export function oklchCss({ l, c, h }: Oklch): string {
  return `oklch(${l.toFixed(3)} ${c.toFixed(3)} ${h.toFixed(1)})`;
}

/** Parses oklch(L C H) with L as a number or a percentage. */
export function parseOklch(text: string): Oklch {
  const m = /oklch\(\s*([\d.]+)(%?)\s+([\d.]+)\s+([\d.]+)\s*\)/i.exec(text);
  if (!m?.[1] || !m[3] || !m[4]) throw new Error(`cannot parse ${text}`);
  return { l: Number(m[1]) / (m[2] === '%' ? 100 : 1), c: Number(m[3]), h: Number(m[4]) };
}

/** WCAG relative luminance. */
export function luminance(rgb: Rgb): number {
  const [r, g, b] = rgbToLinear(rgb);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio between two colours, 1 to 21. */
export function contrast(a: Rgb, b: Rgb): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

export type Cvd = 'protanopia' | 'deuteranopia' | 'tritanopia';

// Machado, Oliveira and Fernandes (2009), severity 1.0, applied to linear RGB.
const CVD_MATRIX: Record<Cvd, [Rgb, Rgb, Rgb]> = {
  protanopia: [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
  ],
  deuteranopia: [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.01182, 0.04294, 0.968881],
  ],
  tritanopia: [
    [1.255528, -0.076749, -0.178779],
    [-0.078411, 0.930809, 0.147602],
    [0.004733, 0.691367, 0.3039],
  ],
};

/** How a colour looks to a person with the given colour vision deficiency. */
export function simulate(rgb: Rgb, kind: Cvd): Rgb {
  const lin = rgbToLinear(rgb);
  const m = CVD_MATRIX[kind];
  const out = m.map((row) => row[0] * lin[0] + row[1] * lin[1] + row[2] * lin[2]) as Rgb;
  return linearToRgb(out.map((v) => Math.min(1, Math.max(0, v))) as Rgb);
}

/** Perceptual distance: Euclidean distance in OKLab (about 0.02 is barely visible, 0.1 is clear). */
export function deltaE(a: Rgb, b: Rgb): number {
  const [l1, a1, b1] = linearToOklab(rgbToLinear(a));
  const [l2, a2, b2] = linearToOklab(rgbToLinear(b));
  return Math.hypot(l1 - l2, a1 - a2, b1 - b2);
}
