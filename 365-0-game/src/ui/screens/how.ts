import type { App } from '../../app/app.ts';
import { button } from '../components/button.ts';
import { backButton } from '../components/backButton.ts';
import { h, mount } from '../dom.ts';
import { icon } from '../icons/index.ts';
import { startRun } from './home.ts';

/**
 * The one-screen, three-line introduction (SPEC 1.10). Shown once before the first run, where its
 * button starts the draft directly; reachable again from Home and Settings.
 */
export function renderHow(app: App, root: HTMLElement, options: { first?: boolean } = {}): void {
  const { t } = app.i18n;
  const first = options.first === true;
  const lines = [
    { icon: 'perfect', text: t('onboarding.perfect', { range: app.fmt.range(19, 28) }) },
    { icon: 'storm', text: t('onboarding.bad') },
    { icon: 'check', text: t('onboarding.pick') },
  ] as const;
  const message = h('p', { class: 'screen__error', role: 'alert' });
  const start = button({
    label: t('onboarding.start'),
    variant: 'primary',
    full: true,
    onClick: () => {
      app.store.update((s) => {
        s.onboarded = true;
      });
      void startRun(app, 'daily', { btn: start, message });
    },
  });

  mount(
    root,
    h(
      'main',
      { class: 'screen' },
      first
        ? null
        : backButton(t('back'), () => {
            app.go('home');
          }),
      h('h1', null, t('onboarding.title')),
      h(
        'ul',
        { class: 'how__lines' },
        ...lines.map((l) =>
          h('li', { class: 'how__line' }, icon(l.icon, { size: 32 }), h('span', null, l.text)),
        ),
      ),
      h('p', { class: 'muted' }, t('app.goal')),
      h('div', { class: 'screen__actions' }, message, first ? start : null),
    ),
  );
}
