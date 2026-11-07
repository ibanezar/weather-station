import './styles/fonts.css';
import './styles/tokens.css';
import './styles/base.css';
import { resolveLocale, translate } from './i18n/index.ts';

const locale = resolveLocale(navigator.language);
document.documentElement.lang = locale;

const app = document.querySelector<HTMLDivElement>('#app');
if (app) {
  const title = document.createElement('h1');
  title.textContent = translate(locale, 'app.title');
  const tagline = document.createElement('p');
  tagline.textContent = translate(locale, 'app.tagline');
  app.replaceChildren(title, tagline);
}
