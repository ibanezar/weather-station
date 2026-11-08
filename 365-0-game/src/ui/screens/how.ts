import { THRESHOLDS } from '../../engine/thresholds.ts';
import type { App } from '../../app/app.ts';
import { backButton } from '../components/backButton.ts';
import { h, mount } from '../dom.ts';
import { icon } from '../icons/index.ts';

/**
 * The three-line introduction (SPEC 1.10) with the goal. Home carries the same story for first-time
 * visitors; this screen is the full version, reachable from Home and Settings.
 */
export function renderHow(app: App, root: HTMLElement): void {
  const { t } = app.i18n;
  const range = app.fmt.range(THRESHOLDS.perfect.tmaxCMin, THRESHOLDS.perfect.tmaxCMax);
  const lines = [
    { icon: 'check', text: t('onboarding.perfect') },
    { icon: 'ok', text: t('onboarding.bad') },
    { icon: 'perfect', text: t('onboarding.pick', { range }) },
  ] as const;
  mount(
    root,
    h(
      'main',
      { class: 'screen' },
      backButton(t('back'), () => {
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
      h('p', { class: 'muted' }, t('onboarding.goal')),
    ),
  );
}
