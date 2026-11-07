import { h } from '../dom.ts';

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

/** A group of mutually exclusive choices; every option is a real button with aria-pressed. */
export function segmented<T extends string>(
  label: string,
  options: readonly SegmentedOption<T>[],
  current: T,
  onChange: (value: T) => void,
): HTMLElement {
  const buttons = options.map((o) =>
    h(
      'button',
      { type: 'button', class: 'seg__btn', 'aria-pressed': String(o.value === current) },
      o.label,
    ),
  );
  buttons.forEach((b, i) => {
    b.addEventListener('click', () => {
      for (const other of buttons) other.setAttribute('aria-pressed', String(other === b));
      const option = options[i];
      if (option) onChange(option.value);
    });
  });
  return h('div', { class: 'seg', role: 'group', 'aria-label': label }, ...buttons);
}
