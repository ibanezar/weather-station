import { describe, expect, it } from 'vitest';
import { COUNTS_URL, isLiveSite, sendCount, type CountEvent } from '../../src/app/counts.ts';
import { computeStats, longestStretch } from '../../src/app/progress-stats.ts';
import {
  defaultSettings,
  emptyStored,
  parseStored,
  Store,
  type KeyValueStore,
} from '../../src/app/storage.ts';
import { ratio } from '../../src/engine/grades.ts';

const defaults = emptyStored(defaultSettings('en-GB', 'en'));
const memory = (): KeyValueStore & { map: Map<string, string> } => {
  const map = new Map<string, string>();
  return {
    map,
    getItem: (k) => map.get(k) ?? null,
    setItem: (k, v) => void map.set(k, v),
    removeItem: (k) => void map.delete(k),
  };
};

describe('the grade ratio', () => {
  it('is capped at 1 so a lucky redraw cannot show more than 100 %', () => {
    expect(ratio(120, 100)).toBe(1);
    expect(ratio(99, 100)).toBe(0.99);
  });
});

describe('longest streak', () => {
  it('finds the longest run of consecutive days, ignoring repeats and order', () => {
    expect(longestStretch([])).toBe(0);
    expect(
      longestStretch(['2026-11-03', '2026-11-01', '2026-11-02', '2026-11-02', '2026-11-07']),
    ).toBe(3);
    expect(longestStretch(['2026-11-30', '2026-12-01'])).toBe(2);
  });
});

describe('statistics from stored progress', () => {
  const record = (w: number) => ({ w, d: 10, l: 5 });
  it('counts games, finds bests per chase and lists the latest dailies', () => {
    const store = new Store(structuredClone(defaults), memory());
    store.recordDaily('2026-11-01', { picks: [], record: record(100), grade: 'sun-chaser' });
    store.recordDaily('2026-11-02', { picks: [], record: record(140), grade: 'climate-sage' });
    store.recordDaily('2026-11-02', { picks: [], record: record(90), grade: 'stormbound' }, 'snow');
    store.recordEndless(record(120), 'sun');
    store.recordEndless(record(80), 'sun');
    const s = computeStats(store.state);
    expect(s.runs).toBe(5);
    expect(s.dailies).toBe(3);
    expect(s.longestStreak).toBe(2);
    const sun = s.perChase.find((c) => c.chase === 'sun');
    expect(sun).toMatchObject({
      runs: 4,
      dailies: 2,
      bestDaily: record(140),
      bestEndless: record(120),
    });
    const snow = s.perChase.find((c) => c.chase === 'snow');
    expect(snow).toMatchObject({ runs: 1, dailies: 1, bestDaily: record(90), bestEndless: null });
    expect(s.recent.map((d) => `${d.date}:${d.chase}`)).toEqual([
      '2026-11-02:sun',
      '2026-11-02:snow',
      '2026-11-01:sun',
    ]);
  });

  it('does not count a daily twice, and resetting progress clears the counts', () => {
    const store = new Store(structuredClone(defaults), memory());
    const r = { picks: [], record: record(100), grade: 'sun-chaser' as const };
    store.recordDaily('2026-11-01', r);
    store.recordDaily('2026-11-01', r);
    expect(store.state.runs['sun']).toBe(1);
    store.resetProgress();
    expect(store.state.runs).toEqual({});
  });

  it('keeps the counts setting and the run counts through a save and load, and repairs bad values', () => {
    const store = new Store(structuredClone(defaults), memory());
    store.update((s) => {
      s.settings.counts = false;
      s.runs['rain'] = 3;
    });
    const again = parseStored(JSON.stringify(store.state), defaults);
    expect(again.settings.counts).toBe(false);
    expect(again.runs).toEqual({ rain: 3 });
    const broken = parseStored(
      JSON.stringify({
        v: 1,
        settings: { counts: 'yes' },
        runs: { sun: -2, x: 4, snow: 'a', heat: 2.7 },
      }),
      defaults,
    );
    expect(broken.settings.counts).toBe(true);
    expect(broken.runs).toEqual({ heat: 2 });
  });
});

describe('anonymous play counts', () => {
  const event: CountEvent = {
    ev: 'finish',
    mode: 'daily',
    chase: 'snow',
    grade: 'sun-chaser',
    rerolls: 1,
  };
  it('sends the event and nothing else when on, and nothing when off', () => {
    const sent: { url: string; body: string }[] = [];
    const send = (url: string, body: string): void => void sent.push({ url, body });
    sendCount(true, event, send);
    sendCount(false, event, send);
    expect(sent).toEqual([{ url: COUNTS_URL, body: JSON.stringify(event) }]);
    expect(Object.keys(JSON.parse(sent[0]?.body ?? '{}') as object).sort()).toEqual([
      'chase',
      'ev',
      'grade',
      'mode',
      'rerolls',
    ]);
  });
  it('never throws, even if sending does', () => {
    expect(() => {
      sendCount(true, event, () => {
        throw new Error('blocked');
      });
    }).not.toThrow();
  });
  it('only runs on the live site', () => {
    expect(isLiveSite('meteorec.si')).toBe(true);
    expect(isLiveSite('www.meteorec.si')).toBe(true);
    expect(isLiveSite('localhost')).toBe(false);
    expect(isLiveSite('ibanezar.github.io')).toBe(false);
    expect(isLiveSite('meteorec.si.evil.example')).toBe(false);
  });
});
