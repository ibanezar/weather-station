import { h } from '../dom.ts';
import { icon } from '../icons/index.ts';

export interface ProgressOptions {
  total: number;
  /** "Round 3 of 12" for the text alternative and the visible counter. */
  roundText: (current: number, total: number) => string;
  /** "3 scouts left". */
  scoutsText: (left: number) => string;
}

export interface Progress {
  el: HTMLElement;
  update: (current: number, scoutsLeft: number) => void;
}

/** Twelve steps, left aligned, with the scouts remaining on the right (SPEC 6.5). */
export function progress(o: ProgressOptions): Progress {
  const segs = Array.from({ length: o.total }, () => h('li', { class: 'progress__step' }));
  const list = h('ol', { class: 'progress__steps', 'aria-hidden': 'true' }, ...segs);
  const count = h('span', { class: 'progress__count num' });
  const scouts = h('span', { class: 'progress__scouts num' });
  const el = h(
    'div',
    { class: 'progress', role: 'group' },
    h('div', { class: 'progress__main' }, count, list),
    scouts,
  );

  return {
    el,
    update(current, scoutsLeft) {
      const text = o.roundText(current, o.total);
      el.setAttribute('aria-label', text);
      count.textContent = text;
      segs.forEach((seg, i) => {
        seg.dataset['state'] = i + 1 < current ? 'done' : i + 1 === current ? 'current' : 'todo';
        if (i + 1 === current) seg.setAttribute('aria-current', 'step');
        else seg.removeAttribute('aria-current');
      });
      scouts.replaceChildren(
        icon('scout', { size: 20 }),
        h('span', null, o.scoutsText(scoutsLeft)),
      );
    },
  };
}
