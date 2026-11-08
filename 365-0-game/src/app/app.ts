// The application shell: settings, language, routing and screen transitions.
import { createI18n, resolveLocale, type I18n } from '../i18n/index.ts';
import { applyVisualSettings, isReducedMotion } from '../ui/settings.ts';
import { createFeedback, type Feedback } from './feedback.ts';
import { sendCount, type CountEvent } from './counts.ts';
import { createFormatter, type Formatter } from './format.ts';
import type { Session } from './session.ts';
import { browserStorage, defaultSettings, emptyStored, Store } from './storage.ts';

export type Route =
  'home' | 'how' | 'draft' | 'reveal' | 'result' | 'settings' | 'about' | 'privacy' | 'stats';

const HASHES: Record<Route, string> = {
  home: '#/',
  how: '#/how',
  draft: '#/draft',
  reveal: '#/reveal',
  result: '#/result',
  settings: '#/settings',
  about: '#/about',
  privacy: '#/privacy',
  stats: '#/stats',
};

export function routeFromHash(hash: string): Route | 'styleguide' {
  if (hash === '#/styleguide') return 'styleguide';
  const found = (Object.keys(HASHES) as Route[]).find((r) => HASHES[r] === hash);
  return found ?? 'home';
}

export type ScreenRenderer = (app: App, root: HTMLElement) => void;

export class App {
  readonly store: Store;
  readonly feedback: Feedback;
  i18n: I18n;
  fmt: Formatter;
  /** The run in progress, or the last finished one. */
  session: Session | undefined;
  route: Route = 'home';
  private rendered = false;
  private screens: Partial<Record<Route, ScreenRenderer>> = {};
  private cleanups: (() => void)[] = [];

  readonly root: HTMLElement;

  constructor(root: HTMLElement, languageTag: string | undefined = navigator.language) {
    this.root = root;
    const locale = resolveLocale(languageTag);
    this.store = new Store(emptyStored(defaultSettings(languageTag, locale)), browserStorage());
    this.i18n = createI18n(this.store.state.settings.language);
    this.fmt = createFormatter(this.i18n.locale, this.store.state.settings.unit);
    this.feedback = createFeedback(() => this.store.state.settings);
  }

  /** Tell the server, anonymously, that a game started or finished (see counts.ts). Off in Settings. */
  count(event: CountEvent): void {
    sendCount(this.store.state.settings.counts, event);
  }

  register(route: Route, render: ScreenRenderer): void {
    this.screens[route] = render;
  }

  /** Screens call this to run code when they are replaced (timers, animation frames). */
  onLeave(fn: () => void): void {
    this.cleanups.push(fn);
  }

  /** Apply language, unit and visual settings to the document. */
  applySettings(): void {
    const s = this.store.state.settings;
    this.i18n = createI18n(s.language);
    this.fmt = createFormatter(this.i18n.locale, s.unit);
    document.documentElement.lang = s.language;
    applyVisualSettings({ theme: s.theme, pattern: s.pattern, motion: s.motion });
  }

  go(route: Route): void {
    const hash = HASHES[route];
    if (location.hash === hash || (route === 'home' && location.hash === '')) this.render();
    else location.hash = hash;
  }

  /** Run a DOM update inside a View Transition when the browser supports it. */
  transition(update: () => void): void {
    if (typeof document.startViewTransition === 'function' && !isReducedMotion()) {
      document.startViewTransition(update);
    } else {
      update();
    }
  }

  render(): void {
    const target = routeFromHash(location.hash);
    if (target === 'styleguide') return;
    this.route = target;
    const draw = (): void => {
      for (const fn of this.cleanups) fn();
      this.cleanups = [];
      this.root.replaceChildren();
      this.screens[target]?.(this, this.root);
      window.scrollTo(0, 0);
      const heading = this.root.querySelector('h1');
      heading?.setAttribute('tabindex', '-1');
    };
    // The first screen appears at once; later ones use a View Transition when available.
    if (this.rendered) this.transition(draw);
    else draw();
    this.rendered = true;
  }
}
