import { h } from '../dom.ts';
import { icon, type IconName } from '../icons/index.ts';

export interface ButtonOptions {
  label: string;
  variant?: 'primary' | 'secondary' | 'quiet';
  icon?: IconName;
  full?: boolean;
  disabled?: boolean;
  onClick?: (event: Event) => void;
}

/** A real <button> with a visible text label; the icon is decorative. */
export function button(o: ButtonOptions): HTMLButtonElement {
  const variant = o.variant ?? 'secondary';
  return h(
    'button',
    {
      type: 'button',
      class: `btn btn--${variant}${o.full ? ' btn--full' : ''}`,
      disabled: o.disabled,
      onClick: o.onClick,
    },
    o.icon ? icon(o.icon) : null,
    h('span', null, o.label),
  );
}
