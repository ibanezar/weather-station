// Everything the game remembers lives under one versioned localStorage key (SPEC 5). Every read and
// write is wrapped, and the game stays fully playable when storage is unavailable.
import { DEFAULT_CHASE, isChaseId, type ChaseId } from '../engine/chase.ts';
import type { GradeId } from '../engine/grades.ts';
import type { DayRecord } from '../engine/types.ts';
import type { Locale } from '../i18n/index.ts';
import type { MotionSetting, PatternSetting, ThemeSetting } from '../ui/settings.ts';
import { completeDaily, type Streak } from './dates.ts';

export const STORAGE_KEY = '365-0:v1';

export type Unit = 'c' | 'f';

export interface Settings {
  unit: Unit;
  language: Locale;
  theme: ThemeSetting;
  motion: MotionSetting;
  pattern: PatternSetting;
  haptics: boolean;
  sound: boolean;
  /** What the player is chasing: sunshine (the classic game), snow, rain, storms or heat. */
  chase: ChaseId;
  /** Send anonymous play counts (a game started or finished, which chase and grade). Nothing else leaves the device. */
  counts: boolean;
}

export interface DailyResult {
  picks: string[];
  /** Rounds that used a second chance, in order (absent in results saved before they existed). */
  rerolls?: number[];
  record: DayRecord;
  grade: GradeId;
}

export interface Stored {
  v: 1;
  settings: Settings;
  /** Best endless record for each chase, by wins. */
  bestEndless: Partial<Record<ChaseId, DayRecord>>;
  /** Keyed by date for sunshine and by `date:chase` for the other chases (see dailyKey). */
  daily: Record<string, DailyResult>;
  streak: Streak;
  /** Finished games (daily and endless) for each chase. */
  runs: Partial<Record<ChaseId, number>>;
  onboarded: boolean;
}

/** Where a daily result is stored: the date for sunshine, `date:chase` for the other chases. */
export function dailyKey(date: string, chase: ChaseId = DEFAULT_CHASE): string {
  return chase === DEFAULT_CHASE ? date : `${date}:${chase}`;
}

/** Fahrenheit by default only where it is the local custom. */
export function defaultUnit(languageTag: string | undefined): Unit {
  return /-(US|LR|MM)\b/i.test(languageTag ?? '') ? 'f' : 'c';
}

export function defaultSettings(languageTag: string | undefined, locale: Locale): Settings {
  return {
    unit: defaultUnit(languageTag),
    language: locale,
    theme: 'system',
    motion: 'system',
    pattern: 'auto',
    haptics: true,
    sound: false,
    chase: DEFAULT_CHASE,
    counts: true,
  };
}

export function emptyStored(settings: Settings): Stored {
  return {
    v: 1,
    settings,
    bestEndless: {},
    daily: {},
    streak: { count: 0, last: null },
    runs: {},
    onboarded: false,
  };
}

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);
const isRecord = (v: unknown): v is DayRecord =>
  isObject(v) &&
  typeof v['w'] === 'number' &&
  typeof v['d'] === 'number' &&
  typeof v['l'] === 'number';

/** Merge whatever was stored over the defaults; anything malformed falls back to the default. */
export function parseStored(raw: string | null, defaults: Stored): Stored {
  if (raw === null) return defaults;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return defaults;
  }
  if (!isObject(data) || data['v'] !== 1) return defaults;

  const out: Stored = structuredClone(defaults);
  const s = data['settings'];
  if (isObject(s)) {
    if (s['unit'] === 'c' || s['unit'] === 'f') out.settings.unit = s['unit'];
    if (s['language'] === 'en' || s['language'] === 'sl') out.settings.language = s['language'];
    if (s['theme'] === 'system' || s['theme'] === 'light' || s['theme'] === 'dark')
      out.settings.theme = s['theme'];
    if (s['motion'] === 'system' || s['motion'] === 'reduce' || s['motion'] === 'full')
      out.settings.motion = s['motion'];
    if (s['pattern'] === 'auto' || s['pattern'] === 'on' || s['pattern'] === 'off')
      out.settings.pattern = s['pattern'];
    if (typeof s['haptics'] === 'boolean') out.settings.haptics = s['haptics'];
    if (typeof s['sound'] === 'boolean') out.settings.sound = s['sound'];
    if (isChaseId(s['chase'])) out.settings.chase = s['chase'];
    if (typeof s['counts'] === 'boolean') out.settings.counts = s['counts'];
  }
  const best = data['bestEndless'];
  if (isRecord(best)) {
    out.bestEndless = { [DEFAULT_CHASE]: best }; // saved before chases existed: it was a sunshine record
  } else if (isObject(best)) {
    for (const [id, r] of Object.entries(best))
      if (isChaseId(id) && isRecord(r)) out.bestEndless[id] = r;
  }
  if (isObject(data['daily'])) {
    for (const [date, r] of Object.entries(data['daily'])) {
      if (
        /^\d{4}-\d{2}-\d{2}(:[a-z]+)?$/.test(date) &&
        isObject(r) &&
        Array.isArray(r['picks']) &&
        r['picks'].every((p) => typeof p === 'string') &&
        isRecord(r['record']) &&
        typeof r['grade'] === 'string'
      ) {
        out.daily[date] = {
          picks: r['picks'],
          ...(Array.isArray(r['rerolls']) && r['rerolls'].every((n) => typeof n === 'number')
            ? { rerolls: r['rerolls'] }
            : {}),
          record: r['record'],
          grade: r['grade'] as GradeId,
        };
      }
    }
  }
  const streak = data['streak'];
  if (
    isObject(streak) &&
    typeof streak['count'] === 'number' &&
    (typeof streak['last'] === 'string' || streak['last'] === null)
  ) {
    out.streak = { count: streak['count'], last: streak['last'] };
  }
  const runs = data['runs'];
  if (isObject(runs)) {
    for (const [id, n] of Object.entries(runs))
      if (isChaseId(id) && typeof n === 'number' && Number.isFinite(n) && n >= 0)
        out.runs[id] = Math.floor(n);
  }
  if (typeof data['onboarded'] === 'boolean') out.onboarded = data['onboarded'];
  return out;
}

export interface KeyValueStore {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
  removeItem: (key: string) => void;
}

/** The app's persistent state, kept in memory and mirrored to storage when it is available. */
export class Store {
  state: Stored;
  private readonly storage: KeyValueStore | undefined;

  constructor(defaults: Stored, storage: KeyValueStore | undefined) {
    this.storage = storage;
    let raw: string | null;
    try {
      raw = storage?.getItem(STORAGE_KEY) ?? null;
    } catch {
      raw = null;
    }
    // Always a copy, so two stores (or a test) never share and mutate the same defaults object.
    this.state = structuredClone(parseStored(raw, defaults));
  }

  save(): void {
    try {
      this.storage?.setItem(STORAGE_KEY, JSON.stringify(this.state));
    } catch {
      // Storage is full, blocked or private: keep playing from memory.
    }
  }

  update(change: (s: Stored) => void): void {
    change(this.state);
    this.save();
  }

  /** Record a finished daily run and move the streak on. */
  recordDaily(date: string, result: DailyResult, chase: ChaseId = DEFAULT_CHASE): void {
    this.update((s) => {
      const key = dailyKey(date, chase);
      if (s.daily[key]) return; // one attempt per day and chase: the first result stands
      s.daily[key] = result;
      s.runs[chase] = (s.runs[chase] ?? 0) + 1;
      s.streak = completeDaily(s.streak, date); // a daily of any chase keeps the streak
    });
  }

  recordEndless(record: DayRecord, chase: ChaseId = DEFAULT_CHASE): void {
    this.update((s) => {
      const best = s.bestEndless[chase];
      if (!best || record.w > best.w) s.bestEndless[chase] = record;
      s.runs[chase] = (s.runs[chase] ?? 0) + 1;
    });
  }

  /** Delete streak, results and best record; settings and the onboarding flag stay. */
  resetProgress(): void {
    this.update((s) => {
      s.bestEndless = {};
      s.daily = {};
      s.streak = { count: 0, last: null };
      s.runs = {};
    });
  }

  /** For tests and "storage unavailable" checks. */
  get persistent(): boolean {
    return this.storage !== undefined;
  }
}

/** localStorage if it works, otherwise undefined (private windows, blocked site data). */
export function browserStorage(): KeyValueStore | undefined {
  try {
    const probe = '365-0:probe';
    window.localStorage.setItem(probe, '1');
    window.localStorage.removeItem(probe);
    return window.localStorage;
  } catch {
    return undefined;
  }
}
