// The daily mystery: a real day of weather, three cities, which one? Each clue after the first costs a point.
import type { App } from '../../app/app.ts';
import { cities, loadMystery } from '../../app/data.ts';
import { localDate, msUntilTomorrow } from '../../app/dates.ts';
import { shareMystery } from '../../app/share.ts';
import maskJson from '../../data/worldmask.json';
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
import { drawWorldMap } from '../canvas/worldmap.ts';
import { button } from '../components/button.ts';
import { dayDial, fillBar, rangeBar } from '../components/clueViz.ts';
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

    interface ClueLine {
      text: string;
      viz?: Element;
      /** The picture goes beside the text instead of under it. */
      side?: boolean;
    }
    const clueLines = (clue: Clue): ClueLine[] => {
      const w = puzzle.w;
      switch (clue) {
        case 'temp':
          return [
            {
              text: t('mystery.temp', { high: fmt.temperature(w.tx), low: fmt.temperature(w.tn) }),
              viz: rangeBar(w.tn, w.tx),
            },
          ];
        case 'sky':
          return [
            { text: t('mystery.cloud', { n: w.cl }), viz: fillBar('cloud', w.cl, 100) },
            w.p > 0
              ? { text: t('mystery.rain', { mm: fmt.number(w.p) }), viz: fillBar('rain', w.p, 30) }
              : { text: t('mystery.dry') },
            ...(w.s > 0
              ? [
                  {
                    text: t('mystery.snow', { cm: fmt.number(w.s) }),
                    viz: fillBar('snow', w.s, 20),
                  },
                ]
              : []),
          ];
        case 'wind':
          return [{ text: t('mystery.gust', { kmh: w.g }), viz: fillBar('wind', w.g, 120) }];
        case 'daylight': {
          const minutes = dayLengthMinutes(answer.lat, puzzle.m, puzzle.d);
          const text =
            minutes <= 0
              ? t('mystery.polarNight')
              : minutes >= 1440
                ? t('mystery.polarDay')
                : t('mystery.daylight', { time: fmt.duration(minutes * 60000) });
          return [{ text, viz: dayDial(minutes), side: true }];
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
          { class: 'mystery__clue-body' },
          h('strong', null, t(`mystery.clue.${clue}` as const)),
          ...clueLines(clue).map((line) =>
            h(
              'div',
              { class: `mystery__line${line.side ? ' mystery__line--side' : ''}` },
              h('p', { class: 'num' }, line.text),
              line.viz ?? null,
            ),
          ),
        ),
      );

    const finished = (): boolean => isFinished(state);
    const wrong = (id: string): boolean => state.wrong.includes(id);
    const dayIso = `${String(puzzle.year)}-${String(puzzle.m + 1).padStart(2, '0')}-${String(puzzle.d).padStart(2, '0')}`;

    // The dot map of the three cities, drawn once the panel is on the page (it needs its width).
    const mapCanvas = h('canvas', {
      class: 'mystery__map',
      role: 'img',
      'aria-label': t('mystery.mapLabel', {
        list: order.map((c, i) => `${String(i + 1)} ${fmt.cityName(c)}`).join(', '),
      }),
    });
    const paintMap = (): void => {
      if (!mapCanvas.isConnected) return;
      drawWorldMap(
        mapCanvas,
        maskJson,
        order.map((c, i) => ({
          latitude: c.lat,
          longitude: c.lon,
          n: i + 1,
          answer: c.id === puzzle.city,
        })),
      );
    };
    const mapObserver = new ResizeObserver(paintMap);
    const scheme = window.matchMedia('(prefers-color-scheme: dark)');
    scheme.addEventListener('change', paintMap);
    app.onLeave(() => {
      mapObserver.disconnect();
      scheme.removeEventListener('change', paintMap);
    });

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
        mapCanvas,
        h('h3', null, t('mystery.explain', { month: fmt.month(puzzle.m) })),
        h(
          'ul',
          { class: 'mystery__usual' },
          ...order.map((c, i) => {
            const typ = puzzle.typ[c.id];
            return h(
              'li',
              { class: c.id === puzzle.city ? 'is-answer' : null },
              h('span', { class: 'mystery__n num', 'aria-hidden': 'true' }, String(i + 1)),
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
      if (done) {
        mapObserver.observe(mapCanvas);
        requestAnimationFrame(paintMap);
      }
    }
    draw();
  };

  load();
}
