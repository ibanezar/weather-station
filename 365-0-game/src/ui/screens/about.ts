import type { App } from '../../app/app.ts';
import { backButton } from '../components/backButton.ts';
import { button } from '../components/button.ts';
import { h, mount } from '../dom.ts';

export function renderAbout(app: App, root: HTMLElement): void {
  const { t } = app.i18n;
  mount(
    root,
    h(
      'main',
      { class: 'screen' },
      backButton(t('settings.back'), () => {
        app.go('settings');
      }),
      h('h1', null, t('about.title')),
      h('p', null, t('app.goal')),
      h('h2', null, t('about.attribution.title')),
      h('p', null, t('about.attribution')),
      h('p', { class: 'muted' }, t('about.resolution')),
      h(
        'p',
        null,
        h(
          'a',
          { href: 'https://open-meteo.com', rel: 'noopener', target: '_blank' },
          'Open-Meteo.com',
        ),
      ),
      button({
        label: t('about.privacy'),
        variant: 'secondary',
        onClick: () => {
          app.go('privacy');
        },
      }),
    ),
  );
}

export function renderPrivacy(app: App, root: HTMLElement): void {
  const { t } = app.i18n;
  mount(
    root,
    h(
      'main',
      { class: 'screen' },
      backButton(t('settings.back'), () => {
        app.go('settings');
      }),
      h('h1', null, t('privacy.title')),
      h('p', null, t('privacy.p1')),
      h('p', null, t('privacy.p2')),
      h('p', null, t('privacy.p3')),
      h('p', null, t('privacy.p4')),
    ),
  );
}
