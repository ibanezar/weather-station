import { describe, expect, it } from 'vitest';
import type { SeedCity } from '../../src/data/types.ts';
import {
  CHAIN_LENGTH,
  chainProgress,
  combosIfPicked,
  complete,
  currentRound,
  findCombos,
  finish,
  monthRisk,
  NET_BASE,
  NET_MAX,
  netsFor,
  netsLeft,
  netsTotal,
  newRun,
  pick,
  PASSPORT_CONTINENTS,
  reroll,
  resolve,
  ROUNDS,
  start,
  type EngineData,
  type RunState,
} from '../../src/engine/index.ts';
import { data, seeds } from './helpers/data.ts';

const city = (archetype: string, continent: string): SeedCity =>
  ({ id: `${archetype}-${continent}`, archetype, continent }) as unknown as SeedCity;
const A = city('tropical', 'asia');
const B = city('desert', 'africa');

describe('combos', () => {
  it('a chain is three picks in a row of the same climate type, then it starts again', () => {
    expect(findCombos([A, A])).toEqual([]);
    expect(findCombos([A, A, A])).toEqual([{ id: 'chain', round: 2 }]);
    expect(findCombos([A, B, A, A])).toEqual([]);
    // A A A A A A: paid at the third and the sixth pick, not at the fourth and fifth
    expect(findCombos([A, A, A, A, A, A]).map((c) => c.round)).toEqual([2, 5]);
    expect(CHAIN_LENGTH).toBe(3);
  });

  it('the passport is five different continents, paid once', () => {
    const picks = ['asia', 'africa', 'europe', 'oceania', 'north-america', 'south-america'].map(
      (c, i) => city(`a${String(i)}`, c),
    );
    expect(findCombos(picks.slice(0, PASSPORT_CONTINENTS - 1))).toEqual([]);
    expect(findCombos(picks)).toEqual([{ id: 'passport', round: PASSPORT_CONTINENTS - 1 }]);
  });

  it('says which combos the next pick would complete', () => {
    expect(combosIfPicked([A, A], A)).toEqual(['chain']);
    expect(combosIfPicked([A, A], B)).toEqual([]);
    expect(combosIfPicked([], A)).toEqual([]);
  });

  it('tracks a chain in progress', () => {
    expect(chainProgress([])).toBeUndefined();
    expect(chainProgress([A])).toEqual({ archetype: 'tropical', length: 1 });
    expect(chainProgress([B, A, A])).toEqual({ archetype: 'tropical', length: 2 });
    expect(chainProgress([A, A, A])?.length).toBe(0); // paid out
    expect(chainProgress([A, A, A, A])?.length).toBe(1);
  });

  it('safety nets are one free plus one per combo, capped', () => {
    expect(netsFor(0)).toBe(NET_BASE);
    expect(netsFor(2)).toBe(3);
    expect(netsFor(99)).toBe(NET_MAX);
  });
});

describe('risk', () => {
  const world = (months: string[]): Pick<EngineData, 'world'> =>
    ({ world: { cities: { x: { d: [months] } } } }) as unknown as Pick<EngineData, 'world'>;
  const year = (wins: number): string => 'p'.repeat(wins) + 'o'.repeat(30 - wins);

  it('reads the spread of perfect days over the stored years', () => {
    const r = monthRisk(world([year(10), year(12), year(11)]), 'x', 0);
    expect(r).toMatchObject({ min: 10, max: 12, level: 'steady' });
    expect(r.mean).toBeCloseTo(11);
  });
  it('calls a wide range swingy, a middling one mixed and no perfect days none', () => {
    expect(monthRisk(world([year(0), year(20)]), 'x', 0).level).toBe('swingy');
    expect(monthRisk(world([year(3), year(12)]), 'x', 0).level).toBe('mixed');
    expect(monthRisk(world([year(0), year(0)]), 'x', 0).level).toBe('none');
  });
  it('works on the real data for every city and month', () => {
    for (const c of data.cities) {
      for (let m = 0; m < 12; m++) {
        const r = monthRisk(data, c.id, m);
        expect(r.min).toBeLessThanOrEqual(r.max);
        expect(r.max).toBeLessThanOrEqual(31);
      }
    }
  });
});

function played(seed: string): RunState {
  let s = start(newRun(seed, 'endless'), data);
  for (let i = 0; i < ROUNDS; i++)
    s = pick(s, (currentRound(s) as { cities: string[] }).cities[0] as string);
  return complete(finish(s, data));
}

describe('re-rolls', () => {
  it('a re-roll shows a different year each time, and never the first one again', () => {
    for (const seed of seeds(40)) {
      const s = start(newRun(seed, 'endless'), data);
      const round = s.draft[3];
      if (!round) throw new Error('no round');
      const id = round.cities[0];
      const years = [0, 1, 2, 3].map(
        (attempt) => resolve(data, seed, 3, id, round.month, round.event, attempt).year,
      );
      expect(new Set(years).size).toBe(4);
    }
  });

  it('is deterministic', () => {
    const s = start(newRun('x:1', 'endless'), data);
    const round = s.draft[0] as { cities: string[]; month: number; event?: string };
    const a = resolve(data, 'x:1', 0, round.cities[1] as string, round.month, round.event, 2);
    const b = resolve(data, 'x:1', 0, round.cities[1] as string, round.month, round.event, 2);
    expect(a).toEqual(b);
  });

  it('attempt 0 is the original draw, so earlier results do not change', () => {
    const s = start(newRun('x:2', 'endless'), data);
    const round = s.draft[4] as { cities: string[]; month: number; event?: string };
    const id = round.cities[2] as string;
    expect(resolve(data, 'x:2', 4, id, round.month, round.event)).toEqual(
      resolve(data, 'x:2', 4, id, round.month, round.event, 0),
    );
  });

  it('spends a net, redraws only that month and keeps the year at 365 days', () => {
    const s = played('x:3');
    const before = s.result;
    if (!before) throw new Error('no result');
    expect(netsLeft(s, data)).toBeGreaterThanOrEqual(NET_BASE);
    const after = reroll(s, data, 5);
    const result = after.result;
    if (!result) throw new Error('no result');
    expect(after.rerolls).toEqual([5]);
    expect(netsLeft(after, data)).toBe(netsLeft(s, data) - 1);
    result.rounds.forEach((r, i) => {
      if (i === 5) {
        expect(r.rerolls).toBe(1);
        expect(r.year).not.toBe(before.rounds[5]?.year);
      } else expect(r).toEqual(before.rounds[i]);
    });
    expect(result.record.w + result.record.d + result.record.l).toBe(365);
    expect(result.bestRecord).toEqual(before.bestRecord); // the benchmark does not move
  });

  it('refuses without a net, before the draft is done, or for a round that does not exist', () => {
    let s = played('x:4');
    const nets = netsTotal(s, data);
    for (let i = 0; i < nets; i++) s = reroll(s, data, i);
    expect(netsLeft(s, data)).toBe(0);
    expect(() => reroll(s, data, 0)).toThrow(/no safety nets/);
    expect(() => reroll(played('x:5'), data, 12)).toThrow(/no such round/);
    expect(() => reroll(start(newRun('x:6', 'endless'), data), data, 0)).toThrow(/cannot re-roll/);
  });

  it('rebuilding a run from its picks and re-rolls gives the same result', () => {
    const s = reroll(reroll(played('x:7'), data, 2), data, 2);
    let again = played('x:7');
    for (const r of s.rerolls) again = reroll(again, data, r);
    expect(again.result).toEqual(s.result);
  });
});
