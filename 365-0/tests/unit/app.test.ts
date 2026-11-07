import { describe, expect, it } from 'vitest';
import {
  activeStreak,
  addDays,
  completeDaily,
  localDate,
  msUntilTomorrow,
} from '../../src/app/dates.ts';
import { createFormatter } from '../../src/app/format.ts';
import { restoreSession, newSession, doPick, doFinish, doComplete } from '../../src/app/session.ts';
import {
  defaultSettings,
  defaultUnit,
  emptyStored,
  parseStored,
  Store,
  STORAGE_KEY,
  type KeyValueStore,
} from '../../src/app/storage.ts';
import { currentRound, dailySeed } from '../../src/engine/index.ts';
import { data } from './helpers/data.ts';

const defaults = emptyStored(defaultSettings('en-GB', 'en'));

const memory = (initial?: string): KeyValueStore & { map: Map<string, string> } => {
  const map = new Map<string, string>(initial === undefined ? [] : [[STORAGE_KEY, initial]]);
  return {
    map,
    getItem: (k) => map.get(k) ?? null,
    setItem: (k, v) => {
      map.set(k, v);
    },
    removeItem: (k) => {
      map.delete(k);
    },
  };
};

describe('dates and streaks', () => {
  it('formats the local date as YYYY-MM-DD', () => {
    expect(localDate(new Date(2026, 10, 6, 23, 59))).toBe('2026-11-06');
    expect(localDate(new Date(2026, 0, 5))).toBe('2026-01-05');
  });

  it('adds days across month ends, year ends and leap days', () => {
    expect(addDays('2026-11-30', 1)).toBe('2026-12-01');
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(addDays('2028-02-28', 1)).toBe('2028-02-29');
    expect(addDays('2027-03-01', -1)).toBe('2027-02-28');
  });

  it('counts the time to local midnight', () => {
    const now = new Date(2026, 10, 6, 23, 0, 0);
    expect(msUntilTomorrow(now)).toBe(3600 * 1000);
  });

  it('grows the streak on consecutive days and restarts after a gap', () => {
    let s = completeDaily({ count: 0, last: null }, '2026-11-01');
    expect(s).toEqual({ count: 1, last: '2026-11-01' });
    s = completeDaily(s, '2026-11-02');
    s = completeDaily(s, '2026-11-03');
    expect(s.count).toBe(3);
    expect(completeDaily(s, '2026-11-03')).toBe(s); // the same day twice changes nothing
    expect(completeDaily(s, '2026-11-05')).toEqual({ count: 1, last: '2026-11-05' });
  });

  it('shows a streak only while the last daily was today or yesterday', () => {
    const s = { count: 4, last: '2026-11-05' };
    expect(activeStreak(s, '2026-11-05')).toBe(4);
    expect(activeStreak(s, '2026-11-06')).toBe(4);
    expect(activeStreak(s, '2026-11-07')).toBe(0);
    expect(activeStreak({ count: 0, last: null }, '2026-11-07')).toBe(0);
  });
});

describe('storage', () => {
  it('defaults the unit to Fahrenheit only in the United States, Liberia and Myanmar', () => {
    expect(defaultUnit('en-US')).toBe('f');
    expect(defaultUnit('sl-SI')).toBe('c');
    expect(defaultUnit('en-GB')).toBe('c');
    expect(defaultUnit(undefined)).toBe('c');
  });

  it('falls back to the defaults for missing, corrupt or foreign data', () => {
    expect(parseStored(null, defaults)).toBe(defaults);
    expect(parseStored('not json', defaults)).toBe(defaults);
    expect(parseStored('{"v":2}', defaults)).toBe(defaults);
    expect(parseStored('[1,2]', defaults)).toBe(defaults);
  });

  it('keeps valid fields and drops invalid ones', () => {
    const raw = JSON.stringify({
      v: 1,
      settings: { unit: 'f', language: 'sl', theme: 'purple', haptics: 'yes' },
      bestEndless: { w: 100, d: 150, l: 115 },
      daily: {
        '2026-11-05': { picks: ['a'], record: { w: 1, d: 2, l: 3 }, grade: 'sun-chaser' },
        'bad-date': { picks: [], record: { w: 1, d: 2, l: 3 }, grade: 'x' },
      },
      streak: { count: 3, last: '2026-11-05' },
      onboarded: true,
    });
    const s = parseStored(raw, defaults);
    expect(s.settings.unit).toBe('f');
    expect(s.settings.language).toBe('sl');
    expect(s.settings.theme).toBe('system'); // "purple" is not a theme
    expect(s.settings.haptics).toBe(true); // "yes" is not a boolean
    expect(s.bestEndless).toEqual({ w: 100, d: 150, l: 115 });
    expect(Object.keys(s.daily)).toEqual(['2026-11-05']);
    expect(s.streak).toEqual({ count: 3, last: '2026-11-05' });
    expect(s.onboarded).toBe(true);
  });

  it('saves and reloads through one versioned key', () => {
    const kv = memory();
    const store = new Store(defaults, kv);
    store.update((s) => {
      s.onboarded = true;
    });
    expect([...kv.map.keys()]).toEqual(['365-0:v1']);
    expect(new Store(defaults, kv).state.onboarded).toBe(true);
  });

  it('stays fully usable when storage is unavailable or throws', () => {
    const none = new Store(defaults, undefined);
    none.recordDaily('2026-11-06', {
      picks: [],
      record: { w: 1, d: 2, l: 3 },
      grade: 'stormbound',
    });
    expect(none.state.streak.count).toBe(1);
    const throwing: KeyValueStore = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('full');
      },
      removeItem: () => undefined,
    };
    const broken = new Store(defaults, throwing);
    expect(() => {
      broken.update((s) => {
        s.onboarded = true;
      });
    }).not.toThrow();
    expect(broken.state.onboarded).toBe(true);
  });

  it('keeps the first daily result of a date and moves the streak once', () => {
    const store = new Store(defaults, memory());
    const first = { picks: ['x'], record: { w: 10, d: 20, l: 335 }, grade: 'stormbound' as const };
    store.recordDaily('2026-11-06', first);
    store.recordDaily('2026-11-06', { ...first, record: { w: 99, d: 0, l: 266 } });
    expect(store.state.daily['2026-11-06']?.record.w).toBe(10);
    expect(store.state.streak.count).toBe(1);
  });

  it('keeps only the best endless record and resets progress without touching settings', () => {
    const store = new Store(defaults, memory());
    store.update((s) => {
      s.settings.unit = 'f';
    });
    store.recordEndless({ w: 50, d: 100, l: 215 });
    store.recordEndless({ w: 40, d: 100, l: 225 });
    store.recordEndless({ w: 70, d: 100, l: 195 });
    expect(store.state.bestEndless?.w).toBe(70);
    store.resetProgress();
    expect(store.state.bestEndless).toBeNull();
    expect(store.state.daily).toEqual({});
    expect(store.state.settings.unit).toBe('f');
  });
});

describe('formatting', () => {
  it('converts and rounds temperatures', () => {
    const c = createFormatter('en', 'c');
    const f = createFormatter('en', 'f');
    expect(c.temperature(10.6)).toBe('11°');
    expect(f.temperature(10.6)).toBe('51°');
    expect(c.temperature(-3.4)).toBe('-3°');
    expect(c.range(19, 28)).toBe('19–28 °C');
    expect(f.range(19, 28)).toBe('66–82 °F');
  });

  it('names months and countries in the chosen language', () => {
    expect(createFormatter('en', 'c').month(6)).toBe('July');
    expect(createFormatter('sl', 'c').month(6)).toBe('Julij');
    expect(createFormatter('en', 'c').country('SI')).toBe('Slovenia');
    expect(createFormatter('sl', 'c').country('SI')).toBe('Slovenija');
    expect(createFormatter('en', 'c').date('2026-11-06')).toBe('November 6');
  });

  it('uses Slovene city names where they differ and builds three-letter abbreviations', () => {
    const lisbon = data.cities.find((c) => c.id === 'lisbon');
    const laPaz = data.cities.find((c) => c.id === 'la-paz');
    if (!lisbon || !laPaz) throw new Error('cities missing');
    expect(createFormatter('en', 'c').cityName(lisbon)).toBe('Lisbon');
    expect(createFormatter('sl', 'c').cityName(lisbon)).toBe('Lizbona');
    expect(createFormatter('en', 'c').abbreviation(lisbon)).toBe('Lis');
    expect(createFormatter('sl', 'c').abbreviation(lisbon)).toBe('Liz');
    expect(createFormatter('en', 'c').abbreviation(laPaz)).toBe('LaP');
  });

  it('formats records and durations', () => {
    const f = createFormatter('en', 'c');
    expect(f.record({ w: 214, d: 91, l: 60 })).toBe('214-91-60');
    expect(f.duration(7 * 3600000 + 12 * 60000)).toBe('7 h 12 min');
    expect(f.duration(30000)).toBe('0 h 1 min');
  });
});

describe('sessions', () => {
  it('replays a finished daily from its seed and picks to the identical result', () => {
    const date = '2026-11-06';
    const played = newSession('daily', data, { date });
    while (currentRound(played.state)) {
      const round = currentRound(played.state);
      if (!round) break;
      doPick(played, round.cities[1]);
    }
    doFinish(played);
    doComplete(played);
    const restored = restoreSession('daily', data, dailySeed(date), date, played.state.picks);
    expect(restored.state.result).toEqual(played.state.result);
    expect(restored.state.phase).toBe('done');
  });

  it('gives different endless seeds different drafts', () => {
    const a = newSession('endless', data, { entropy: 'aaa' });
    const b = newSession('endless', data, { entropy: 'bbb' });
    expect(a.state.draft).not.toEqual(b.state.draft);
  });
});
