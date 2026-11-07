import { h } from '../dom.ts';
import { button } from './button.ts';

export interface ConfirmOptions {
  title: string;
  body: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
}

/** A modal confirmation using the native <dialog>: focus is trapped and Escape cancels. */
export function confirmDialog(o: ConfirmOptions): void {
  const close = (): void => {
    dialog.close();
    dialog.remove();
  };
  const dialog = h(
    'dialog',
    { class: 'dialog', 'aria-labelledby': 'dialog-title' },
    h('h2', { id: 'dialog-title' }, o.title),
    h('p', null, o.body),
    h(
      'div',
      { class: 'dialog__actions' },
      button({ label: o.cancelLabel, variant: 'secondary', onClick: close }),
      button({
        label: o.confirmLabel,
        variant: 'primary',
        onClick: () => {
          close();
          o.onConfirm();
        },
      }),
    ),
  );
  dialog.addEventListener('cancel', () => {
    dialog.remove();
  });
  document.body.append(dialog);
  dialog.showModal();
}
