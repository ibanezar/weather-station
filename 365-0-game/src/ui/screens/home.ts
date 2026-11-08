import { activeStreak, localDate } from '../../app/dates.ts';
import type { App } from '../../app/app.ts';
import { loadEngineData, prefetchWorld } from '../../app/data.ts';
import { installMode, onInstallChange, promptInstall } from '../../app/install.ts';
import { newSession, randomEntropy, restoreSession } from '../../app/session.ts';
import { dailySeed } from '../../engine/run.ts';
import { button } from '../components/button.ts';
import { chip } from '../components/chip.ts';
import type { MessageKey } from '../../i18n/index.ts';
import { h, mount } from '../dom.ts';
import { THRESHOLDS } from '../../engine/thresholds.ts';
import { cities } from '../../app/data.ts';
import { logoMark } from '../components/logo.ts';

/** Start (or reopen) a run. Shows the load error with a retry when the weather data cannot load. */
export async function startRun(
  app: App,
  mode: 'daily' | 'endless',
  ui: { btn: HTMLButtonElement; message: HTMLElement },
): Promise<void> {
  const { t } = app.i18n;
  const today = localDate();
  ui.btn.disabled = true;
  ui.message.textContent = '';
  app.store.update((st) => {
    st.onboarded = true;
  });
  try {
    const data = await loadEngineData();
    if (mode === 'daily') {
      const done = app.store.state.daily[today];
      if (done) {
        app.session = restoreSession(
          'daily',
          data,
          dailySeed(today),
          today,
          done.picks,
          done.rerolls ?? [],
        );
        app.go('result');
        return;
      }
    }
    app.session = newSession(mode, data, { date: today, entropy: randomEntropy() });
    app.go('draft');
  } catch {
    ui.message.textContent = `${t('error.world')} `;
    ui.message.append(
      button({
        label: t('error.retry'),
        variant: 'secondary',
        onClick: () => void startRun(app, mode, ui),
      }),
    );
    ui.btn.disabled = false;
  }
}

export function renderHome(app: App, root: HTMLElement): void {
  const { t, plural } = app.i18n;
  const today = localDate();
  const dailyDone = app.store.state.daily[today] !== undefined;
  const streak = activeStreak(app.store.state.streak, today);
  const best = app.store.state.bestEndless;
  const message = h('p', { class: 'screen__error', role: 'alert' });

  const dailyBtn = button({
    label: dailyDone ? t('home.seeResult') : t('home.playDaily'),
    variant: 'primary',
    full: true,
    onClick: () => void startRun(app, 'daily', { btn: dailyBtn, message }),
  });
  const endlessBtn = button({
    label: t('home.playEndless'),
    variant: 'secondary',
    full: true,
    onClick: () => void startRun(app, 'endless', { btn: endlessBtn, message }),
  });

  // Install: the browser's own dialog where it offers one, the Share-menu steps on iPhone, nothing otherwise.
  const installSlot = h('div', { class: 'home__install' });
  const drawInstall = (): void => {
    const mode = installMode();
    if (mode === 'none') {
      installSlot.replaceChildren();
      return;
    }
    const hint = h('p', { class: 'muted home__install-hint', role: 'status' });
    const installBtn = button({
      label: t('home.install'),
      variant: 'secondary',
      icon: 'install',
      full: true,
      onClick: () => {
        if (mode === 'prompt') void promptInstall();
        else hint.textContent = t('home.installIos');
      },
    });
    installSlot.replaceChildren(installBtn, hint);
  };
  drawInstall();

  const range = app.fmt.range(THRESHOLDS.perfect.tmaxCMin, THRESHOLDS.perfect.tmaxCMax);
  const steps = [1, 2, 3].map((n) =>
    h(
      'li',
      { class: 'home__step' },
      h('span', { class: 'home__num num', 'aria-hidden': 'true' }, String(n)),
      h(
        'div',
        null,
        h('strong', { class: 'home__step-title' }, t(`home.step${String(n)}.title` as MessageKey)),
        h(
          'p',
          { class: 'muted home__step-text' },
          t(`home.step${String(n)}.text` as MessageKey, { range }),
        ),
      ),
    ),
  );

  mount(
    root,
    h(
      'main',
      { class: 'screen screen--home' },
      h(
        'header',
        { class: 'home__head' },
        h(
          'div',
          { class: 'home__brand' },
          logoMark(64),
          h('h1', { class: 'home__title' }, t('app.title')),
        ),
        h('p', { class: 'home__tagline' }, t('app.tagline')),
        h('p', { class: 'home__pitch' }, t('home.pitch')),
      ),
      h('ol', { class: 'home__steps', 'aria-label': t('onboarding.title') }, ...steps),
      h(
        'div',
        { class: 'screen__actions' },
        message,
        dailyBtn,
        h(
          'p',
          { class: 'muted home__daily num' },
          t('home.dailyCaption'),
          streak >= 2 ? ` · ${plural('home.streak', streak)}` : null,
        ),
        endlessBtn,
        installSlot,
        best
          ? h(
              'p',
              { class: 'muted num home__best' },
              t('home.bestEndless', { record: app.fmt.record(best) }),
            )
          : null,
      ),
      h(
        'section',
        { class: 'home__legend', 'aria-label': t('home.dayTypes') },
        h('h2', { class: 'home__legend-title' }, t('home.dayTypes')),
        h(
          'div',
          { class: 'home__chips' },
          chip({ label: t('home.dayPerfect'), swatch: 'p' }),
          chip({ label: t('home.dayOk'), swatch: 'o' }),
          chip({ label: t('home.dayBad'), swatch: 'loss' }),
        ),
        h('p', { class: 'muted home__facts' }, t('home.facts', { cities: cities.length })),
      ),
      h(
        'nav',
        { class: 'home__links', 'aria-label': t('home.settings') },
        button({
          label: t('home.settings'),
          variant: 'quiet',
          icon: 'settings',
          onClick: () => {
            app.go('settings');
          },
        }),
        button({
          label: t('home.howItWorks'),
          variant: 'quiet',
          icon: 'info',
          onClick: () => {
            app.go('how');
          },
        }),
      ),
    ),
  );
  app.onLeave(onInstallChange(drawInstall));
  prefetchWorld();
}
