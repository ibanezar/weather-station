import { describe, expect, it } from 'vitest';
import {
  bestPossible,
  buildShareText,
  complete,
  currentRound,
  dailySeed,
  DAY_TYPE_CHARS,
  dominantType,
  endlessSeed,
  eventAffects,
  finish,
  generateDraft,
  getCity,
  gradeFor,
  GRADE_TIERS,
  isScouted,
  makeRng,
  monthSquares,
  newRun,
  pick,
  ratio,
  record,
  resolve,
  ROUNDS,
  scout,
  scoutInfo,
  SCOUTS_PER_RUN,
  shareImageModel,
  SQUARES,
  start,
  undo,
  validateDraft,
  type DayType,
  type EngineData,
  type RunState,
  type WorldEvent,
} from '../../src/engine/index.ts';
import { data, seeds } from './helpers/data.ts';

/** Play a whole run, choosing the option at `choose(round)` (0, 1 or 2) each round. */
function play(seed: string, choose: (round: number) => number): RunState {
  let s = start(newRun(seed, 'endless'), data);
  for (let i = 0; i < ROUNDS; i++) {
    const round = currentRound(s);
    if (!round) throw new Error('no round');
    s = pick(s, round.cities[choose(i)] as string);
  }
  return finish(s, data);
}

describe('rng', () => {
  it('is stable for the same parts and different for different parts', () => {
    const a = makeRng('s', 1, 'x');
    const b = makeRng('s', 1, 'x');
    for (let i = 0; i < 20; i++) expect(a()).toBe(b());
    expect(makeRng('s', 1, 'x')()).not.toBe(makeRng('s', 2, 'x')());
    expect(makeRng('ab', 'c')()).not.toBe(makeRng('a', 'bc')());
  });

  it('returns floats in [0, 1) that are roughly uniform', () => {
    const r = makeRng('uniform');
    let sum = 0;
    for (let i = 0; i < 20000; i++) {
      const x = r();
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThan(1);
      sum += x;
    }
    expect(sum / 20000).toBeCloseTo(0.5, 1);
  });
});

describe('determinism', () => {
  it('gives the same draft, outcomes and record for the same seed, across 1,000 seeds', () => {
    for (const seed of seeds(1000)) {
      const d1 = generateDraft(seed, data);
      const d2 = generateDraft(seed, data);
      expect(d2).toEqual(d1);
      const a = play(seed, (i) => i % 3);
      const b = play(seed, (i) => i % 3);
      expect(b.result).toEqual(a.result);
      expect(b.best).toEqual(a.best);
    }
  });

  it('builds daily and endless seeds as specified', () => {
    expect(dailySeed('2026-11-06')).toBe('365-0:daily:2026-11-06');
    expect(endlessSeed('abc')).toBe('365-0:endless:abc');
    expect(() => dailySeed('6.11.2026')).toThrow();
  });
});

describe('independence of rounds', () => {
  it('changing one pick never changes the outcome of any other round', () => {
    for (const seed of seeds(200, 'indep')) {
      const base = play(seed, () => 0).result;
      expect(base).toBeDefined();
      for (let k = 0; k < ROUNDS; k += 3) {
        const changed = play(seed, (i) => (i === k ? 2 : 0)).result;
        base?.rounds.forEach((r, i) => {
          if (i === k) return;
          expect(changed?.rounds[i]).toEqual(r);
        });
      }
    }
  });
});

describe('records', () => {
  it('always sum to 365', () => {
    for (const seed of seeds(300, 'sum')) {
      for (const choose of [() => 0, () => 1, (i: number) => (i * 7) % 3]) {
        const r = play(seed, choose).result;
        expect(r).toBeDefined();
        if (!r) continue;
        expect(r.record.w + r.record.d + r.record.l).toBe(365);
        expect(r.bestRecord.w + r.bestRecord.d + r.bestRecord.l).toBe(365);
        for (const round of r.rounds)
          expect(round.days.length).toBe(
            [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][round.month],
          );
      }
    }
  });

  it('counts wins, draws and losses', () => {
    const days = 'poorsshffpo'.split('') as DayType[];
    expect(record(days)).toEqual({ w: 2, d: 3, l: 6 });
  });
});

describe('best possible', () => {
  it('is at least as good as any achievable record, checked by brute force on 200 seeds', () => {
    for (const seed of seeds(200, 'brute')) {
      const draft = generateDraft(seed, data);
      const best = bestPossible(data, seed, draft);
      // Every combination of the 3 options in 12 rounds: 3^12 = 531,441 per seed.
      const w = best.rounds.map((r) => r.options.map((o) => o.record.w));
      const l = best.rounds.map((r) => r.options.map((o) => o.record.l));
      let maxW = -1;
      let minLAtMaxW = Infinity;
      const walk = (round: number, sw: number, sl: number): void => {
        if (round === ROUNDS) {
          if (sw > maxW || (sw === maxW && sl < minLAtMaxW)) {
            maxW = sw;
            minLAtMaxW = sl;
          }
          return;
        }
        for (let o = 0; o < 3; o++)
          walk(round + 1, sw + (w[round]?.[o] ?? 0), sl + (l[round]?.[o] ?? 0));
      };
      walk(0, 0, 0);
      expect(best.record.w).toBe(maxW);
      expect(best.record.l).toBe(minLAtMaxW);
    }
  }, 120_000);

  it('can never be beaten by the player, and picking the best every round matches it', () => {
    for (const seed of seeds(300, 'never')) {
      for (const choose of [() => 0, () => 1, () => 2]) {
        const r = play(seed, choose).result;
        expect(r?.record.w).toBeLessThanOrEqual(r?.bestRecord.w ?? 0);
        expect(r?.ratio).toBeLessThanOrEqual(1);
      }
      const draft = generateDraft(seed, data);
      const best = bestPossible(data, seed, draft);
      const perfect = play(seed, (i) => {
        const id = best.rounds[i]?.best.cityId;
        return (draft[i]?.cities as string[]).indexOf(id ?? '');
      }).result;
      expect(perfect?.record).toEqual(best.record);
      expect(perfect?.grade).toBe('perfect-forecast');
    }
  });
});

describe('draft rules', () => {
  it('hold across 5,000 seeds', () => {
    let eventRounds = 0;
    for (const seed of seeds(5000, 'rules')) {
      const draft = generateDraft(seed, data);
      expect(validateDraft(draft, data), seed).toEqual([]);
      eventRounds += draft.filter((r) => r.event !== undefined).length;
    }
    // About six of the twelve months carry an event.
    const mean = eventRounds / 5000;
    expect(mean).toBeGreaterThan(5);
    expect(mean).toBeLessThanOrEqual(6);
  });

  it('uses all twelve months in order and 36 different cities', () => {
    const draft = generateDraft('shape', data);
    expect(draft.map((r) => r.month)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]);
    expect(new Set(draft.flatMap((r) => r.cities)).size).toBe(36);
  });

  it('validateDraft catches a repeated city and a weak round', () => {
    const draft = generateDraft('bad', data).map((r) => ({
      ...r,
      cities: [...r.cities] as typeof r.cities,
    }));
    const first = draft[0];
    const second = draft[1];
    if (!first || !second) throw new Error('missing rounds');
    second.cities[0] = first.cities[0];
    expect(validateDraft(draft, data).some((e) => e.includes('repeats'))).toBe(true);
  });
});

describe('events', () => {
  const synthetic = (days: string): EngineData => ({
    cities: data.cities,
    events: data.events,
    world: {
      v: 1,
      years: [2000],
      cities: Object.fromEntries(
        data.cities.map((c) => [
          c.id,
          { t: [], sp: [], sb: [], d: Array.from({ length: 12 }, () => [days]) },
        ]),
      ),
    },
  });

  it('never produce an unknown day type on the real data', () => {
    const allowed = new Set<string>(DAY_TYPE_CHARS);
    for (const seed of seeds(300, 'ev')) {
      for (const round of generateDraft(seed, data)) {
        if (!round.event) continue;
        for (const id of round.cities) {
          const o = resolve(data, seed, round.month, id, round.month, round.event);
          for (const t of o.days) expect(allowed.has(t)).toBe(true);
        }
      }
    }
  });

  it.each(data.events)(
    '$id converts matching days with its stated probability',
    (event: WorldEvent) => {
      const city = data.cities.find((c) => eventAffects(event, c));
      if (!city) throw new Error(`no city for ${event.id}`);
      const transform = event.transforms[0];
      if (!transform) throw new Error('no transform');
      const n = 20000;
      const source = transform.from[0] as DayType;
      const o = resolve(synthetic(source.repeat(n)), 's', 0, city.id, 0, event.id);
      const converted = o.days.filter((t) => t === transform.to).length / n;
      expect(Math.abs(converted - transform.p)).toBeLessThan(0.02);
      expect(o.days.every((t) => t === source || t === transform.to)).toBe(true);
    },
  );

  it('leave days of other types and unaffected cities alone', () => {
    const heatwave = data.events.find((e) => e.id === 'heatwave') as WorldEvent;
    const polar = data.cities.find((c) => c.archetype === 'polar' && !eventAffects(heatwave, c));
    if (!polar) throw new Error('no unaffected city');
    const rainy = resolve(synthetic('r'.repeat(5000)), 's', 0, polar.id, 0, 'heatwave');
    expect(rainy.days.every((t) => t === 'r')).toBe(true);
    const affected = data.cities.find((c) => eventAffects(heatwave, c)) as { id: string };
    const stillRain = resolve(synthetic('r'.repeat(5000)), 's', 0, affected.id, 0, 'heatwave');
    expect(stillRain.days.every((t) => t === 'r')).toBe(true); // heatwave only converts ok and perfect
    const unaffected = resolve(synthetic('o'.repeat(5000)), 's', 0, polar.id, 0, 'heatwave');
    expect(unaffected.days.every((t) => t === 'o')).toBe(true);
  });

  it('exposes only cities whose tags match', () => {
    const clear = data.events.find((e) => e.id === 'clear-spell') as WorldEvent;
    expect(data.cities.every((c) => eventAffects(clear, c))).toBe(true);
    const vortex = data.events.find((e) => e.id === 'polar-vortex') as WorldEvent;
    expect(eventAffects(vortex, getCity(data, 'dubai'))).toBe(false);
    expect(eventAffects(vortex, getCity(data, 'moscow'))).toBe(true);
  });
});

describe('run state machine', () => {
  const fresh = (): RunState => start(newRun('sm', 'endless'), data);

  it('moves idle, drafting, revealing, done', () => {
    const idle = newRun('sm', 'daily');
    expect(idle.phase).toBe('idle');
    expect(() => pick(idle, 'x')).toThrow();
    const s = fresh();
    expect(s.phase).toBe('drafting');
    expect(s.best?.record.w).toBeGreaterThan(0);
    const done = complete(play('sm', () => 0));
    expect(done.phase).toBe('done');
    expect(() => complete(done)).toThrow();
  });

  it('rejects a city that is not on offer, and finishing early', () => {
    const s = fresh();
    expect(() => pick(s, 'not-a-city')).toThrow();
    expect(() => finish(s, data)).toThrow();
  });

  it('undoes only the most recent pick', () => {
    let s = fresh();
    const first = currentRound(s)?.cities[0] as string;
    s = pick(s, first);
    expect(s.picks).toEqual([first]);
    s = undo(s);
    expect(s.picks).toEqual([]);
    expect(() => undo(s)).toThrow();
    s = pick(s, first);
    s = pick(s, currentRound(s)?.cities[1] as string);
    s = undo(s);
    expect(s.picks).toEqual([first]);
    expect(() => undo(s)).toThrow();
  });

  it('has three scouts, charges once per card and refuses a fourth', () => {
    let s = fresh();
    expect(s.scoutsLeft).toBe(SCOUTS_PER_RUN);
    const [a, b, c] = currentRound(s)?.cities as [string, string, string];
    s = scout(s, a);
    expect(isScouted(s, a)).toBe(true);
    expect(scout(s, a)).toBe(s); // scouting the same card again is free
    s = scout(s, b);
    s = scout(s, c);
    expect(s.scoutsLeft).toBe(0);
    s = pick(s, a);
    const next = currentRound(s)?.cities[0] as string;
    expect(() => scout(s, next)).toThrow(/no scouts left/);
  });

  it('reports bucketed scout values from the world data', () => {
    const info = scoutInfo(data, 'dubai', 6);
    expect(Number.isInteger(info.perfect) && info.perfect >= 0 && info.perfect <= 4).toBe(true);
    expect(Number.isInteger(info.bad) && info.bad >= 0 && info.bad <= 4).toBe(true);
  });
});

describe('grades', () => {
  it('map ratios to the tiers in SPEC 1.8', () => {
    expect(gradeFor(0)).toBe('stormbound');
    expect(gradeFor(0.549)).toBe('stormbound');
    expect(gradeFor(0.55)).toBe('umbrella-carrier');
    expect(gradeFor(0.65)).toBe('drizzle-dodger');
    expect(gradeFor(0.75)).toBe('fair-weather-friend');
    expect(gradeFor(0.85)).toBe('sun-chaser');
    expect(gradeFor(0.93)).toBe('climate-sage');
    expect(gradeFor(0.99)).toBe('perfect-forecast');
    expect(gradeFor(1)).toBe('perfect-forecast');
    expect(GRADE_TIERS.map((t) => t.min)).toEqual([0.99, 0.93, 0.85, 0.75, 0.65, 0.55, 0]);
  });

  it('computes the ratio and survives a best of zero', () => {
    expect(ratio(50, 100)).toBe(0.5);
    expect(ratio(0, 0)).toBe(1);
  });
});

describe('sharing', () => {
  const result = (() => {
    const r = play('share', () => 0).result;
    if (!r) throw new Error('no result');
    return r;
  })();

  it('picks the dominant day type, ties going to the earlier type', () => {
    expect(dominantType(['r', 'r', 'p'])).toBe('r');
    expect(dominantType(['p', 'o', 'o', 'p'])).toBe('p');
    expect(dominantType(['f'])).toBe('f');
  });

  it('builds twelve squares and the text of SPEC 6.8', () => {
    const squares = monthSquares(result);
    expect(Array.from(squares)).toHaveLength(12);
    for (const ch of squares) expect(Object.values(SQUARES)).toContain(ch);
    const text = buildShareText(result, {
      title: '365-0',
      modeLabel: 'daily',
      date: '2026-11-06',
      recordLabel: 'Record',
      gradeTitle: 'Sun chaser',
      url: 'https://example.test/',
    });
    const lines = text.split('\n');
    expect(lines).toHaveLength(4);
    expect(lines[0]).toBe('365-0 daily 2026-11-06');
    expect(lines[1]).toBe(
      `Record ${String(result.record.w)}-${String(result.record.d)}-${String(result.record.l)} (Sun chaser)`,
    );
    expect(lines[2]).toBe(squares);
    expect(lines[3]).toBe('https://example.test/');
  });

  it('exposes one column of days per month for the image', () => {
    const model = shareImageModel(result, { mode: 'endless' });
    expect(model.months).toHaveLength(12);
    expect(model.date).toBeUndefined();
    expect(model.months[1]?.days).toHaveLength(28);
    expect(model.grade).toBe(result.grade);
  });
});
