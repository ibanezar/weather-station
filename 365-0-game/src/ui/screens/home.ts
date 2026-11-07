import { activeStreak, localDate } from '../../app/dates.ts';
import type { App } from '../../app/app.ts';
import { loadEngineData, prefetchWorld } from '../../app/data.ts';
import { newSession, randomEntropy, restoreSession } from '../../app/session.ts';
import { dailySeed } from '../../engine/run.ts';
import { button } from '../components/button.ts';
import { chip } from '../components/chip.ts';
import { h, mount } from '../dom.ts';
import { renderHow } from './how.ts';

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
  if (!app.store.state.onboarded) {
    renderHow(app, root, { first: true });
    return;
  }
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

  mount(
    root,
    h(
      'main',
      { class: 'screen screen--home' },
      h(
        'header',
        { class: 'home__head' },
        h('h1', { class: 'home__title' }, t('app.title')),
        h('p', { class: 'muted num' }, t('home.seedDate', { date: app.fmt.date(today) })),
        streak >= 2
          ? chip({ label: plural('home.streak', streak), icon: 'streak' })
          : h('p', { class: 'muted' }, t('home.streakEmpty')),
        h('p', { class: 'home__goal' }, t('app.goal')),
      ),
      h(
        'div',
        { class: 'screen__actions' },
        message,
        dailyBtn,
        endlessBtn,
        best
          ? h(
              'p',
              { class: 'muted num home__best' },
              t('home.bestEndless', { record: app.fmt.record(best) }),
            )
          : null,
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
    ),
  );
  prefetchWorld();
}
