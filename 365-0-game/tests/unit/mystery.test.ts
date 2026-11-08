import { describe, expect, it } from 'vitest';
import {
  candidateOrder,
  CLUES,
  dayLengthMinutes,
  guess,
  isFinished,
  newMystery,
  points,
  puzzleFor,
  resultOf,
  reveal,
  stateFrom,
  type MysteryFile,
  type Puzzle,
} from '../../src/engine/mystery.ts';
import type { SeedCity } from '../../src/data/types.ts';
import { DAILY_VARIABLES, type ApiResponse } from '../../scripts/lib/build.ts';
import { buildMystery, gapDegrees, misfit, monthStats } from '../../scripts/lib/mystery.ts';
import { validateMystery } from '../../scripts/lib/validate.ts';
import { makeRng } from '../../src/engine/rng.ts';

const puzzle: Puzzle = {
  m: 10,
  d: 8,
  year: 2019,
  city: 'oslo',
  decoys: ['lima', 'cairo'],
  w: { tx: 2, tn: -3, p: 1, s: 0, g: 30, cl: 80 },
  typ: { oslo: [0, 6, -4, 1, 40], lima: [20, 24, 17, 19, 1], cairo: [22, 28, 13, 18, 2] },
};

describe('playing a mystery', () => {
  it('scores 4 points for the first clue down to 1 for all four, and 0 when not solved', () => {
    let s = newMystery();
    expect(points(guess(s, puzzle, 'oslo'))).toBe(4);
    s = reveal(reveal(s));
    expect(points(guess(s, puzzle, 'oslo'))).toBe(2);
    s = reveal(reveal(s));
    expect(s.revealed).toBe(CLUES.length);
    expect(reveal(s).revealed).toBe(CLUES.length);
    expect(points(guess(s, puzzle, 'oslo'))).toBe(1);
    expect(points(newMystery())).toBe(0);
  });

  it('a wrong guess crosses the city out and shows the next clue', () => {
    const s = guess(newMystery(), puzzle, 'lima');
    expect(s).toMatchObject({ wrong: ['lima'], revealed: 2, solved: false });
    expect(points(guess(s, puzzle, 'oslo'))).toBe(3);
    // The same wrong city again changes nothing.
    expect(guess(s, puzzle, 'lima')).toEqual(s);
  });

  it('two wrong guesses end it with no points, the last city is the answer', () => {
    const s = guess(guess(newMystery(), puzzle, 'lima'), puzzle, 'cairo');
    expect(isFinished(s)).toBe(true);
    expect(points(s)).toBe(0);
    expect(guess(s, puzzle, 'oslo')).toEqual(s);
    expect(reveal(s)).toEqual(s);
  });

  it('rebuilds the state from a stored result, including clues looked at on purpose', () => {
    let s = reveal(newMystery());
    s = guess(s, puzzle, 'lima');
    s = reveal(s);
    s = guess(s, puzzle, 'oslo');
    const stored = resultOf(s, puzzle);
    expect(stored).toEqual({ guesses: ['lima', 'oslo'], revealed: 4, points: 1, done: true });
    expect(stateFrom(stored, puzzle)).toEqual(s);
    const lost = resultOf(guess(guess(newMystery(), puzzle, 'cairo'), puzzle, 'lima'), puzzle);
    expect(stateFrom(lost, puzzle).wrong).toEqual(['cairo', 'lima']);
    expect(lost.points).toBe(0);
  });
});

describe('choosing the puzzle', () => {
  const file: MysteryFile = {
    v: 1,
    from: '2026-11-09',
    years: [2016, 2025],
    puzzles: [1, 2, 3].map((n) => ({ ...puzzle, year: 2015 + n })),
  };
  it('takes the puzzle of the day and starts over after the end', () => {
    expect(puzzleFor(file, '2026-11-09').year).toBe(2016);
    expect(puzzleFor(file, '2026-11-11').year).toBe(2018);
    expect(puzzleFor(file, '2026-11-12').year).toBe(2016);
    expect(puzzleFor(file, '2026-11-08').year).toBe(2018); // before the start also works
  });
  it('offers the three cities in the same order to everyone on a date', () => {
    const a = candidateOrder(puzzle, '2026-11-09');
    expect(a).toEqual(candidateOrder(puzzle, '2026-11-09'));
    expect([...a].sort()).toEqual(['cairo', 'lima', 'oslo']);
    const orders = new Set(
      Array.from({ length: 20 }, (_, i) =>
        candidateOrder(puzzle, `2026-12-${String(i + 1).padStart(2, '0')}`).join(),
      ),
    );
    expect(orders.size).toBeGreaterThan(1);
  });
});

describe('length of the day', () => {
  const hm = (min: number): string =>
    `${String(Math.floor(min / 60))}:${String(min % 60).padStart(2, '0')}`;
  it('matches known values within a few minutes', () => {
    // Ljubljana, 46.05 N: about 8 h 40 min on 21 December and 15 h 50 min on 21 June.
    expect(Math.abs(dayLengthMinutes(46.05, 11, 21) - (8 * 60 + 40))).toBeLessThanOrEqual(8);
    expect(Math.abs(dayLengthMinutes(46.05, 5, 21) - (15 * 60 + 50))).toBeLessThanOrEqual(8);
    // On the equator the day is a little over 12 hours all year.
    for (const m of [0, 3, 6, 9]) {
      const v = dayLengthMinutes(0, m, 15);
      expect(v, hm(v)).toBeGreaterThan(715);
      expect(v, hm(v)).toBeLessThan(735);
    }
  });
  it('is 0 in polar night, 24 h in polar day, and flips between the hemispheres', () => {
    expect(dayLengthMinutes(78, 11, 21)).toBe(0);
    expect(dayLengthMinutes(78, 5, 21)).toBe(1440);
    expect(dayLengthMinutes(-34, 11, 21)).toBeGreaterThan(14 * 60);
    expect(dayLengthMinutes(34, 11, 21)).toBeLessThan(10 * 60);
  });
});

// A small world with distinct climates, two years of daily data.
const BASES: Record<
  string,
  { c: SeedCity['continent']; country: string; mean: number; amp: number }
> = {
  oslo: { c: 'europe', country: 'NO', mean: 6, amp: 12 },
  rome: { c: 'europe', country: 'IT', mean: 16, amp: 9 },
  cairo: { c: 'africa', country: 'EG', mean: 22, amp: 8 },
  lima: { c: 'south-america', country: 'PE', mean: 19, amp: 4 },
  delhi: { c: 'asia', country: 'IN', mean: 25, amp: 9 },
  ushuaia: { c: 'south-america', country: 'AR', mean: 5, amp: 5 },
  perth: { c: 'oceania', country: 'AU', mean: 18, amp: 6 },
  quito: { c: 'south-america', country: 'EC', mean: 14, amp: 1 },
};

function fakeCities(): SeedCity[] {
  return Object.entries(BASES).map(([id, b]) => ({
    id,
    name: { en: id },
    country: b.country,
    continent: b.c,
    lat: 10,
    lon: 10,
    tags: [],
    archetype: 'oceanic',
  }));
}

function fakeResponse(id: string, year: number): ApiResponse {
  const b = BASES[id] ?? BASES['oslo']!;
  const rng = makeRng('fake', id, year);
  const time: string[] = [];
  for (let m = 0; m < 12; m++) {
    const n = [31, year % 4 === 0 ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m] ?? 30;
    for (let d = 1; d <= n; d++)
      time.push(`${String(year)}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`);
  }
  const daily = { time } as ApiResponse['daily'];
  const southern = ['ushuaia', 'perth', 'lima'].includes(id);
  const mean = time.map((t) => {
    const doy =
      (Date.UTC(year, Number(t.slice(5, 7)) - 1, Number(t.slice(8, 10))) - Date.UTC(year, 0, 1)) /
      864e5;
    const season = Math.cos(((doy - (southern ? 15 : 196)) / 365) * 2 * Math.PI);
    return b.mean + b.amp * season + (rng() - 0.5) * 4;
  });
  for (const key of DAILY_VARIABLES) {
    daily[key] = mean.map((t) => {
      switch (key) {
        case 'temperature_2m_max':
          return Math.round((t + 4) * 10) / 10;
        case 'temperature_2m_min':
          return Math.round((t - 4) * 10) / 10;
        case 'temperature_2m_mean':
          return Math.round(t * 10) / 10;
        case 'precipitation_sum':
          return rng() < 0.3 ? Math.round(rng() * 80) / 10 : 0;
        case 'snowfall_sum':
          return t < 0 && rng() < 0.4 ? Math.round(rng() * 50) / 10 : 0;
        case 'wind_gusts_10m_max':
          return Math.round(10 + rng() * 40);
        case 'weather_code':
          return 1;
        case 'cloud_cover_mean':
          return Math.round(rng() * 100);
      }
    });
  }
  return { latitude: 0, longitude: 0, elevation: 0, daily };
}

function fakeInput() {
  const cities = fakeCities();
  const years = [2020, 2021, 2022];
  const responses = new Map<string, ApiResponse>();
  for (const c of cities)
    for (const y of years) responses.set(`${c.id}/${String(y)}`, fakeResponse(c.id, y));
  return { cities, years, responses };
}

describe('building the puzzles', () => {
  const input = fakeInput();
  const file = buildMystery(input, '2026-11-09', 40);

  it('builds one valid puzzle for each day', () => {
    expect(file.puzzles).toHaveLength(40);
    expect(validateMystery(file, input.cities)).toEqual([]);
    expect(file.puzzles[0]).toMatchObject({ m: 10, d: 9 });
    expect(file.puzzles[22]).toMatchObject({ m: 11, d: 1 });
  });

  it('every right city fits the day and every wrong one clearly does not', () => {
    const stats = new Map(
      input.cities.map((c) => [
        c.id,
        monthStats([...input.years].map((y) => input.responses.get(`${c.id}/${String(y)}`)!)),
      ]),
    );
    for (const p of file.puzzles) {
      const obs = { tx: p.w.tx, tn: p.w.tn };
      const own = stats.get(p.city)?.[p.m];
      expect(own && misfit(obs, own)).toBeLessThanOrEqual(1.5);
      for (const id of p.decoys) {
        const st = stats.get(id)?.[p.m];
        expect(st && misfit(obs, st)).toBeGreaterThanOrEqual(1);
        expect(st && gapDegrees(obs, st)).toBeGreaterThanOrEqual(2);
        expect(input.cities.find((c) => c.id === id)?.country).not.toBe(
          input.cities.find((c) => c.id === p.city)?.country,
        );
      }
      expect(Object.keys(p.typ).sort()).toEqual([p.city, ...p.decoys].sort());
    }
  });

  it('is deterministic, and a longer file keeps the puzzles that are already out', () => {
    expect(buildMystery(input, '2026-11-09', 40)).toEqual(file);
    const longer = buildMystery(input, '2026-11-09', 60);
    expect(longer.puzzles.slice(0, 40)).toEqual(file.puzzles);
  });

  it('spreads the right answer over many cities', () => {
    expect(new Set(file.puzzles.map((p) => p.city)).size).toBeGreaterThanOrEqual(4);
  });

  it('the validator catches broken puzzles', () => {
    const bad = structuredClone(file);
    const p = bad.puzzles[0]!;
    p.decoys = [p.city, p.decoys[1]];
    bad.puzzles[1]!.w.tx = 500;
    bad.puzzles[2]!.d = 31; // 31 December is fine, but this is November
    bad.puzzles[2]!.m = 10;
    const errors = validateMystery(bad, input.cities);
    expect(errors.some((e) => e.includes('puzzle 0') && e.includes('decoys'))).toBe(true);
    expect(errors.some((e) => e.includes('puzzle 1') && e.includes('weather'))).toBe(true);
    expect(errors.some((e) => e.includes('puzzle 2') && e.includes('day'))).toBe(true);
    expect(validateMystery({ v: 2 }, input.cities).length).toBeGreaterThan(0);
  });

  it('refuses to invent a puzzle when no city can be told apart', () => {
    const one = { ...input, cities: input.cities.slice(0, 2) };
    expect(() => buildMystery(one, '2026-11-09', 1)).toThrow(/no fair mystery/);
  });
});

import maskJson from '../../src/data/worldmask.json';
import { isLand, project } from '../../src/engine/worldmap.ts';

describe('the dot map', () => {
  const mask = maskJson;
  it('has a full grid of land and sea', () => {
    expect(mask.rows).toHaveLength((mask.top * 2) / mask.step);
    expect(mask.rows.every((r) => r.length === mask.cols && /^[01]+$/.test(r))).toBe(true);
    const land = mask.rows.join('').replaceAll('0', '').length;
    expect(land / (mask.cols * mask.rows.length)).toBeGreaterThan(0.15);
    expect(land / (mask.cols * mask.rows.length)).toBeLessThan(0.4);
  });

  it('puts places where they belong', () => {
    const at = (lat: number, lon: number): { col: number; row: number } => {
      const p = project(mask, lat, lon);
      return {
        col: Math.min(mask.cols - 1, Math.floor(p.x * mask.cols)),
        row: Math.min(mask.rows.length - 1, Math.floor(p.y * mask.rows.length)),
      };
    };
    // Ljubljana, Cairo, Chicago and Alice Springs are on land; the middle of the Pacific and the South Atlantic are not.
    for (const [lat, lon] of [
      [46.05, 14.5],
      [30.04, 31.24],
      [41.88, -87.63],
      [-23.7, 133.9],
    ] as const) {
      const { col, row } = at(lat, lon);
      expect(isLand(mask, col, row), `${String(lat)},${String(lon)}`).toBe(true);
    }
    for (const [lat, lon] of [
      [0, -150],
      [-30, -15],
    ] as const) {
      const { col, row } = at(lat, lon);
      expect(isLand(mask, col, row), `${String(lat)},${String(lon)}`).toBe(false);
    }
  });

  it('puts the corners at the corners and keeps everything on the map', () => {
    expect(project(mask, mask.top, -180)).toEqual({ x: 0, y: 0 });
    expect(project(mask, -mask.top, 180)).toEqual({ x: 1, y: 1 });
    expect(project(mask, 90, 200).y).toBe(0);
    expect(project(mask, 0, 0)).toEqual({ x: 0.5, y: 0.5 });
  });
});
