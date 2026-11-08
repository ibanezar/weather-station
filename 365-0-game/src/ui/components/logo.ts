import { BRAND, MARK_RADIUS, markTiles } from '../../brand/mark.ts';
import { svg } from '../dom.ts';

/** The 365-0 mark. Decorative: the name next to it is real text. */
export function logoMark(size = 64): SVGSVGElement {
  const el = svg('svg', {
    viewBox: '0 0 100 100',
    width: size,
    height: size,
    class: 'logo-mark',
    'aria-hidden': 'true',
    focusable: 'false',
  });
  el.append(svg('rect', { width: 100, height: 100, rx: MARK_RADIUS, fill: BRAND.background }));
  for (const t of markTiles()) {
    el.append(svg('rect', { x: t.x, y: t.y, width: t.w, height: t.h, rx: 2.2, fill: t.fill }));
  }
  return el;
}
