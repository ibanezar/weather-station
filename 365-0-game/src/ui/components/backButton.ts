import { button } from './button.ts';

/** A quiet "Back" button at the top of a secondary screen. */
export function backButton(label: string, onClick: () => void): HTMLButtonElement {
  return button({ label, variant: 'quiet', icon: 'back', onClick });
}
