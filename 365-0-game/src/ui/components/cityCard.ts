import type { Archetype } from '../../data/types.ts';
import { h } from '../dom.ts';
import { icon } from '../icons/index.ts';
import { isReducedMotion } from '../settings.ts';
import { cssTimeToMs } from '../time.ts';
import { steps } from './steps.ts';

export interface ScoutInfo {
  /** Bucket (0 to 4) of the winning days. */
  win: number;
  /** Bucket (0 to 4) of the losing days. */
  loss: number;
}

export interface CityCardOptions {
  name: string;
  country: string;
  /** Already formatted for the player's unit, e.g. "11°". */
  temperature: string;
  archetype: Archetype;
  archetypeLabel: string;
  /** Spoken before the card text, e.g. "Pick this city". Visually hidden. */
  pickAction: string;
  scoutLabel: string;
  /** Accessible name of the Scout button; must contain scoutLabel, e.g. "Scout Reykjavik". */
  scoutFullLabel: string;
  scoutedLabel: string;
  winLabel: string;
  lossLabel: string;
  /** Text for a bucket value, e.g. "3 of 5". */
  stepText: (bucket: number) => string;
  /** Free information on every card: how much this month varies from year to year. */
  risk?: { level: string; label: string; detail: string };
  /** Set when picking this city completes a combo, e.g. "Chain: +1 second chance". */
  combo?: string;
  onPick: () => void;
  onScout: () => void;
}

export interface CityCard {
  el: HTMLElement;
  /** Flip the card to show the scouted bars. */
  showScout: (info: ScoutInfo) => void;
  /** Disable the Scout button (no scouts left). */
  setScoutEnabled: (enabled: boolean) => void;
}

/** Duration of the flip in ms, from the motion token (0 when motion is reduced). */
function flipMs(): number {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--dur-flip');
  return isReducedMotion() ? 0 : cssTimeToMs(raw);
}

/**
 * A city card: one real button that picks the city, plus a separate Scout button on top of it.
 * The two are siblings, because a button cannot contain another button. The pick button has no
 * aria-label: its name is its visible text, so what is read out is always what is shown.
 */
export function cityCard(o: CityCardOptions): CityCard {
  const front = h(
    'span',
    { class: 'city-card__face city-card__front' },
    h(
      'span',
      { class: 'city-card__head' },
      h(
        'span',
        { class: 'city-card__title' },
        h('span', { class: 'city-card__name' }, o.name),
        ' ', // real whitespace, so the visible text reads "Name Country Temperature"
        h('span', { class: 'city-card__country muted' }, o.country),
      ),
      ' ',
      h('span', { class: 'city-card__temp num' }, o.temperature),
    ),
    h(
      'span',
      { class: 'city-card__foot' },
      h('span', { class: 'city-card__archetype' }, icon(o.archetype, { label: o.archetypeLabel })),
      o.risk
        ? h(
            'span',
            { class: 'city-card__risk', 'data-level': o.risk.level },
            h('strong', null, o.risk.label),
            ' ',
            o.risk.detail
              ? h('span', { class: 'city-card__risk-detail muted' }, o.risk.detail)
              : null,
          )
        : null,
    ),
    o.combo ? h('span', { class: 'city-card__combo' }, icon('check', { size: 16 }), o.combo) : null,
  );
  const inner = h('span', { class: 'city-card__inner' }, front);
  const pick = h(
    'button',
    { type: 'button', class: 'city-card__pick', onClick: o.onPick },
    h('span', { class: 'visually-hidden' }, `${o.pickAction}. `),
    inner,
  );
  const scoutBtn = h(
    'button',
    {
      type: 'button',
      class: 'city-card__scout',
      'aria-label': o.scoutFullLabel,
      onClick: o.onScout,
    },
    icon('scout', { size: 20 }),
    h('span', null, o.scoutLabel),
  );
  const el = h('div', { class: 'city-card', 'data-flipped': 'false' }, pick, scoutBtn);

  function backFace(info: ScoutInfo): HTMLElement {
    return h(
      'span',
      { class: 'city-card__face city-card__back' },
      h(
        'span',
        { class: 'city-card__scouted' },
        h('span', { class: 'city-card__name' }, o.name),
        ' ',
        h(
          'span',
          { class: 'city-card__scouted-tag muted' },
          icon('check', { size: 18 }),
          o.scoutedLabel,
        ),
      ),
      h(
        'span',
        { class: 'city-card__bar' },
        h('span', { class: 'city-card__bar-label' }, o.winLabel),
        ' ',
        steps(info.win, o.stepText(info.win), 'perfect'),
      ),
      h(
        'span',
        { class: 'city-card__bar' },
        h('span', { class: 'city-card__bar-label' }, o.lossLabel),
        ' ',
        steps(info.loss, o.stepText(info.loss), 'bad'),
      ),
    );
  }

  return {
    el,
    showScout(info) {
      // The Scout button is about to become hidden: keep keyboard focus on the card.
      if (document.activeElement === scoutBtn) pick.focus();
      el.dataset['flipped'] = 'true';
      scoutBtn.disabled = true;
      const back = backFace(info);
      const half = flipMs() / 2;
      if (half <= 0 || typeof inner.animate !== 'function') {
        inner.replaceChildren(back);
        return;
      }
      // A flip in two halves: turn away, swap the face, turn back.
      inner
        .animate([{ transform: 'rotateY(0deg)' }, { transform: 'rotateY(90deg)' }], {
          duration: half,
          easing: 'ease-in',
        })
        .finished.then(() => {
          inner.replaceChildren(back);
          inner.animate([{ transform: 'rotateY(-90deg)' }, { transform: 'rotateY(0deg)' }], {
            duration: half,
            easing: 'ease-out',
          });
        })
        .catch(() => {
          inner.replaceChildren(back);
        });
    },
    setScoutEnabled(enabled) {
      if (el.dataset['flipped'] !== 'true') scoutBtn.disabled = !enabled;
    },
  };
}
