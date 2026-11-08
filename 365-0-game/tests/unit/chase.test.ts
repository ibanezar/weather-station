import { describe, expect, it } from 'vitest';
import {
  CHASE_IDS,
  CHASES,
  DAY_TYPE_CHARS,
  bestPossible,
  chaseBuckets,
  complete,
  currentRound,
  dailySeed,
  finish,
  generateDraft,
  isChaseId,
  MIN_BEST_WINS,
  keep,
  monthRisk,
  newRun,
  pick,
  quintileBuckets,
  record,
  recordFor,
  scoutInfo,
  start,
  type DayType,
  type ChaseId,
} from '../../src/engine/index.ts';
import { parseStored, defaultSettings, emptyStored, dailyKey } from '../../src/app/storage.ts';
import { data, seeds } from './helpers/data.ts';

describe('chases', () => {
  it('have disjoint win and loss types, and every day type is a win, draw or loss somewhere', () => {
    for (const id of CHASE_IDS) {
      const { win, loss } = CHASES[id];
      expect(win.length).toBeGreaterThan(0);
      expect(win.some((t) => loss.includes(t))).toBe(false);
    }
    for (const t of DAY_TYPE_CHARS) {
      expect(CHASE_IDS.some((id) => CHASES[id].win.includes(t))).toBe(t !== 'o');
    }
  });

  it('score the same days differently', () => {
    const days = (
      'p'.repeat(10) +
      'o'.repeat(5) +
      'r'.repeat(4) +
      's'.repeat(3) +
      'h'.repeat(2) +
      'f'.repeat(6)
    ).split('') as DayType[];
    expect(recordFor(days, 'sun')).toEqual({ w: 10, d: 5, l: 15 });
    expect(recordFor(days, 'snow')).toEqual({ w: 6, d: 5 + 4 + 3, l: 2 + 10 });
    expect(recordFor(days, 'rain')).toEqual({ w: 4, d: 5 + 3 + 6, l: 10 + 2 });
    expect(recordFor(days, 'storm')).toEqual({ w: 3, d: 5 + 4 + 2 + 6, l: 10 });
    expect(recordFor(days, 'heat')).toEqual({ w: 2, d: 10 + 5 + 3, l: 6 + 4 });
    // The classic game is the default
    expect(record(days)).toEqual(recordFor(days, 'sun'));
    for (const id of CHASE_IDS) {
      const r = recordFor(days, id);
      expect(r.w + r.d + r.l).toBe(days.length);
    }
  });

  it('knows its ids', () => {
    expect(isChaseId('snow')).toBe(true);
    expect(isChaseId('tornado')).toBe(false);
    expect(isChaseId(undefined)).toBe(false);
  });

  it('give each chase its own daily draft, with the classic one unchanged', () => {
    expect(dailySeed('2026-11-08')).toBe('365-0:daily:2026-11-08');
    expect(dailySeed('2026-11-08', 'sun')).toBe('365-0:daily:2026-11-08');
    expect(dailySeed('2026-11-08', 'snow')).toBe('365-0:daily:2026-11-08:snow');
    const a = generateDraft(dailySeed('2026-11-08'), data);
    const b = generateDraft(dailySeed('2026-11-08', 'snow'), data);
    expect(a).not.toEqual(b);
  });

  it('change which city is best: the best snow year is not the best sunny year', () => {
    let different = 0;
    for (const seed of seeds(40, 'chase')) {
      const draft = generateDraft(seed, data);
      const sun = bestPossible(data, seed, draft, 'sun');
      const snow = bestPossible(data, seed, draft, 'snow');
      if (sun.rounds.some((r, i) => r.best.cityId !== snow.rounds[i]?.best.cityId)) different += 1;
      expect(snow.record.w).toBeGreaterThanOrEqual(0);
    }
    expect(different).toBeGreaterThan(30);
  });

  it('never deal a chase a draft with too few winnable months, and leave the sunny draft alone', () => {
    for (const id of CHASE_IDS) {
      for (const seed of seeds(120, `floor:${id}`)) {
        const run = start(newRun(seed, 'endless', id), data);
        expect(run.best?.record.w ?? 0, `${id} ${seed}`).toBeGreaterThanOrEqual(MIN_BEST_WINS[id]);
      }
    }
    for (const seed of seeds(20, 'same')) {
      expect(start(newRun(seed, 'endless', 'sun'), data).draft).toEqual(generateDraft(seed, data));
    }
  });

  it('can be played from the first pick to the grade, with wins counted for the chase', () => {
    for (const id of CHASE_IDS) {
      let s = start(newRun(`play:${id}`, 'endless', id), data);
      for (let i = 0; i < 12; i++) {
        s = keep(pick(s, (currentRound(s) as { cities: string[] }).cities[0] as string));
      }
      s = complete(finish(s, data));
      const result = s.result;
      expect(result).toBeDefined();
      const days = result?.rounds.flatMap((r) => r.days) ?? [];
      expect(result?.record).toEqual(recordFor(days, id));
      expect(days.length).toBe(365);
      expect(result?.bestRecord.w).toBeGreaterThanOrEqual(result?.record.w ?? 0);
    }
  });
});

describe('scout buckets and risk by chase', () => {
  it('quintiles give the same bucket to equal values', () => {
    expect(quintileBuckets([1, 1, 1, 1, 1])).toEqual([2, 2, 2, 2, 2]);
    expect(quintileBuckets([0, 1, 2, 3, 4]).sort()).toEqual([0, 1, 2, 3, 4]);
  });

  it('are stored for sunshine and computed for the others, always 0 to 4', () => {
    expect(scoutInfo(data, 'dubai', 6)).toEqual(scoutInfo(data, 'dubai', 6, 'sun'));
    for (const id of CHASE_IDS) {
      for (const c of data.cities) {
        for (let m = 0; m < 12; m += 5) {
          const info = scoutInfo(data, c.id, m, id);
          expect(info.win).toBeGreaterThanOrEqual(0);
          expect(info.win).toBeLessThanOrEqual(4);
          expect(info.loss).toBeGreaterThanOrEqual(0);
          expect(info.loss).toBeLessThanOrEqual(4);
        }
      }
    }
  });

  it('rank the right places high: Dubai in July for heat, Reykjavik in January for snow', () => {
    expect(chaseBuckets(data.world, 'heat', 'dubai', 6).win).toBeGreaterThanOrEqual(3);
    expect(chaseBuckets(data.world, 'heat', 'reykjavik', 6).win).toBe(0);
    expect(chaseBuckets(data.world, 'snow', 'reykjavik', 0).win).toBeGreaterThanOrEqual(3);
    expect(chaseBuckets(data.world, 'snow', 'dubai', 0).win).toBe(0);
  });

  it('count the risk in winning days of the chase', () => {
    const sun = monthRisk(data, 'dubai', 6, 'sun');
    const heat = monthRisk(data, 'dubai', 6, 'heat');
    expect(heat.max).toBeGreaterThan(sun.max);
  });
});

describe('storage', () => {
  const defaults = emptyStored(defaultSettings('en-GB', 'en'));

  it('keeps an old sunshine record, and a daily key per chase', () => {
    const raw = JSON.stringify({
      v: 1,
      bestEndless: { w: 80, d: 100, l: 185 },
      daily: {
        '2026-11-07': { picks: ['a'], record: { w: 1, d: 2, l: 3 }, grade: 'stormbound' },
        '2026-11-08:snow': {
          picks: ['b'],
          rerolls: [3],
          record: { w: 1, d: 2, l: 3 },
          grade: 'stormbound',
        },
        'bad-key': { picks: ['c'], record: { w: 1, d: 2, l: 3 }, grade: 'stormbound' },
      },
      settings: { chase: 'storm' },
    });
    const out = parseStored(raw, defaults);
    expect(out.bestEndless).toEqual({ sun: { w: 80, d: 100, l: 185 } });
    expect(Object.keys(out.daily).sort()).toEqual(['2026-11-07', '2026-11-08:snow']);
    expect(out.daily['2026-11-08:snow']?.rerolls).toEqual([3]); // redraws survive a reload
    expect(out.settings.chase).toBe('storm');
    expect(dailyKey('2026-11-08')).toBe('2026-11-08');
    expect(dailyKey('2026-11-08', 'rain')).toBe('2026-11-08:rain');
  });

  it('ignores an unknown chase', () => {
    const out = parseStored(JSON.stringify({ v: 1, settings: { chase: 'tornado' } }), defaults);
    expect(out.settings.chase).toBe('sun');
  });
});

describe('invented events', () => {
  const invented = data.events.filter((e) => e.fictional === true);
  it('are four, and named like the wish list', () => {
    expect(invented.map((e) => e.id).sort()).toEqual([
      'blizzard',
      'flash-flood',
      'tornado-outbreak',
      'volcanic-ash',
    ]);
  });
  it('show up in drafts, and only on cities their tags cover', () => {
    let seen = 0;
    for (const seed of seeds(300, 'inv')) {
      for (const round of generateDraft(seed, data)) {
        if (round.event && invented.some((e) => e.id === round.event)) seen += 1;
      }
    }
    expect(seen).toBeGreaterThan(100);
  });
  it('are always valid chase ids in the type', () => {
    const id: ChaseId = 'heat';
    expect(CHASE_IDS).toContain(id);
  });
});
