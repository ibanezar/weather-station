import type { App } from '../../app/app.ts';
import { CHASE_ICON, chaseKey, gradeKey } from '../../app/chase-text.ts';
import { activeStreak, localDate } from '../../app/dates.ts';
import { computeStats } from '../../app/progress-stats.ts';
import { backButton } from '../components/backButton.ts';
import { h, mount } from '../dom.ts';
import { icon } from '../icons/index.ts';

function tile(value: string, label: string): HTMLElement {
  return h(
    'div',
    { class: 'stats__tile' },
    h('strong', { class: 'stats__value num' }, value),
    h('span', { class: 'muted stats__label' }, label),
  );
}

export function renderStats(app: App, root: HTMLElement): void {
  const { t, plural } = app.i18n;
  const { fmt } = app;
  const stats = computeStats(app.store.state);
  const streak = activeStreak(app.store.state.streak, localDate());
  const dash = '–';
  const record = (r: { w: number; d: number; l: number } | null): string =>
    r ? fmt.record(r) : dash;

  const body =
    stats.runs === 0 && stats.dailies === 0 && stats.mystery.played === 0
      ? h('p', { class: 'muted' }, t('stats.empty'))
      : h(
          'div',
          { class: 'stats__body' },
          h(
            'div',
            { class: 'stats__tiles' },
            tile(String(stats.runs), t('stats.played')),
            tile(String(streak), t('stats.streak')),
            tile(String(stats.longestStreak), t('stats.longestStreak')),
            tile(String(stats.dailies), t('stats.dailies')),
            ...(stats.mystery.played > 0 && stats.mystery.averagePoints !== null
              ? [
                  tile(String(stats.mystery.played), t('stats.mysteries')),
                  tile(
                    fmt.number(Math.round(stats.mystery.averagePoints * 10) / 10),
                    t('stats.mysteryAvg'),
                  ),
                ]
              : []),
          ),
          h(
            'table',
            { class: 'result__table stats__table' },
            h(
              'thead',
              null,
              h(
                'tr',
                null,
                h('th', { scope: 'col' }, t('stats.chase')),
                h('th', { scope: 'col' }, t('stats.bestDaily')),
                h('th', { scope: 'col' }, t('stats.bestEndless')),
                h('th', { scope: 'col', class: 'num' }, t('stats.games')),
              ),
            ),
            h(
              'tbody',
              null,
              ...stats.perChase.map((c) =>
                h(
                  'tr',
                  null,
                  h(
                    'th',
                    { scope: 'row' },
                    h(
                      'span',
                      { class: 'stats__chase' },
                      icon(CHASE_ICON[c.chase], { size: 20 }),
                      t(chaseKey(c.chase, 'name')),
                    ),
                  ),
                  h('td', { class: 'num' }, record(c.bestDaily)),
                  h('td', { class: 'num' }, record(c.bestEndless)),
                  h('td', { class: 'num' }, String(c.runs)),
                ),
              ),
            ),
          ),
          stats.recent.length > 0
            ? h(
                'section',
                null,
                h('h2', null, t('stats.recent')),
                h(
                  'ul',
                  { class: 'stats__recent' },
                  ...stats.recent.map((d) =>
                    h(
                      'li',
                      null,
                      h('span', { class: 'stats__date' }, fmt.date(d.date)),
                      h('span', { class: 'muted' }, t(chaseKey(d.chase, 'name'))),
                      h('strong', { class: 'num' }, fmt.record(d.record)),
                      h('span', { class: 'muted' }, t(gradeKey(d.chase, d.grade))),
                    ),
                  ),
                ),
              )
            : null,
        );

  mount(
    root,
    h(
      'main',
      { class: 'screen screen--stats' },
      backButton(t('settings.back'), () => {
        app.go('home');
      }),
      h('h1', null, t('stats.title')),
      streak >= 2 ? h('p', { class: 'muted' }, plural('home.streak', streak)) : null,
      body,
      h('p', { class: 'muted stats__note' }, t('stats.note')),
    ),
  );
}
