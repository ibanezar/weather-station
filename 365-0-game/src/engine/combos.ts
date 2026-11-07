// Combos: picking in patterns earns safety nets (re-rolls), so the draft is more than twelve separate choices.
import type { SeedCity } from '../data/types.ts';

export type ComboId = 'chain' | 'passport';

export interface Combo {
  id: ComboId;
  /** The round (0 to 11) whose pick completed the combo. */
  round: number;
}

/** Every run starts with this many safety nets. */
export const NET_BASE = 1;
export const NET_MAX = 4;
/** Chain: this many picks in a row of the same climate type. */
export const CHAIN_LENGTH = 3;
/** Passport: picks from this many different continents. */
export const PASSPORT_CONTINENTS = 5;

/** Combos completed by a list of picks, in the order they were completed. */
export function findCombos(picks: readonly SeedCity[]): Combo[] {
  const out: Combo[] = [];
  const continents = new Set<string>();
  let passport = false;
  let streak = 0;
  picks.forEach((city, round) => {
    const previous = picks[round - 1];
    streak = previous?.archetype === city.archetype ? streak + 1 : 1;
    if (streak === CHAIN_LENGTH) {
      out.push({ id: 'chain', round });
      streak = 0; // a new chain needs three fresh picks
    }
    continents.add(city.continent);
    if (!passport && continents.size >= PASSPORT_CONTINENTS) {
      passport = true;
      out.push({ id: 'passport', round });
    }
  });
  return out;
}

/** Combos that picking `candidate` next would complete (for the badge on a card). */
export function combosIfPicked(picks: readonly SeedCity[], candidate: SeedCity): ComboId[] {
  const before = findCombos(picks).length;
  return findCombos([...picks, candidate])
    .slice(before)
    .map((c) => c.id);
}

/** Where the current chain stands: how many of the last picks share the latest climate type. */
export function chainProgress(
  picks: readonly SeedCity[],
): { archetype: string; length: number } | undefined {
  const last = picks[picks.length - 1];
  if (!last) return undefined;
  let length = 0;
  for (let i = picks.length - 1; i >= 0 && picks[i]?.archetype === last.archetype; i--) length += 1;
  // Whole chains already paid out do not count towards the next one.
  return { archetype: last.archetype, length: length % CHAIN_LENGTH };
}

export function netsFor(combos: number): number {
  return Math.min(NET_MAX, NET_BASE + combos);
}
