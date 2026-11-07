import './styles/fonts.css';
import './styles/index.css';
import { resolveLocale, translate } from './i18n/index.ts';

const locale = resolveLocale(navigator.language);
document.documentElement.lang = locale;

const app = document.querySelector<HTMLDivElement>('#app');

/** Tiny hash router: #/styleguide shows the design system, everything else the app. */
async function route(): Promise<void> {
  if (!app) return;
  if (location.hash === '#/styleguide') {
    const { renderStyleguide } = await import('./ui/screens/styleguide.ts');
    renderStyleguide(app);
    return;
  }
  const title = document.createElement('h1');
  title.textContent = translate(locale, 'app.title');
  const tagline = document.createElement('p');
  tagline.textContent = translate(locale, 'app.tagline');
  app.replaceChildren(title, tagline);
}

window.addEventListener('hashchange', () => void route());
void route();
