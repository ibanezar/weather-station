// Install prompt handling: remember the browser's offer so Settings can show an Install button.

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

let deferred: BeforeInstallPromptEvent | undefined;
const listeners = new Set<() => void>();

const notify = (): void => {
  for (const fn of listeners) fn();
};

export function initInstallPrompt(): void {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault(); // keep the offer for our own button
    deferred = event as BeforeInstallPromptEvent;
    notify();
  });
  window.addEventListener('appinstalled', () => {
    deferred = undefined;
    notify();
  });
}

export function canInstall(): boolean {
  return deferred !== undefined;
}

/** Show the browser's install dialog. Resolves to true when the player accepts. */
export async function promptInstall(): Promise<boolean> {
  const offer = deferred;
  if (!offer) return false;
  deferred = undefined; // an offer can be used once
  notify();
  await offer.prompt();
  return (await offer.userChoice).outcome === 'accepted';
}

/** Run `fn` when the install offer appears or goes away. Returns the unsubscribe function. */
export function onInstallChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}
