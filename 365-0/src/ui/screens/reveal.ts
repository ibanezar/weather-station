import type { App } from '../../app/app.ts';
import { doComplete } from '../../app/session.ts';
import { DAYS_IN_MONTH } from '../../data/types.ts';
import type { DayType } from '../../engine/thresholds.ts';
import type { MessageKey } from '../../i18n/index.ts';
import { drawGrid, resolvePalette, type GridColumn } from '../canvas/grid.ts';
import { button } from '../components/button.ts';
import { chip } from '../components/chip.ts';
import { h, mount } from '../dom.ts';
import { isPatternMode, isReducedMotion } from '../settings.ts';
import { cities } from '../../app/data.ts';

/** Reveal timing (SPEC 6.6): months left to right, tiles top to bottom with an 8 ms stagger. */
const MONTH_MS = 500;
const STAGGER_MS = 8;
const FLIP_MS = 120;
const FLASH_MS = 200;

interface Tile {
  type: DayType;
  start: number;
}

export function renderReveal(app: App, root: HTMLElement): void {
  const session = app.session;
  const result = session?.state.result;
  if (!session || !result) {
    app.go('home');
    return;
  }
  const { t } = app.i18n;
  const { fmt } = app;
  const key = (k: string): MessageKey => k as MessageKey;

  // The result is known as soon as the draft is locked: store it now, so closing the app mid-reveal
  // still counts the run (and a daily cannot be replayed).
  const firstTime = session.state.phase === 'revealing';
  if (firstTime) {
    doComplete(session);
    if (session.mode === 'daily' && session.date !== undefined) {
      app.store.recordDaily(session.date, {
        picks: [...session.state.picks],
        record: result.record,
        grade: result.grade,
      });
    } else {
      app.store.recordEndless(result.record);
    }
  }

  const columns: GridColumn[] = result.rounds.map((r) => ({ days: r.days }));
  const tiles: Tile[] = [];
  result.rounds.forEach((r, m) => {
    r.days.forEach((type, d) => {
      tiles.push({ type, start: m * MONTH_MS + d * STAGGER_MS });
    });
  });
  const lastMonth = result.rounds.length - 1;
  const total =
    lastMonth * MONTH_MS + ((DAYS_IN_MONTH[lastMonth] ?? 31) - 1) * STAGGER_MS + FLIP_MS + FLASH_MS;

  const w = h('span', null, '0');
  const d = h('span', null, '0');
  const l = h('span', null, '0');
  const counter = h('p', { class: 'reveal__record num', 'aria-hidden': 'true' }, w, '-', d, '-', l);
  const labels = h(
    'div',
    { class: 'grid-panel__labels', 'aria-hidden': 'true' },
    ...result.rounds.map((r) =>
      h(
        'span',
        null,
        fmt.abbreviation(
          cities.find((c) => c.id === r.cityId) ?? (cities[0] as (typeof cities)[number]),
        ),
      ),
    ),
  );
  const canvas = h('canvas', {
    role: 'img',
    'aria-label': t('reveal.gridAlt', {
      w: result.record.w,
      d: result.record.d,
      l: result.record.l,
    }),
  });
  const well = h('div', { class: 'well grid-panel' }, labels, canvas);
  const hint = h('p', { class: 'muted reveal__hint' }, t('reveal.skip'));
  const announce = h('div', { class: 'visually-hidden', role: 'status', 'aria-live': 'polite' });
  const seeResult = button({
    label: t('reveal.see'),
    variant: 'primary',
    full: true,
    onClick: () => {
      app.go('result');
    },
  });
  const gradeTitle = h('h2', { class: 'reveal__grade' }, t(key(`grade.${result.grade}`)));
  const done = h('div', { class: 'reveal__done' }, gradeTitle, seeResult);
  done.hidden = true;

  let frame = 0;
  let startTime = 0;
  let finished = false;

  const progressOf = (index: number, now: number): number => {
    const tile = tiles[index] as Tile;
    const x = (now - tile.start) / FLIP_MS;
    if (x <= 0) return 0;
    if (x < 1) return x;
    if (tile.type !== 'p') return 1;
    const f = (now - tile.start - FLIP_MS) / FLASH_MS;
    return f < 1 ? 1 + f : 2;
  };

  function paint(now: number): void {
    drawGrid(canvas, columns, resolvePalette(well), {
      pattern: isPatternMode(),
      tileProgress: (i) => progressOf(i, now),
    });
    let wins = 0;
    let draws = 0;
    let losses = 0;
    for (const tile of tiles) {
      if (now < tile.start + FLIP_MS) break; // starts are in order, so nothing later is resolved
      if (tile.type === 'p') wins += 1;
      else if (tile.type === 'o') draws += 1;
      else losses += 1;
    }
    w.textContent = String(wins);
    d.textContent = String(draws);
    l.textContent = String(losses);
  }

  function finish(playEffects: boolean): void {
    if (finished) return;
    finished = true;
    cancelAnimationFrame(frame);
    paint(total + 1);
    w.textContent = String(result?.record.w);
    d.textContent = String(result?.record.d);
    l.textContent = String(result?.record.l);
    hint.hidden = true;
    done.hidden = false;
    // Announce the final record and grade once.
    announce.textContent = t('reveal.announce', {
      w: result?.record.w ?? 0,
      d: result?.record.d ?? 0,
      l: result?.record.l ?? 0,
      grade: gradeTitle.textContent,
    });
    if (playEffects) {
      app.feedback.haptic('success');
      app.feedback.sound('done');
    }
    seeResult.focus();
  }

  function tick(): void {
    const now = performance.now() - startTime;
    if (now >= total) {
      finish(true);
      return;
    }
    paint(now);
    frame = requestAnimationFrame(tick);
  }

  mount(
    root,
    h(
      'main',
      { class: 'screen screen--reveal' },
      h('h1', { class: 'reveal__title' }, t('reveal.title')),
      counter,
      h(
        'div',
        { class: 'legend' },
        chip({ label: t('result.legend.win'), swatch: 'p' }),
        chip({ label: t('result.legend.draw'), swatch: 'o' }),
        chip({ label: t('result.legend.loss'), swatch: 'loss' }),
      ),
      well,
      hint,
      done,
      announce,
    ),
  );

  const skipping = firstTime && !isReducedMotion();
  if (skipping) {
    // Tap anywhere to skip to the end state.
    root.addEventListener(
      'pointerdown',
      () => {
        finish(true);
      },
      { once: true },
    );
    startTime = performance.now();
    frame = requestAnimationFrame(tick);
  } else {
    // Reduced motion, or coming back to a finished reveal: everything at once, announced once.
    requestAnimationFrame(() => {
      finish(false);
    });
  }
  const observer = new ResizeObserver(() => {
    if (finished) paint(total + 1);
  });
  observer.observe(well);
  app.onLeave(() => {
    observer.disconnect();
    cancelAnimationFrame(frame);
  });
}
