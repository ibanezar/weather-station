import type { App } from '../../app/app.ts';
import { cities } from '../../app/data.ts';
import { activeStreak, localDate, msUntilTomorrow } from '../../app/dates.ts';
import { shareResult } from '../../app/share.ts';
import type { SeedCity } from '../../data/types.ts';
import type { MessageKey } from '../../i18n/index.ts';
import { drawGrid, resolvePalette, type GridColumn } from '../canvas/grid.ts';
import { button } from '../components/button.ts';
import { chip } from '../components/chip.ts';
import { showToast } from '../components/toast.ts';
import { h, mount } from '../dom.ts';
import { isPatternMode } from '../settings.ts';
import { doReroll, randomEntropy, newSession } from '../../app/session.ts';
import { netsLeft } from '../../engine/run.ts';
import { loadEngineData } from '../../app/data.ts';

const cityById = (id: string): SeedCity => cities.find((c) => c.id === id) as SeedCity;

export function renderResult(app: App, root: HTMLElement): void {
  const session = app.session;
  const result = session?.state.result;
  if (!session || !result) {
    app.go('home');
    return;
  }
  const { t, plural } = app.i18n;
  const { fmt } = app;
  const key = (k: string): MessageKey => k as MessageKey;
  const daily = session.mode === 'daily';
  const percent = Math.round(result.ratio * 100);
  const gradeName = t(key(`grade.${result.grade}`));
  const streak = daily ? activeStreak(app.store.state.streak, localDate()) : 0;

  // The grid: highlight a month when its row in "What if" is tapped.
  const columns: GridColumn[] = result.rounds.map((r) => ({ days: r.days }));
  const alt = t('result.gridAlt', { w: result.record.w, d: result.record.d, l: result.record.l });
  const labels = h(
    'div',
    { class: 'grid-panel__labels', 'aria-hidden': 'true' },
    ...result.rounds.map((r) => h('span', null, fmt.abbreviation(cityById(r.cityId)))),
  );
  const canvas = h('canvas', { role: 'img', 'aria-label': alt });
  const well = h('div', { class: 'well grid-panel' }, labels, canvas);
  let highlighted: number | null = null;
  const paint = (): void => {
    drawGrid(canvas, columns, resolvePalette(well), {
      pattern: isPatternMode(),
      highlightColumn: highlighted,
    });
  };

  // The grid as a list, behind a toggle (the text alternative of the picture).
  const table = h(
    'table',
    { class: 'result__table' },
    h(
      'thead',
      null,
      h(
        'tr',
        null,
        h('th', { scope: 'col' }, t('result.month')),
        h('th', { scope: 'col' }, t('result.yourPick')),
        h('th', { scope: 'col' }, t('result.recordLabel')),
      ),
    ),
    h(
      'tbody',
      null,
      ...result.rounds.map((r) =>
        h(
          'tr',
          null,
          h('th', { scope: 'row' }, fmt.month(r.month)),
          h(
            'td',
            null,
            t('result.pickedRow', { city: fmt.cityName(cityById(r.cityId)), year: r.year }),
          ),
          h('td', { class: 'num' }, fmt.record(r.record)),
        ),
      ),
    ),
  );
  const listBox = h('div', { class: 'result__list' }, table);
  listBox.hidden = true;
  const listToggle = button({
    label: t('result.showList'),
    variant: 'quiet',
    onClick: () => {
      listBox.hidden = !listBox.hidden;
      listToggle
        .querySelector('span')
        ?.replaceChildren(listBox.hidden ? t('result.showList') : t('result.hideList'));
      listToggle.setAttribute('aria-expanded', String(!listBox.hidden));
    },
  });
  listToggle.setAttribute('aria-expanded', 'false');

  // "What if": what the player picked against the best option, month by month.
  const rowButtons = result.rounds.map((r, i) => {
    const mine = cityById(r.cityId);
    const bestCity = cityById(r.best.cityId);
    const same = r.cityId === r.best.cityId;
    const b = h(
      'button',
      { type: 'button', class: 'whatif__row', 'aria-pressed': 'false' },
      h('span', { class: 'whatif__month' }, fmt.month(r.month)),
      h(
        'span',
        { class: 'whatif__pick' },
        t('result.pickedRow', { city: fmt.cityName(mine), year: r.year }),
      ),
      h(
        'span',
        { class: 'whatif__best muted' },
        same
          ? t('result.sameAsBest')
          : t('result.bestRow', { city: fmt.cityName(bestCity), year: r.best.year }),
      ),
    );
    b.addEventListener('click', () => {
      highlighted = highlighted === i ? null : i;
      for (const other of rowButtons)
        other.setAttribute('aria-pressed', String(other === b && highlighted === i));
      paint();
    });
    return b;
  });
  const whatIf = h(
    'details',
    { class: 'whatif' },
    h('summary', null, t('result.whatIf')),
    h('p', { class: 'muted' }, t('result.whatIfIntro')),
    h('div', { class: 'whatif__rows' }, ...rowButtons),
  );

  const observer = new ResizeObserver(paint);
  let timer: ReturnType<typeof setInterval> | undefined;

  // Second chances: draw a month again. The new year stands, better or worse.
  const chancesLeft = netsLeft(session.state, session.data);
  const useChance = (i: number): void => {
    const before = result.rounds[i]?.record.w ?? 0;
    const y = window.scrollY;
    doReroll(session, i);
    const next = session.state.result;
    if (!next) return;
    const picks = [...session.state.picks];
    if (session.mode === 'daily' && session.date !== undefined) {
      app.store.updateDaily(session.date, {
        picks,
        rerolls: [...session.state.rerolls],
        record: next.record,
        grade: next.grade,
      });
    } else {
      app.store.recordEndless(next.record);
    }
    showToast({
      message: t('result.chances.done', {
        month: fmt.month(result.rounds[i]?.month ?? 0),
        before,
        after: next.rounds[i]?.record.w ?? 0,
      }),
    });
    observer.disconnect();
    clearInterval(timer);
    renderResult(app, root);
    window.scrollTo(0, y);
  };
  const chanceButtons = result.rounds.map((r, i) =>
    h(
      'button',
      {
        type: 'button',
        class: 'chances__btn',
        disabled: chancesLeft <= 0,
        onClick: () => {
          useChance(i);
        },
      },
      h('span', null, fmt.month(r.month).slice(0, 3)),
      ' ',
      h('span', { class: 'num' }, String(r.record.w)),
      r.rerolls > 0
        ? h('span', { class: 'chances__mark muted' }, ` ${t('result.chances.mark')}`)
        : null,
      h(
        'span',
        { class: 'visually-hidden' },
        `, ${t('result.chances.month', { month: fmt.month(r.month) })}`,
      ),
    ),
  );
  const chancesBox = h(
    'section',
    { class: 'chances', 'aria-label': t('result.chances.title') },
    h('h2', null, t('result.chances.title')),
    h(
      'p',
      { class: 'muted' },
      t('result.chances.intro', {
        left: chancesLeft > 0 ? plural('draft.chancesLeft', chancesLeft) : t('result.chances.none'),
      }),
      chancesLeft <= 0 ? ` ${t('result.chances.gain')}` : '',
    ),
    h('div', { class: 'chances__grid' }, ...chanceButtons),
  );

  // Actions.
  const status = h('p', { class: 'muted result__status', role: 'status', 'aria-live': 'polite' });
  const report = (outcome: Awaited<ReturnType<typeof shareResult>>): void => {
    status.textContent =
      outcome === 'shared'
        ? t('result.shared')
        : outcome === 'downloaded'
          ? t('result.downloaded')
          : outcome === 'copied'
            ? t('result.copied')
            : t('result.shareFailed');
  };
  const shareBtn = button({
    label: t('result.share'),
    variant: 'primary',
    icon: 'share',
    full: true,
    onClick: () => {
      void shareResult(app, session, 'feed').then(report);
    },
  });
  const storyBtn = button({
    label: t('result.shareStory'),
    variant: 'quiet',
    onClick: () => {
      void shareResult(app, session, 'story').then(report);
    },
  });
  const endlessBtn = button({
    label: t('result.playEndless'),
    variant: 'secondary',
    full: true,
    onClick: () => {
      endlessBtn.disabled = true;
      void loadEngineData().then(
        (data) => {
          app.session = newSession('endless', data, { entropy: randomEntropy() });
          app.go('draft');
        },
        () => {
          endlessBtn.disabled = false;
          showToast({ message: t('error.world') });
        },
      );
    },
  });
  const countdown = h('p', { class: 'muted num' });
  const updateCountdown = (): void => {
    countdown.textContent = t('result.countdown', { time: fmt.duration(msUntilTomorrow()) });
  };

  mount(
    root,
    h(
      'main',
      { class: 'screen screen--result' },
      h(
        'header',
        { class: 'result__head' },
        h(
          'h1',
          { class: 'result__record num' },
          h('span', { class: 'visually-hidden' }, `${t('result.recordLabel')} `),
          fmt.record(result.record),
        ),
        h(
          'div',
          { class: 'legend' },
          chip({ label: t('result.legend.win'), swatch: 'p' }),
          chip({ label: t('result.legend.draw'), swatch: 'o' }),
          chip({ label: t('result.legend.loss'), swatch: 'loss' }),
          streak >= 2 ? chip({ label: plural('result.streak', streak), icon: 'streak' }) : null,
        ),
      ),
      h(
        'section',
        { class: 'result__grade', 'aria-label': gradeName },
        h('h2', null, gradeName),
        h(
          'p',
          null,
          t(daily ? 'result.gradeLine.daily' : 'result.gradeLine.endless', {
            grade: gradeName,
            percent,
          }),
        ),
        h(
          'p',
          { class: 'result__best num' },
          h(
            'strong',
            null,
            t(daily ? 'result.bestToday' : 'result.bestRun', { n: result.bestRecord.w }),
          ),
          ' ',
          h('span', { class: 'muted' }, t('result.yours', { n: result.record.w })),
        ),
      ),
      h(
        'div',
        { class: 'screen__actions' },
        shareBtn,
        storyBtn,
        endlessBtn,
        status,
        daily ? countdown : null,
      ),
      chancesBox,
      well,
      listToggle,
      listBox,
      whatIf,
      button({
        label: t('result.home'),
        variant: 'quiet',
        onClick: () => {
          app.go('home');
        },
      }),
    ),
  );

  paint();
  observer.observe(well);
  if (daily) {
    updateCountdown();
    timer = setInterval(updateCountdown, 30000);
  }
  app.onLeave(() => {
    observer.disconnect();
    clearInterval(timer);
  });
}
