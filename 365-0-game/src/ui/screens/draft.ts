import type { App } from '../../app/app.ts';
import { cities } from '../../app/data.ts';
import { doFinish, doPick, doScout, doStepBack, doUndo, type Session } from '../../app/session.ts';
import { DAYS_IN_MONTH, type SeedCity } from '../../data/types.ts';
import { chainProgress, combosIfPicked, findCombos } from '../../engine/combos.ts';
import { monthRisk } from '../../engine/risk.ts';
import { currentRound, isScouted, netsTotal, scoutInfo } from '../../engine/run.ts';
import type { DayType } from '../../engine/thresholds.ts';
import type { MessageKey } from '../../i18n/index.ts';
import { drawGrid, resolvePalette, type GridColumn } from '../canvas/grid.ts';
import { chip } from '../components/chip.ts';
import { cityCard, type CityCard } from '../components/cityCard.ts';
import { confirmDialog } from '../components/confirm.ts';
import { progress } from '../components/progress.ts';
import { showToast } from '../components/toast.ts';
import { h, mount } from '../dom.ts';
import { isPatternMode, isReducedMotion } from '../settings.ts';

const FINISH_DELAY_MS = 1200;
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
  let finishTimer: ReturnType<typeof setTimeout> | undefined;
  let locked = false;
  let fade: { column: number; start: number } | undefined;
  let frame = 0;

  const picks = (): number => s.state.picks.length;
  const pickedCities = (): SeedCity[] => s.state.picks.map(cityById);
  const chances = (): number => netsTotal(s.state, s.data) - s.state.rerolls.length;

  function drawPreview(): void {
    const columns: GridColumn[] = Array.from({ length: 12 }, (_, m) =>
      m < picks()
        ? { days: Array<DayType>(DAYS_IN_MONTH[m] ?? 30).fill('o'), claimed: true }
        : { days: null },
    );
    const claimedAlpha = (col: number): number => {
      if (!fade || fade.column !== col) return 1;
      return Math.min(1, (performance.now() - fade.start) / 160);
    };
    drawGrid(canvas, columns, resolvePalette(well), {
      pattern: isPatternMode(),
      compact: true,
      claimedAlpha,
    });
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', t('draft.gridAlt', { months: picks() }));
    labels.replaceChildren(
      ...columns.map((_, m) => {
        const id = s.state.picks[m];
        return h('span', null, id ? fmt.abbreviation(cityById(id)) : fmt.month(m).charAt(0));
      }),
    );
  }

  function animatePick(column: number): void {
    if (isReducedMotion()) {
      drawPreview();
      return;
    }
    fade = { column, start: performance.now() };
    const tick = (): void => {
      drawPreview();
      if (performance.now() - (fade?.start ?? 0) < 170) frame = requestAnimationFrame(tick);
    };
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(tick);
  }

  function makeCard(id: string, monthIndex: number): CityCard {
    const city = cityById(id);
    const name = fmt.cityName(city);
    const risk = monthRisk(s.data, id, monthIndex);
    const combos = combosIfPicked(pickedCities(), city);
    const card = cityCard({
      risk: {
        level: risk.level,
        label: t(key(`draft.risk.${risk.level}`)),
        detail: risk.level === 'none' ? '' : t('draft.riskRange', { min: risk.min, max: risk.max }),
      },
      ...(combos.length > 0
        ? { combo: combos.map((c) => t(key(`draft.combo.${c}`))).join(' · ') }
        : {}),
      name,
      country: fmt.country(city.country),
      temperature: fmt.temperature(world.cities[id]?.t[monthIndex] ?? 0),
      archetype: city.archetype,
      archetypeLabel: t(key(`archetype.${city.archetype}`)),
      pickAction: t('draft.pick'),
      scoutLabel: t('draft.scout'),
      scoutFullLabel: t('draft.scoutCity', { city: name }),
      scoutedLabel: t('draft.scouted'),
      perfectLabel: t('draft.perfectDays'),
      badLabel: t('draft.badDays'),
      stepText: (b) => t('draft.stepOf', { n: b + 1 }),
      onPick: () => {
        onPick(id);
      },
      onScout: () => {
        onScout(id, card);
      },
    });
    if (isScouted(s.state, id)) card.showScout(scoutInfo(s.data, id, monthIndex));
    if (s.state.scoutsLeft <= 0) card.setScoutEnabled(false);
    return card;
  }

  function renderRound(): void {
    const round = currentRound(s.state);
    prog.update(Math.min(12, picks() + 1), s.state.scoutsLeft, chances());
    drawPreview();
    const chain = chainProgress(pickedCities());
    chainSlot.textContent =
      chain && chain.length > 0 && picks() < 12
        ? t('draft.chain', { type: t(key(`archetype.${chain.archetype}`)), n: chain.length })
        : '';
    if (!round) {
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
    ask.textContent = t('draft.ask', { month: fmt.month(round.month) });
    if (round.event) {
      eventSlot.replaceChildren(
        h(
          'div',
          { role: 'group', 'aria-label': t('draft.eventAria') },
          chip({
            tone: 'event',
            icon: 'info',
            label: t('draft.event', {
              name: t(key(`event.${round.event}.name`)),
              blurb: t(key(`event.${round.event}.blurb`)),
            }),
          }),
        ),
      );
    } else {
      eventSlot.replaceChildren();
    }
    cardList = round.cities.map((id) => makeCard(id, round.month));
    cardsBox.replaceChildren(...cardList.map((c) => c.el));
  }

  function onScout(id: string, card: CityCard): void {
    if (locked) return;
    doScout(s, id);
    app.feedback.haptic('medium');
    app.feedback.sound('scout');
    const round = currentRound(s.state);
    card.showScout(scoutInfo(s.data, id, round?.month ?? 0));
    prog.update(picks() + 1, s.state.scoutsLeft, chances());
    if (s.state.scoutsLeft <= 0) for (const c of cardList) c.setScoutEnabled(false);
  }

  function undoPick(): void {
    clearTimeout(finishTimer);
    finishTimer = undefined;
    doUndo(s);
    locked = false;
    app.transition(renderRound);
  }

  function onPick(id: string): void {
    if (locked) return;
    app.feedback.haptic('light');
    app.feedback.sound('pick');
    const combosBefore = findCombos(pickedCities()).length;
    doPick(s, id);
    const placed = picks() - 1;
    const earned = findCombos(pickedCities()).slice(combosBefore);
    showToast({
      message: [
        t('draft.picked', { city: fmt.cityName(cityById(id)) }),
        ...earned.map((c) => t(key(`draft.comboEarned.${c.id}`))),
      ].join(' '),
      actionLabel: t('draft.undo'),
      onAction: undoPick,
      durationMs: FINISH_DELAY_MS,
    });
    if (picks() === 12) {
      locked = true;
      app.transition(renderRound);
      finishTimer = setTimeout(() => {
        doFinish(s);
        app.go('reveal');
      }, FINISH_DELAY_MS);
    } else {
      app.transition(renderRound);
    }
    animatePick(placed);
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
  // The Android back gesture (and the browser Back button): step back through the picks, and ask
  // before abandoning a run with no picks. A guard entry in the history lets us catch the gesture.
  const armBackGuard = (): void => {
    if ((history.state as { draftGuard?: boolean } | null)?.draftGuard !== true) {
      history.pushState({ draftGuard: true }, '');
    }
  };
  const onPop = (): void => {
    if (location.hash !== '#/draft') return;
    armBackGuard();
    if (locked) {
      undoPick(); // back during the two seconds before the reveal takes the last pick back
    } else if (picks() > 0) {
      doStepBack(s);
      app.transition(renderRound);
    } else {
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
    }
  };
  armBackGuard();
  window.addEventListener('popstate', onPop);

  renderRound();
  const observer = new ResizeObserver(drawPreview);
  observer.observe(well);
  app.onLeave(() => {
    observer.disconnect();
    cancelAnimationFrame(frame);
    clearTimeout(finishTimer);
    window.removeEventListener('popstate', onPop);
  });
}
