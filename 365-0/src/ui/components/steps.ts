import { h } from '../dom.ts';

export const STEP_COUNT = 5;

/**
 * A five-step bar for a bucketed value (0 to 4 fills 1 to 5 steps). The text alternative carries the
 * label and the value, so the bar never relies on colour or length alone.
 */
export function steps(
  bucket: number,
  label: string,
  valueText: string,
  tone: 'perfect' | 'bad',
): HTMLElement {
  const filled = Math.min(STEP_COUNT, Math.max(0, Math.round(bucket) + 1));
  return h(
    'div',
    { class: `steps steps--${tone}`, role: 'img', 'aria-label': `${label}: ${valueText}` },
    ...Array.from({ length: STEP_COUNT }, (_, i) =>
      h('span', { class: `steps__step${i < filled ? ' steps__step--on' : ''}` }),
    ),
  );
}
