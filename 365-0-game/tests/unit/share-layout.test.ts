import { describe, expect, it } from 'vitest';
import { GRID_ROWS } from '../../src/ui/canvas/grid.ts';
import { SHARE_SIZES, shareLayout, type ShareFormat } from '../../src/ui/canvas/shareImage.ts';

describe.each(['feed', 'story'] as ShareFormat[])('share image layout (%s)', (format) => {
  const L = shareLayout(format);

  it('has the sizes of SPEC 6.8', () => {
    expect(SHARE_SIZES.feed).toEqual({ width: 1080, height: 1350 });
    expect(SHARE_SIZES.story).toEqual({ width: 1080, height: 1920 });
    expect({ width: L.width, height: L.height }).toEqual(SHARE_SIZES[format]);
  });

  it('keeps the grid inside the margins and above the address', () => {
    expect(L.grid.x).toBe(L.margin);
    expect(L.grid.x + L.grid.width).toBe(L.width - L.margin);
    expect(L.grid.y + L.grid.height).toBeLessThan(L.urlY - 20);
    expect(L.grid.height).toBe(GRID_ROWS * L.grid.tileH + (GRID_ROWS - 1) * L.grid.gap);
    expect(L.grid.tileH).toBeGreaterThanOrEqual(14);
  });

  it('stacks title, record, grade, best line, labels, grid and address from top to bottom', () => {
    const order = [L.titleY, L.recordY, L.gradeY, L.bestY, L.labelsY, L.grid.y, L.urlY];
    for (let i = 1; i < order.length; i++) {
      expect(order[i] as number, `step ${String(i)}`).toBeGreaterThan(order[i - 1] as number);
    }
    // Room for the big record under the title: a record glyph is about 0.8 em tall.
    expect(L.recordY - 0.8 * L.recordSize).toBeGreaterThan(L.titleY + 20);
    // And the grade title (104 px) under the record.
    expect(L.gradeY - 0.8 * 104).toBeGreaterThan(L.recordY + 10);
  });

  it('fits everything inside the canvas', () => {
    for (const y of [L.titleY, L.recordY, L.gradeY, L.bestY, L.labelsY, L.urlY]) {
      expect(y).toBeGreaterThan(0);
      expect(y).toBeLessThan(L.height);
    }
  });
});
