import { h } from '../dom.ts';
import { icon } from '../icons/index.ts';

export interface ToastOptions {
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  /** How long it stays. The undo toast uses 2000. */
  durationMs?: number;
}

let region: HTMLElement | undefined;

function getRegion(): HTMLElement {
  if (region?.isConnected) return region;
  region = h('div', { class: 'toast-region', role: 'status', 'aria-live': 'polite' });
  document.body.append(region);
  return region;
}

/** Show a toast; returns a function that dismisses it early. */
export function showToast(o: ToastOptions): () => void {
  const host = getRegion();
  host.replaceChildren(); // one toast at a time
  const dismiss = (): void => {
    clearTimeout(timer);
    toast.remove();
  };
  const toast = h(
    'div',
    { class: 'toast' },
    h('span', { class: 'toast__message' }, o.message),
    o.actionLabel
      ? h(
          'button',
          {
            type: 'button',
            class: 'toast__action',
            onClick: () => {
              dismiss();
              o.onAction?.();
            },
          },
          icon('undo', { size: 20 }),
          h('span', null, o.actionLabel),
        )
      : null,
  );
  host.append(toast);
  const timer = setTimeout(dismiss, o.durationMs ?? 2000);
  return dismiss;
}
