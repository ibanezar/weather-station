// Draft generation (SPEC 1.6 and 1.7). Deterministic for a given seed.
import type { SeedCity } from '../data/types.ts';
import { eventAffects, getCity } from './lookup.ts';
import { makeRng, randInt, shuffle } from './rng.ts';
import type { DraftRound, EngineData } from './types.ts';

export const ROUNDS = 12;
export const CITIES_PER_ROUND = 3;
/** About half the months carry an event. */
export const EVENT_ROUNDS = 6;
/** The same event is used at most this often in one run, when alternatives exist. */
export const MAX_PER_EVENT = 2;

/** Three different archetypes and at least two different continents. */
export function validTriple(a: SeedCity, b: SeedCity, c: SeedCity): boolean {
  const archetypes = new Set([a.archetype, b.archetype, c.archetype]);
  const continents = new Set([a.continent, b.continent, c.continent]);
  return archetypes.size === 3 && continents.size >= 2;
}

function findTriple(order: readonly SeedCity[]): [SeedCity, SeedCity, SeedCity] | undefined {
  for (let i = 0; i < order.length; i++) {
    const a = order[i] as SeedCity;
    for (let j = i + 1; j < order.length; j++) {
      const b = order[j] as SeedCity;
      if (b.archetype === a.archetype) continue;
      for (let k = j + 1; k < order.length; k++) {
        const c = order[k] as SeedCity;
        if (validTriple(a, b, c)) return [a, b, c];
      }
    }
  }
  return undefined;
}

export function generateDraft(
  seed: string,
  data: Pick<EngineData, 'cities' | 'events'>,
): DraftRound[] {
  const used = new Set<string>();
  const rounds: DraftRound[] = [];

  for (let r = 0; r < ROUNDS; r++) {
    const rng = makeRng(seed, 'draft', r);
    const order = shuffle(
      data.cities.filter((c) => !used.has(c.id)),
      rng,
    );
    const triple = findTriple(order);
    if (!triple) throw new Error(`draft: no valid cities left for round ${String(r)}`);
    for (const c of triple) used.add(c.id);
    rounds.push({ month: r, cities: [triple[0].id, triple[1].id, triple[2].id] });
  }

  // Events are decided after the cities, so each one can be checked against what is on offer.
  const eventMonths = new Set(
    shuffle(
      Array.from({ length: ROUNDS }, (_, i) => i),
      makeRng(seed, 'events'),
    ).slice(0, EVENT_ROUNDS),
  );
  const usage = new Map<string, number>();
  for (const round of rounds) {
    if (!eventMonths.has(round.month)) continue;
    const cities = round.cities.map((id) => getCity(data, id));
    const affecting = data.events.filter((e) => cities.some((c) => eventAffects(e, c)));
    const fresh = affecting.filter((e) => (usage.get(e.id) ?? 0) < MAX_PER_EVENT);
    const pool = fresh.length > 0 ? fresh : affecting;
    if (pool.length === 0) continue;
    const event = pool[
      randInt(makeRng(seed, 'event', round.month), pool.length)
    ] as (typeof pool)[number];
    round.event = event.id;
    usage.set(event.id, (usage.get(event.id) ?? 0) + 1);
  }
  return rounds;
}

/** Returns a list of rule violations (empty when the draft follows SPEC 1.6 and 1.7). */
export function validateDraft(
  draft: readonly DraftRound[],
  data: Pick<EngineData, 'cities' | 'events'>,
): string[] {
  const errors: string[] = [];
  if (draft.length !== ROUNDS)
    errors.push(`expected ${String(ROUNDS)} rounds, got ${String(draft.length)}`);
  const seen = new Set<string>();
  draft.forEach((round, r) => {
    if (round.month !== r) errors.push(`round ${String(r)} has month ${String(round.month)}`);
    const cities = round.cities.map((id) => getCity(data, id));
    for (const c of cities) {
      if (seen.has(c.id)) errors.push(`round ${String(r)}: ${c.id} repeats`);
      seen.add(c.id);
    }
    if (new Set(cities.map((c) => c.archetype)).size !== 3) {
      errors.push(`round ${String(r)}: archetypes are not all different`);
    }
    if (new Set(cities.map((c) => c.continent)).size < 2) {
      errors.push(`round ${String(r)}: fewer than two continents`);
    }
    if (round.event !== undefined) {
      const event = data.events.find((e) => e.id === round.event);
      if (!event) errors.push(`round ${String(r)}: unknown event ${round.event}`);
      else if (!cities.some((c) => eventAffects(event, c))) {
        errors.push(`round ${String(r)}: event ${event.id} affects none of the cities`);
      }
    }
  });
  return errors;
}
