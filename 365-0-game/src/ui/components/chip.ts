import type { DayType } from '../../engine/thresholds.ts';
import { h } from '../dom.ts';
import { icon, type IconName } from '../icons/index.ts';

export interface ChipOptions {
  label: string;
  icon?: IconName;
  /** A small day-type swatch before the label (used by the win/draw/loss legend). */
  swatch?: DayType | 'loss' | readonly DayType[];
  /** Visual weight: neutral by default, 'event' for the round event chip. */
  tone?: 'neutral' | 'event';
}

export function swatch(kind: DayType | 'loss' | readonly DayType[]): HTMLElement {
  if (typeof kind !== 'string') {
    // Several day types together: a win, draw or loss that is made of more than one type.
    if (kind.length === 1)
      return h('span', { class: `swatch day-${kind[0] as string}`, 'aria-hidden': 'true' });
    return h(
      'span',
      { class: `swatch swatch--multi swatch--n${String(kind.length)}`, 'aria-hidden': 'true' },
      ...kind.map((t) => h('span', { class: `swatch__part day-${t}` })),
    );
  }
  if (kind === 'loss') {
    // Rain, storm, heat and freeze together: a loss is any of them.
    return h(
      'span',
      { class: 'swatch swatch--loss', 'aria-hidden': 'true' },
      ...(['r', 's', 'h', 'f'] as const).map((t) => h('span', { class: `swatch__part day-${t}` })),
    );
  }
  return h('span', { class: `swatch day-${kind}`, 'aria-hidden': 'true' });
}

export function chip(o: ChipOptions): HTMLElement {
  return h(
    'span',
    { class: `chip chip--${o.tone ?? 'neutral'}` },
    o.swatch ? swatch(o.swatch) : null,
    o.icon ? icon(o.icon, { size: 18 }) : null,
    h('span', null, o.label),
  );
}
