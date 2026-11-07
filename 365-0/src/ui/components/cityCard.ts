import type { Archetype } from '../../data/types.ts';
import { h } from '../dom.ts';
import { icon } from '../icons/index.ts';
import { steps } from './steps.ts';

export interface ScoutInfo {
  perfect: number;
  bad: number;
}

export interface CityCardOptions {
  name: string;
  country: string;
  /** Already formatted for the player's unit, e.g. "11°". */
  temperature: string;
  archetype: Archetype;
  archetypeLabel: string;
  /** The action part of the pick button's name, e.g. "Pick this city". */
  pickAction: string;
  scoutLabel: string;
  /** Accessible name of the Scout button; must contain scoutLabel, e.g. "Scout Reykjavik". */
  scoutFullLabel: string;
  scoutedLabel: string;
  perfectLabel: string;
  badLabel: string;
  /** Text for a bucket value, e.g. "3 of 5". */
  stepText: (bucket: number) => string;
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

/**
 * A city card: one real button that picks the city, plus a separate Scout button on top of it.
 * The two are siblings, because a button cannot contain another button.
 */
export function cityCard(o: CityCardOptions): CityCard {
  const back = h('div', { class: 'city-card__face city-card__back', 'aria-hidden': 'true' });
  const front = h(
    'div',
    { class: 'city-card__face city-card__front' },
    h(
      'div',
      { class: 'city-card__head' },
      h(
        'div',
        { class: 'city-card__title' },
        h('span', { class: 'city-card__name' }, o.name),
        ' ', // real whitespace, so the visible text reads "Name Country Temperature"
        h('span', { class: 'city-card__country muted' }, o.country),
      ),
      ' ',
      h('span', { class: 'city-card__temp num' }, o.temperature),
    ),
    h(
      'div',
      { class: 'city-card__foot' },
      h(
        'span',
        { class: 'city-card__archetype', title: o.archetypeLabel },
        icon(o.archetype, { label: o.archetypeLabel }),
      ),
    ),
  );

  // The name starts with the visible text (name, country, temperature) so it contains what is shown.
  const baseName = `${o.name}, ${o.country}, ${o.temperature}, ${o.archetypeLabel}. ${o.pickAction}.`;
  const pick = h(
    'button',
    { type: 'button', class: 'city-card__pick', 'aria-label': baseName, onClick: o.onPick },
    h('span', { class: 'city-card__inner' }, front, back),
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

  return {
    el,
    showScout(info) {
      back.replaceChildren(
        h(
          'div',
          { class: 'city-card__scouted' },
          h('span', { class: 'city-card__name' }, o.name),
          h(
            'span',
            { class: 'city-card__scouted-tag muted' },
            icon('check', { size: 18 }),
            o.scoutedLabel,
          ),
        ),
        h(
          'div',
          { class: 'city-card__bar' },
          h('span', { class: 'city-card__bar-label' }, o.perfectLabel),
          steps(info.perfect, o.perfectLabel, o.stepText(info.perfect), 'perfect'),
        ),
        h(
          'div',
          { class: 'city-card__bar' },
          h('span', { class: 'city-card__bar-label' }, o.badLabel),
          steps(info.bad, o.badLabel, o.stepText(info.bad), 'bad'),
        ),
      );
      // Screen readers get the scouted values as text on the pick button; the faces are visual.
      pick.setAttribute(
        'aria-label',
        `${baseName} ${o.perfectLabel}: ${o.stepText(info.perfect)}. ${o.badLabel}: ${o.stepText(info.bad)}.`,
      );
      // The Scout button is about to become hidden: keep keyboard focus on the card.
      if (document.activeElement === scoutBtn) pick.focus();
      el.dataset['flipped'] = 'true';
      scoutBtn.disabled = true;
    },
    setScoutEnabled(enabled) {
      if (el.dataset['flipped'] !== 'true') scoutBtn.disabled = !enabled;
    },
  };
}
