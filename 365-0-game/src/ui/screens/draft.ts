import type { App } from '../../app/app.ts';
import { cities } from '../../app/data.ts';
import { doFinish, doKeep, doPick, doReroll, doScout, type Session } from '../../app/session.ts';
import { DAYS_IN_MONTH, type SeedCity } from '../../data/types.ts';
import { chaseKey } from '../../app/chase-text.ts';
import { chainProgress, combosIfPicked, findCombos } from '../../engine/combos.ts';
import { monthStrip } from '../../engine/strip.ts';
import { monthRisk } from '../../engine/risk.ts';
import {
  isScouted,
  monthOf,
  netsTotal,
  pendingMonth,
  scoutInfo,
  type PickedRound,
} from '../../engine/run.ts';
import { CHASES } from '../../engine/chase.ts';
import type { DayType } from '../../engine/thresholds.ts';
import type { MessageKey } from '../../i18n/index.ts';
import { drawGrid, resolvePalette, type GridColumn } from '../canvas/grid.ts';
import { button } from '../components/button.ts';
import { chip } from '../components/chip.ts';
import { cityCard, type CityCard } from '../components/cityCard.ts';
import { confirmDialog } from '../components/confirm.ts';
import { progress } from '../components/progress.ts';
import { showToast } from '../components/toast.ts';
import { h, mount } from '../dom.ts';
import { isPatternMode, isReducedMotion } from '../settings.ts';

/** How a month plays out after the pick: one tile every STAGGER_MS, each flipping for FLIP_MS. */
const STAGGER_MS = 24;
const FLIP_MS = 120;
const FLASH_MS = 200;
const cityById = (id: string): SeedCity => cities.find((c) => c.id === id) as SeedCity;

export function renderDraft(app: App, root: HTMLElement): void {
  const session = app.session;
  if (session?.state.phase !== 'drafting') {
    app.go('home');
    return;
  }
  const s: Session = session;
  const { t, plural } = app.i18n;
  const { fmt } = app;
  const world = s.data.world;
  const key = (k: string): MessageKey => k as MessageKey;

  const prog = progress({
    total: 12,
    roundText: (current, total) => t('draft.round', { current, total }),
    scoutsText: (n) => plural('draft.scoutsLeft', n),
    chancesText: (n) => plural('draft.chancesLeft', n),
  });
  const month = h('h1', { class: 'draft__month' });
  const ask = h('p', { class: 'muted draft__ask' });
  const eventSlot = h('div', { class: 'draft__event' });
  const chainSlot = h('p', { class: 'muted draft__chain', 'aria-live': 'polite' });
  const labels = h('div', { class: 'grid-panel__labels', 'aria-hidden': 'true' });
  const canvas = h('canvas');
  const well = h('div', { class: 'well grid-panel' }, labels, canvas);
  const cardsBox = h('div', {
    class: 'draft__cards',
    role: 'group',
    'aria-label': t('draft.cities'),
  });
  let cardList: CityCard[] = [];
  let frame = 0;
  /** The month being played out right now (set while a pick is pending). */
  let playing:
    { start: number; days: readonly DayType[]; offset: number; done: boolean } | undefined;

  const isInvented = (id: string): boolean =>
    s.data.events.some((e) => e.id === id && e.fictional === true);
  const picks = (): number => s.state.picks.length;
  const pickedCities = (): SeedCity[] => s.state.picks.map(cityById);
  const chances = (): number => netsTotal(s.state, s.data) - s.state.rerolls.length;

  const progressOf = (index: number, now: number): number => {
    if (!playing) return 1;
    const j = index - playing.offset;
    if (j < 0) return 1; // a month that is already final
    const x = (now - playing.start - j * STAGGER_MS) / FLIP_MS;
    if (x <= 0) return 0;
    if (x < 1) return x;
    if ((playing.days[j] ?? 'o') !== 'p') return 1;
    const f = (now - playing.start - j * STAGGER_MS - FLIP_MS) / FLASH_MS;
    return f < 1 ? 1 + f : 2;
  };

  /** The grid: every final month in its real weather, the pending one flipping tile by tile. */
  function drawPreview(now = performance.now()): void {
    const settled = s.state.settled;
    const columns: GridColumn[] = Array.from({ length: 12 }, (_, m) => {
      if (m < settled) return { days: monthOf(s.state, s.data, m).days };
      if (m === settled && playing) return { days: playing.days };
      return { days: null };
    });
    drawGrid(canvas, columns, resolvePalette(well), {
      pattern: isPatternMode(),
      compact: true,
      tileProgress: (i) => progressOf(i, now),
      flashTypes: CHASES[s.chase].win,
    });
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', t('draft.gridAlt', { months: settled }));
    labels.replaceChildren(
      ...columns.map((_, m) => {
        const id = s.state.picks[m];
        return h('span', null, id ? fmt.abbreviation(cityById(id)) : fmt.month(m).charAt(0));
      }),
    );
  }

  function makeCard(id: string, monthIndex: number): CityCard {
    const city = cityById(id);
    const name = fmt.cityName(city);
    const risk = monthRisk(s.data, id, monthIndex, s.chase);
    const combos = combosIfPicked(pickedCities(), city);
    const card = cityCard({
      risk: {
        level: risk.level,
        label:
          risk.level === 'none'
            ? t(chaseKey(s.chase, 'rarely'))
            : t(key(`draft.risk.${risk.level}`)),
        detail:
          risk.level === 'none'
            ? ''
            : t(chaseKey(s.chase, 'range'), { min: risk.min, max: risk.max }),
      },
      ...(combos.length > 0
        ? { combo: combos.map((c) => t(key(`draft.combo.${c}`))).join(' · ') }
        : {}),
      strip: monthStrip(s.data, id, monthIndex, s.chase),
      name,
      country: fmt.country(city.country),
      temperature: fmt.temperature(world.cities[id]?.t[monthIndex] ?? 0),
      archetype: city.archetype,
      archetypeLabel: t(key(`archetype.${city.archetype}`)),
      pickAction: t('draft.pick'),
      scoutLabel: t('draft.scout'),
      scoutFullLabel: t('draft.scoutCity', { city: name }),
      scoutedLabel: t('draft.scouted'),
      winLabel: t(chaseKey(s.chase, 'winLabel')),
      lossLabel: t(chaseKey(s.chase, 'lossLabel')),
      stepText: (b) => t('draft.stepOf', { n: b + 1 }),
      onPick: () => {
        onPick(id);
      },
      onScout: () => {
        onScout(id, card);
      },
    });
    if (isScouted(s.state, id)) card.showScout(scoutInfo(s.data, id, monthIndex, s.chase));
    if (s.state.scoutsLeft <= 0) card.setScoutEnabled(false);
    return card;
  }

  function renderRound(): void {
    cancelAnimationFrame(frame);
    const pending = pendingMonth(s.state, s.data);
    const round = s.state.draft[s.state.settled];
    prog.update(Math.min(12, s.state.settled + 1), s.state.scoutsLeft, chances());
    const chain = chainProgress(pickedCities());
    chainSlot.textContent =
      !pending && chain && chain.length > 0 && picks() < 12
        ? t('draft.chain', { type: t(key(`archetype.${chain.archetype}`)), n: chain.length })
        : '';
    if (!round) {
      playing = undefined;
      drawPreview();
      month.textContent = fmt.month(11);
      ask.textContent = '';
      eventSlot.replaceChildren();
      cardList = [];
      cardsBox.replaceChildren(
        h('p', { class: 'muted draft__complete', role: 'status' }, t('draft.complete')),
      );
      return;
    }
    month.textContent = fmt.month(round.month);
    ask.textContent = pending
      ? ''
      : t('draft.ask', {
          month: fmt.month(round.month),
          goal: t(chaseKey(s.chase, 'goal')),
        });
    if (round.event) {
      eventSlot.replaceChildren(
        h(
          'div',
          { role: 'group', 'aria-label': t('draft.eventAria') },
          chip({
            tone: 'event',
            icon: 'info',
            label: t(isInvented(round.event) ? 'draft.eventInvented' : 'draft.event', {
              name: t(key(`event.${round.event}.name`)),
              blurb: t(key(`event.${round.event}.blurb`)),
            }),
          }),
          isInvented(round.event)
            ? h('p', { class: 'muted draft__invented' }, t('draft.eventInventedNote'))
            : null,
        ),
      );
    } else {
      eventSlot.replaceChildren();
    }
    if (pending) {
      cardList = [];
      showMonth(pending);
      return;
    }
    playing = undefined;
    drawPreview();
    cardList = round.cities.map((id) => makeCard(id, round.month));
    cardsBox.replaceChildren(
      ...cardList.map((c) => c.el),
      h('p', { class: 'muted draft__strip-note' }, t('draft.stripNote')),
    );
  }

  /** The month the player just picked plays out; then they keep it or spend a second chance on it. */
  function showMonth(m: PickedRound): void {
    const city = cityById(m.cityId);
    const final = s.state.settled + 1 === 12;
    const offset = s.state.draft
      .slice(0, s.state.settled)
      .reduce((n, r) => n + (DAYS_IN_MONTH[r.month] ?? 30), 0);
    const total = (m.days.length - 1) * STAGGER_MS + FLIP_MS + FLASH_MS;
    const reduced = isReducedMotion();
    const start = performance.now();
    playing = { start, days: m.days, offset, done: reduced };

    const w = h('strong', null, '0');
    const d = h('strong', null, '0');
    const l = h('strong', null, '0');
    const stat = (n: HTMLElement, label: string, kind: string): HTMLElement =>
      h('span', { class: `month-result__stat month-result__stat--${kind}` }, n, ' ', label);
    const announce = h('p', { class: 'visually-hidden', role: 'status', 'aria-live': 'polite' });
    const heading = h(
      'h2',
      { class: 'month-result__title', tabindex: '-1' },
      t('draft.monthOf', { city: fmt.cityName(city), year: m.year }),
    );

    const nextBtn = button({
      label: t(final ? 'draft.finishYear' : 'draft.nextMonth'),
      variant: 'primary',
      full: true,
      onClick: keepMonth,
    });
    const left = chances();
    const redrawBtn = button({
      label: t('draft.redraw', { n: left }),
      variant: 'secondary',
      icon: 'refresh',
      full: true,
      onClick: redrawMonth,
    });
    const note = h(
      'p',
      { class: 'muted month-result__note' },
      left > 0 ? t('draft.redrawNote') : t('draft.noChances'),
    );
    const setEnabled = (on: boolean): void => {
      nextBtn.disabled = !on;
      redrawBtn.disabled = !on;
    };

    const panel = h(
      'section',
      { class: 'month-result', 'aria-label': t('draft.monthResult') },
      heading,
      h(
        'p',
        { class: 'month-result__score num', 'aria-hidden': 'true' },
        stat(w, t(chaseKey(s.chase, 'statWin')), 'p'),
        stat(d, t(chaseKey(s.chase, 'statDraw')), 'o'),
        stat(l, t(chaseKey(s.chase, 'statLoss')), 'l'),
      ),
      announce,
      h('div', { class: 'month-result__actions' }, nextBtn, left > 0 ? redrawBtn : null),
      note,
    );
    cardsBox.replaceChildren(panel);

    const setCounts = (now: number): void => {
      let cw = 0;
      let cd = 0;
      let cl = 0;
      m.days.forEach((type, j) => {
        if (now - start - j * STAGGER_MS < FLIP_MS) return;
        if (CHASES[s.chase].win.includes(type)) cw += 1;
        else if (CHASES[s.chase].loss.includes(type)) cl += 1;
        else cd += 1;
      });
      w.textContent = String(cw);
      d.textContent = String(cd);
      l.textContent = String(cl);
    };
    const finishPlay = (): void => {
      if (!playing || playing.done) {
        if (playing) setCounts(Infinity);
        setEnabled(true);
        return;
      }
      cancelAnimationFrame(frame);
      playing.done = true;
      drawPreview(start + total + 1);
      setCounts(Infinity);
      setEnabled(true);
      announce.textContent = t('draft.monthAnnounce', {
        city: fmt.cityName(city),
        year: m.year,
        w: m.record.w,
        d: m.record.d,
        l: m.record.l,
        win: t(chaseKey(s.chase, 'statWin')),
        draw: t(chaseKey(s.chase, 'statDraw')),
        loss: t(chaseKey(s.chase, 'statLoss')),
      });
      app.feedback.haptic(m.record.w >= 15 ? 'success' : 'light');
      nextBtn.focus();
    };

    if (reduced) {
      setCounts(Infinity);
      drawPreview(start + total + 1);
      setEnabled(true);
      announce.textContent = t('draft.monthAnnounce', {
        city: fmt.cityName(city),
        year: m.year,
        w: m.record.w,
        d: m.record.d,
        l: m.record.l,
        win: t(chaseKey(s.chase, 'statWin')),
        draw: t(chaseKey(s.chase, 'statDraw')),
        loss: t(chaseKey(s.chase, 'statLoss')),
      });
      requestAnimationFrame(() => {
        nextBtn.focus();
      });
      return;
    }
    setEnabled(false);
    heading.focus({ preventScroll: true });
    const tick = (): void => {
      const now = performance.now();
      if (now - start >= total) {
        finishPlay();
        return;
      }
      drawPreview(now);
      setCounts(now);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    // Tap the panel or the grid to skip the animation.
    const skip = (): void => {
      finishPlay();
    };
    panel.addEventListener('pointerdown', skip, { once: true });
    well.addEventListener('pointerdown', skip, { once: true });
  }

  function keepMonth(): void {
    doKeep(s);
    app.feedback.haptic('light');
    if (s.state.settled === 12) {
      doFinish(s);
      app.go('reveal');
      return;
    }
    app.transition(renderRound);
  }

  function redrawMonth(): void {
    doReroll(s);
    app.feedback.haptic('medium');
    app.feedback.sound('scout');
    app.transition(renderRound);
  }

  function onScout(id: string, card: CityCard): void {
    doScout(s, id);
    app.feedback.haptic('medium');
    app.feedback.sound('scout');
    const round = s.state.draft[s.state.settled];
    card.showScout(scoutInfo(s.data, id, round?.month ?? 0, s.chase));
    prog.update(s.state.settled + 1, s.state.scoutsLeft, chances());
    if (s.state.scoutsLeft <= 0) for (const c of cardList) c.setScoutEnabled(false);
  }

  function onPick(id: string): void {
    app.feedback.haptic('light');
    app.feedback.sound('pick');
    const combosBefore = findCombos(pickedCities()).length;
    doPick(s, id);
    const earned = findCombos(pickedCities()).slice(combosBefore);
    if (earned.length > 0) {
      showToast({
        message: earned.map((c) => t(key(`draft.comboEarned.${c.id}`))).join(' · '),
        durationMs: 3500,
      });
    }
    app.transition(renderRound);
  }

  mount(
    root,
    h(
      'main',
      { class: 'screen screen--draft' },
      h('header', { class: 'draft__head' }, prog.el, month, ask, eventSlot, chainSlot),
      well,
      h('div', { class: 'draft__spacer' }),
      cardsBox,
    ),
  );
  // The Android back gesture (and the browser Back button) asks before abandoning the run: a pick
  // shows its month at once, so there is no going back one pick. A guard entry in the history lets us
  // catch the gesture.
  const armBackGuard = (): void => {
    if ((history.state as { draftGuard?: boolean } | null)?.draftGuard !== true) {
      history.pushState({ draftGuard: true }, '');
    }
  };
  const onPop = (): void => {
    if (location.hash !== '#/draft') return;
    armBackGuard();
    confirmDialog({
      title: t('draft.leave'),
      body: t('draft.leaveBody'),
      confirmLabel: t('draft.leaveConfirm'),
      cancelLabel: t('draft.leaveStay'),
      onConfirm: () => {
        app.session = undefined;
        app.go('home');
      },
    });
  };
  armBackGuard();
  window.addEventListener('popstate', onPop);

  renderRound();
  const observer = new ResizeObserver(() => {
    drawPreview();
  });
  observer.observe(well);
  app.onLeave(() => {
    observer.disconnect();
    cancelAnimationFrame(frame);
    window.removeEventListener('popstate', onPop);
  });
}
