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

/** True when the game already runs as an installed app. */
export function isStandalone(): boolean {
  const nav = navigator as Navigator & { standalone?: boolean };
  return window.matchMedia('(display-mode: standalone)').matches || nav.standalone === true;
}

/** iPhone and iPad Safari never offer an install prompt; the player has to use the Share menu. */
function isIosSafari(): boolean {
  const ua = navigator.userAgent;
  const ios =
    /iPad|iPhone|iPod/.test(ua) || (ua.includes('Macintosh') && navigator.maxTouchPoints > 1);
  return ios && /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
}

/**
 * What the Install button should do: 'prompt' opens the browser's dialog, 'ios' shows how to add the game
 * from the Share menu, 'none' hides the button (already installed, or the browser cannot install).
 */
export function installMode(): 'prompt' | 'ios' | 'none' {
  if (isStandalone()) return 'none';
  if (canInstall()) return 'prompt';
  return isIosSafari() ? 'ios' : 'none';
}
