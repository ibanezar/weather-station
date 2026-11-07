import './styles/fonts.css';
import './styles/index.css';
import { App, routeFromHash } from './app/app.ts';
import { renderAbout, renderPrivacy } from './ui/screens/about.ts';
import { renderDraft } from './ui/screens/draft.ts';
import { renderHome } from './ui/screens/home.ts';
import { renderHow } from './ui/screens/how.ts';
import { renderResult } from './ui/screens/result.ts';
import { renderReveal } from './ui/screens/reveal.ts';
import { renderSettings } from './ui/screens/settings.ts';

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

  /** #/styleguide is the design-system page; everything else is the game. */
  const dispatch = (): void => {
    if (routeFromHash(location.hash) === 'styleguide') void showStyleguide(root);
    else app.render();
  };
  app.applySettings();
  window.addEventListener('hashchange', dispatch);
  dispatch();
}
