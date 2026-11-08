// The daily mystery: a real day of weather, three cities, which one? Each clue after the first costs a point.
import type { App } from '../../app/app.ts';
import { cities, loadMystery } from '../../app/data.ts';
import { localDate, msUntilTomorrow } from '../../app/dates.ts';
import { shareMystery } from '../../app/share.ts';
import type { SeedCity } from '../../data/types.ts';
import {
  candidateOrder,
  CLUES,
  dayLengthMinutes,
  guess,
  isFinished,
  MAX_POINTS,
  newMystery,
  points,
  puzzleFor,
  resultOf,
  reveal,
  stateFrom,
  type Clue,
  type MysteryState,
  type Puzzle,
} from '../../engine/mystery.ts';
import type { IconName } from '../icons/index.ts';
import { backButton } from '../components/backButton.ts';
import { button } from '../components/button.ts';
import { h, mount } from '../dom.ts';
import { icon } from '../icons/index.ts';

const CLUE_ICON: Record<Clue, IconName> = {
  temp: 'heat',
  sky: 'ok',
  wind: 'wind',
  daylight: 'perfect',
};

const cityById = (id: string): SeedCity => cities.find((c) => c.id === id) as SeedCity;

export function renderMystery(app: App, root: HTMLElement): void {
  const { t, plural } = app.i18n;
  let alive = true;
  app.onLeave(() => {
    alive = false;
  });

  const holder = h('div', { class: 'mystery__holder' });
  mount(
    root,
    h(
      'main',
      { class: 'screen screen--mystery' },
      backButton(t('settings.back'), () => {
        app.go('home');
      }),
      h('h1', null, t('mystery.title')),
      holder,
    ),
  );

  const load = (): void => {
    holder.replaceChildren(h('p', { class: 'muted' }, '…'));
    loadMystery().then(
      (file) => {
        if (alive) play(puzzleFor(file, localDate()));
      },
      () => {
        if (!alive) return;
        holder.replaceChildren(
          h('p', { class: 'screen__error', role: 'alert' }, t('mystery.loadError')),
          button({ label: t('error.retry'), variant: 'secondary', onClick: load }),
        );
      },
    );
  };

  const play = (puzzle: Puzzle): void => {
    const today = localDate();
    const stored = app.store.state.mystery[today];
    let state: MysteryState = stored ? stateFrom(stored, puzzle) : newMystery();
    if (!stored) {
      app.store.recordMystery(today, resultOf(state, puzzle));
      app.count({ ev: 'start', mode: 'mystery' });
    }
    const order = candidateOrder(puzzle, today).map(cityById);
    const answer = cityById(puzzle.city);
    const { fmt } = app;

    const save = (next: MysteryState): void => {
      const wasFinished = isFinished(state);
      state = next;
      const result = resultOf(state, puzzle);
      app.store.recordMystery(today, result);
      if (!wasFinished && result.done) {
        app.count({ ev: 'finish', mode: 'mystery', points: result.points });
      }
      draw();
    };

    const clueText = (clue: Clue): string[] => {
      const w = puzzle.w;
      switch (clue) {
        case 'temp':
          return [t('mystery.temp', { high: fmt.temperature(w.tx), low: fmt.temperature(w.tn) })];
        case 'sky':
          return [
            t('mystery.cloud', { n: w.cl }),
            w.p > 0 ? t('mystery.rain', { mm: fmt.number(w.p) }) : t('mystery.dry'),
            ...(w.s > 0 ? [t('mystery.snow', { cm: fmt.number(w.s) })] : []),
          ];
        case 'wind':
          return [t('mystery.gust', { kmh: w.g })];
        case 'daylight': {
          const minutes = dayLengthMinutes(answer.lat, puzzle.m, puzzle.d);
          if (minutes <= 0) return [t('mystery.polarNight')];
          if (minutes >= 1440) return [t('mystery.polarDay')];
          return [t('mystery.daylight', { time: fmt.duration(minutes * 60000) })];
        }
      }
    };

    const clueItem = (clue: Clue): HTMLElement =>
      h(
        'li',
        { class: 'mystery__clue' },
        icon(CLUE_ICON[clue], { size: 28 }),
        h(
          'div',
          null,
          h('strong', null, t(`mystery.clue.${clue}` as const)),
          ...clueText(clue).map((line) => h('p', { class: 'num' }, line)),
        ),
      );

    const finished = (): boolean => isFinished(state);
    const wrong = (id: string): boolean => state.wrong.includes(id);
    const dayIso = `${String(puzzle.year)}-${String(puzzle.m + 1).padStart(2, '0')}-${String(puzzle.d).padStart(2, '0')}`;

    const resultPanel = (): HTMLElement => {
      const pts = points(state);
      return h(
        'section',
        { class: 'mystery__result well', 'aria-live': 'polite' },
        h(
          'h2',
          null,
          state.solved ? t('mystery.right') : t('mystery.missed', { city: fmt.cityName(answer) }),
        ),
        h('p', { class: 'mystery__score num' }, t('mystery.score', { n: pts, max: MAX_POINTS })),
        h(
          'p',
          null,
          t('mystery.answer', {
            city: fmt.cityName(answer),
            country: fmt.country(answer.country),
            date: fmt.fullDate(dayIso),
          }),
        ),
        h('h3', null, t('mystery.explain', { month: fmt.month(puzzle.m) })),
        h(
          'ul',
          { class: 'mystery__usual' },
          ...order.map((c) => {
            const typ = puzzle.typ[c.id];
            return h(
              'li',
              { class: c.id === puzzle.city ? 'is-answer' : null },
              typ
                ? t('mystery.usually', {
                    city: fmt.cityName(c),
                    country: fmt.country(c.country),
                    high: fmt.range(typ[0], typ[1]),
                    low: fmt.range(typ[2], typ[3]),
                    wet: typ[4],
                  })
                : fmt.cityName(c),
            );
          }),
        ),
        h('p', { class: 'muted' }, t('mystery.note')),
      );
    };

    const status = h('p', { class: 'muted result__status', role: 'status', 'aria-live': 'polite' });
    const countdown = h(
      'p',
      { class: 'muted num' },
      t('result.countdown', { time: fmt.duration(msUntilTomorrow()) }),
    );

    function draw(): void {
      const done = finished();
      const shown = done ? CLUES.length : state.revealed;
      const parts: (Node | null)[] = [
        h('p', { class: 'muted' }, t('mystery.intro', { month: fmt.month(puzzle.m) })),
        h(
          'ul',
          { class: 'mystery__clues', 'aria-label': t('mystery.clues') },
          ...CLUES.slice(0, shown).map(clueItem),
        ),
        done
          ? null
          : h(
              'div',
              { class: 'mystery__more' },
              h(
                'p',
                { class: 'muted num' },
                plural('mystery.worth', MAX_POINTS + 1 - state.revealed),
              ),
              state.revealed < CLUES.length
                ? button({
                    label: t('mystery.more'),
                    variant: 'quiet',
                    onClick: () => {
                      save(reveal(state));
                    },
                  })
                : null,
            ),
        h('h2', { class: 'mystery__which' }, t('mystery.which')),
        h(
          'div',
          { class: 'mystery__choices' },
          ...order.map((c) => {
            const crossed = wrong(c.id);
            const isAnswer = done && c.id === puzzle.city;
            const b = h(
              'button',
              {
                type: 'button',
                class: `mystery__choice${crossed ? ' is-crossed' : ''}${isAnswer ? ' is-answer' : ''}`,
                disabled: done || crossed,
                onClick: () => {
                  save(guess(state, puzzle, c.id));
                },
              },
              h('strong', null, fmt.cityName(c)),
              h(
                'span',
                { class: 'muted' },
                crossed ? t('mystery.crossed') : fmt.country(c.country),
              ),
            );
            return b;
          }),
        ),
        done ? resultPanel() : null,
        done
          ? h(
              'div',
              { class: 'screen__actions' },
              button({
                label: t('result.share'),
                variant: 'primary',
                icon: 'share',
                full: true,
                onClick: () => {
                  void shareMystery(app, today, points(state), MAX_POINTS).then((outcome) => {
                    status.textContent =
                      outcome === 'shared'
                        ? t('result.shared')
                        : outcome === 'copied'
                          ? t('result.copied')
                          : t('result.shareFailed');
                  });
                },
              }),
              status,
              countdown,
            )
          : null,
      ];
      holder.replaceChildren(...parts.filter((x): x is Node => x !== null));
    }
    draw();
  };

  load();
}
