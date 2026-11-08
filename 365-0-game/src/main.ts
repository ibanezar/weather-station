import './styles/fonts.css';
import './styles/index.css';
import { App, routeFromHash } from './app/app.ts';
import { initInstallPrompt } from './app/install.ts';
import { renderAbout, renderPrivacy } from './ui/screens/about.ts';
import { renderDraft } from './ui/screens/draft.ts';
import { renderHome } from './ui/screens/home.ts';
import { renderHow } from './ui/screens/how.ts';
import { renderResult } from './ui/screens/result.ts';
import { renderReveal } from './ui/screens/reveal.ts';
import { renderSettings } from './ui/screens/settings.ts';
import { renderStats } from './ui/screens/stats.ts';

const root = document.querySelector<HTMLDivElement>('#app');

async function showStyleguide(el: HTMLElement): Promise<void> {
  const { renderStyleguide } = await import('./ui/screens/styleguide.ts');
  renderStyleguide(el);
}

if (root) {
  const app = new App(root);
  app.register('home', renderHome);
  app.register('how', (a, r) => {
    renderHow(a, r);
  });
  app.register('draft', renderDraft);
  app.register('reveal', renderReveal);
  app.register('result', renderResult);
  app.register('settings', renderSettings);
  app.register('about', renderAbout);
  app.register('privacy', renderPrivacy);
  app.register('stats', renderStats);

  /** #/styleguide is the design-system page; everything else is the game. */
  const dispatch = (): void => {
    if (routeFromHash(location.hash) === 'styleguide') void showStyleguide(root);
    else app.render();
  };
  app.applySettings();
  window.addEventListener('hashchange', dispatch);
  dispatch();
}

// Offline support: register the service worker that the build emits (not in development, where it
// would serve stale files).
initInstallPrompt();
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  // A new deploy installs a new service worker in the background and takes the page over, but the page
  // that is open keeps running the old code. When that happens, reload to the new version: at once on
  // Home, otherwise the next time the player is back on Home (never in the middle of a game).
  const hadController = navigator.serviceWorker.controller !== null;
  let updated = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (hadController) updated = true;
    if (updated && routeFromHash(location.hash) === 'home') location.reload();
  });
  window.addEventListener('hashchange', () => {
    if (updated && routeFromHash(location.hash) === 'home') location.reload();
  });
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./sw.js').catch(() => {
      // Offline support is an extra: the game still works online without it.
    });
  });
}
