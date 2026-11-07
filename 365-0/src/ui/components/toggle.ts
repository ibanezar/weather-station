import { h } from '../dom.ts';

/** An on/off switch: a real button with role="switch", labelled by the visible text beside it. */
export function toggle(
  label: string,
  on: boolean,
  onLabel: string,
  offLabel: string,
  onChange: (value: boolean) => void,
): HTMLElement {
  let value = on;
  const state = h('span', { class: 'switch__state muted' }, value ? onLabel : offLabel);
  const track = h(
    'span',
    { class: 'switch__track', 'aria-hidden': 'true' },
    h('span', { class: 'switch__thumb' }),
  );
  const btn = h(
    'button',
    { type: 'button', class: 'switch', role: 'switch', 'aria-checked': String(value) },
    h('span', { class: 'switch__label' }, label),
    state,
    track,
  );
  btn.addEventListener('click', () => {
    value = !value;
    btn.setAttribute('aria-checked', String(value));
    state.textContent = value ? onLabel : offLabel;
    onChange(value);
  });
  return btn;
}
