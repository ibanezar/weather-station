import { describe, expect, it } from 'vitest';
import {
  classifyDay,
  DAY_TYPE_CHARS,
  isLoss,
  THRESHOLDS,
  type DailyWeather,
} from '../../src/engine/thresholds.ts';

/** A clearly perfect day; each test changes one thing. */
const PERFECT: DailyWeather = {
  tmax: 24,
  tmin: 14,
  precip: 0,
  snow: 0,
  gust: 20,
  code: 1,
  cloud: 30,
};
const day = (over: Partial<DailyWeather>): DailyWeather => ({ ...PERFECT, ...over });

describe('classifyDay', () => {
  it('calls the reference day perfect', () => {
    expect(classifyDay(PERFECT)).toBe('p');
  });

  describe('perfect boundaries', () => {
    it.each([
      [{ tmax: 16 }, 'p'],
      [{ tmax: 15.9 }, 'o'],
      [{ tmax: 32 }, 'p'],
      [{ tmax: 32.1 }, 'o'],
      [{ tmin: 5 }, 'p'],
      [{ tmin: 4.9 }, 'o'],
      [{ precip: 0.9 }, 'p'],
      [{ precip: 1 }, 'o'],
      [{ gust: 49.9 }, 'p'],
      [{ gust: 50 }, 'o'],
      [{ cloud: 90 }, 'p'],
      [{ cloud: 90.1 }, 'o'],
    ] as [Partial<DailyWeather>, string][])('%j is %s', (over, expected) => {
      expect(classifyDay(day(over))).toBe(expected);
    });

    it('skips the cloud condition when cloud cover is unknown', () => {
      expect(classifyDay(day({ cloud: undefined }))).toBe('p');
      expect(classifyDay(day({ cloud: 100 }))).toBe('o');
    });
  });

  describe('loss types', () => {
    it.each([
      [{ precip: 5 }, 'r'],
      [{ precip: 4.99 }, 'o'],
      [{ precip: 0.99 }, 'p'],
      [{ precip: 29.9 }, 'r'],
      [{ precip: 30 }, 's'],
      [{ gust: 70 }, 's'],
      [{ gust: 69.9 }, 'o'],
      [{ code: 95 }, 's'],
      [{ code: 96 }, 's'],
      [{ code: 99 }, 's'],
      [{ code: 61 }, 'p'],
      [{ tmax: 3 }, 'f'],
      [{ tmax: 3.1 }, 'o'],
      [{ snow: 1 }, 'f'],
      [{ snow: 0.9 }, 'p'],
      [{ tmax: 36 }, 'h'],
      [{ tmax: 35.9 }, 'o'],
    ] as [Partial<DailyWeather>, string][])('%j is %s', (over, expected) => {
      expect(classifyDay(day(over))).toBe(expected);
    });
  });

  describe('precedence: storm, freeze, heat, rain, perfect, ok', () => {
    it('storm beats freeze, heat and rain', () => {
      expect(classifyDay(day({ code: 95, tmax: 1, snow: 5, precip: 6 }))).toBe('s');
      expect(classifyDay(day({ gust: 80, tmax: 38 }))).toBe('s');
    });
    it('freeze beats rain', () => {
      expect(classifyDay(day({ tmax: 1, precip: 6 }))).toBe('f');
    });
    it('snow makes a freeze even on a mild day', () => {
      expect(classifyDay(day({ tmax: 12, snow: 2, precip: 6 }))).toBe('f');
    });
    it('heat beats rain', () => {
      expect(classifyDay(day({ tmax: 37, precip: 6 }))).toBe('h');
    });
    it('rain beats a day that would otherwise be perfect', () => {
      expect(classifyDay(day({ precip: 6 }))).toBe('r');
      expect(classifyDay(day({ precip: 2 }))).toBe('o'); // drizzle spoils a perfect day but is not a loss
    });
  });

  it('only returns the six allowed characters', () => {
    for (let tmax = -20; tmax <= 45; tmax += 5) {
      for (const precip of [0, 1, 30]) {
        for (const gust of [10, 40, 70]) {
          expect(DAY_TYPE_CHARS).toContain(classifyDay(day({ tmax, precip, gust })));
        }
      }
    }
  });
});

describe('isLoss', () => {
  it('counts rain, storm, heat and freeze as losses only', () => {
    expect(DAY_TYPE_CHARS.filter(isLoss)).toEqual(['r', 's', 'h', 'f']);
  });
});

describe('thresholds', () => {
  it('are the values tuned on the real data (the SPEC 1.4 starting values gave 10% perfect days)', () => {
    expect(THRESHOLDS.storm.gustKmhMin).toBe(70);
    expect(THRESHOLDS.storm.precipMmMin).toBe(30);
    expect(THRESHOLDS.freeze.tmaxCMax).toBe(3);
    expect(THRESHOLDS.heat.tmaxCMin).toBe(36);
    expect(THRESHOLDS.rain.precipMmMin).toBe(5);
    expect(THRESHOLDS.perfect.precipMmMax).toBe(1);
    expect(THRESHOLDS.perfect.tmaxCMin).toBe(16);
    expect(THRESHOLDS.perfect.tmaxCMax).toBe(32);
  });
});
