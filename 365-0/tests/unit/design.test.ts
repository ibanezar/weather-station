import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  contrast,
  deltaE,
  hexToOklch,
  hexToRgb,
  inGamut,
  oklchToRgb,
  parseOklch,
  rgbToHex,
  simulate,
} from '../../scripts/lib/color.ts';
import {
  CVD_MIN_DELTA_E,
  DAY_TOKENS,
  checkCvd,
  checkPairs,
  parseTokens,
  resolveColor,
} from '../../scripts/lib/tokens.ts';
import { ARCHETYPES } from '../../src/data/types.ts';
import { DAY_TYPE_CHARS } from '../../src/engine/thresholds.ts';
import { ARCHETYPE_ICONS, DAY_ICONS, ICONS } from '../../src/ui/icons/index.ts';

const tokensCss = readFileSync(join(import.meta.dirname, '../../src/styles/tokens.css'), 'utf8');

describe('colour maths', () => {
  it('round-trips hex through OKLCH', () => {
    for (const hex of ['#FFB703', '#2F6FDE', '#14202E', '#EDF1F4', '#FFFFFF', '#000000']) {
      expect(rgbToHex(oklchToRgb(hexToOklch(hex)))).toBe(hex);
    }
  });

  it('gives black on white the maximum contrast and a colour on itself the minimum', () => {
    expect(contrast(hexToRgb('#000000'), hexToRgb('#FFFFFF'))).toBeCloseTo(21, 5);
    expect(contrast(hexToRgb('#FFB703'), hexToRgb('#FFB703'))).toBeCloseTo(1, 5);
  });

  it('keeps greys grey under every colour-blindness simulation', () => {
    const grey = hexToRgb('#808080');
    for (const kind of ['protanopia', 'deuteranopia', 'tritanopia'] as const) {
      expect(deltaE(grey, simulate(grey, kind))).toBeLessThan(0.02);
    }
  });

  it('makes red and green much closer for protanopia than for normal vision', () => {
    const red = hexToRgb('#FF0000');
    const green = hexToRgb('#00A000');
    expect(deltaE(simulate(red, 'protanopia'), simulate(green, 'protanopia'))).toBeLessThan(
      deltaE(red, green) / 2,
    );
  });

  it('parses OKLCH text and detects out-of-gamut colours', () => {
    expect(parseOklch('oklch(0.5 0.1 200)')).toEqual({ l: 0.5, c: 0.1, h: 200 });
    expect(parseOklch('oklch(50% 0.1 200)').l).toBe(0.5);
    expect(inGamut({ l: 0.5, c: 0.05, h: 200 })).toBe(true);
    expect(inGamut({ l: 0.9, c: 0.35, h: 200 })).toBe(false);
  });
});

describe('design tokens', () => {
  const tokens = parseTokens(tokensCss);

  it('meet every text and graphic contrast limit in both themes', () => {
    const failing = checkPairs(tokens).filter((p) => !p.ok);
    expect(failing.map((p) => `${p.theme} ${p.fg} on ${p.bg}: ${p.ratio.toFixed(2)}`)).toEqual([]);
  });

  it('keep all six day types apart under colour-blindness simulation', () => {
    const results = checkCvd(tokens);
    expect(results).toHaveLength(4 * 15);
    const close = results.filter((r) => !r.ok);
    expect(close.map((r) => `${r.vision} ${r.a} ${r.b}: ${r.distance.toFixed(3)}`)).toEqual([]);
  });

  it('resolve light-dark() per theme and var() references', () => {
    expect(rgbToHex(resolveColor(tokens, '--surface', 'light'))).toBe('#EDF1F4');
    expect(rgbToHex(resolveColor(tokens, '--surface', 'dark'))).toBe('#0E1624');
    expect(rgbToHex(resolveColor(tokens, '--accent', 'dark'))).toBe(
      rgbToHex(resolveColor(tokens, '--day-perfect', 'dark')),
    );
  });

  it('would fail the check if the text colour were too close to the surface', () => {
    const bad = tokensCss.replace(
      /--ink-muted: light-dark\([^;]+\);/,
      '--ink-muted: light-dark(oklch(0.9 0.006 240), oklch(0.25 0.03 261));',
    );
    expect(checkPairs(parseTokens(bad)).some((p) => !p.ok)).toBe(true);
  });

  it('would fail the check if two day types became the same colour', () => {
    const bad = tokensCss.replace(/--day-storm: [^;]+;/, '--day-storm: oklch(0.56 0.18 261);');
    const results = checkCvd(parseTokens(bad));
    expect(results.some((r) => !r.ok && r.distance < CVD_MIN_DELTA_E)).toBe(true);
  });

  it('declare every day-type token used by the grid', () => {
    for (const name of DAY_TOKENS) expect(tokens.raw.has(name)).toBe(true);
  });
});

describe('icon set', () => {
  it('has an icon for every day type and every archetype, plus the interface icons', () => {
    expect(DAY_ICONS).toHaveLength(DAY_TYPE_CHARS.length);
    for (const name of DAY_ICONS) expect(ICONS[name].length).toBeGreaterThan(0);
    for (const archetype of ARCHETYPES) expect(ARCHETYPE_ICONS).toContain(archetype);
    for (const name of ['scout', 'undo', 'share', 'settings', 'check', 'streak'] as const) {
      expect(ICONS[name].length).toBeGreaterThan(0);
    }
  });

  it('only uses shapes that fit the 24 px grid', () => {
    for (const shapes of Object.values(ICONS)) {
      for (const [tag, attrs] of shapes) {
        if (tag === 'circle') {
          const { cx, cy, r } = attrs as { cx: number; cy: number; r: number };
          expect(cx - r).toBeGreaterThanOrEqual(0);
          expect(cx + r).toBeLessThanOrEqual(24);
          expect(cy - r).toBeGreaterThanOrEqual(0);
          expect(cy + r).toBeLessThanOrEqual(24);
        }
      }
    }
  });
});
