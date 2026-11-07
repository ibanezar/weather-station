import { h } from '../dom.ts';

export const STEP_COUNT = 5;

/**
 * A five-step bar for a bucketed value (0 to 4 fills 1 to 5 steps). Its text alternative is the value
 * ("3 of 5"); the visible label ("Perfect days") sits beside it, so the two read together.
 */
export function steps(bucket: number, valueText: string, tone: 'perfect' | 'bad'): HTMLElement {
  const filled = Math.min(STEP_COUNT, Math.max(0, Math.round(bucket) + 1));
  return h(
    'span',
    { class: `steps steps--${tone}`, role: 'img', 'aria-label': valueText },
    ...Array.from({ length: STEP_COUNT }, (_, i) =>
      h('span', { class: `steps__step${i < filled ? ' steps__step--on' : ''}` }),
    ),
  );
}
