// Locale-aware formatting: temperatures in the player's unit, month, country and city names, dates.
import type { SeedCity } from '../data/types.ts';
import type { DayRecord } from '../engine/types.ts';
import type { Locale } from '../i18n/index.ts';
import type { Unit } from './storage.ts';

export interface Formatter {
  /** "11°" in the player's unit. */
  temperature: (celsius: number) => string;
  /** "19–28 °C" or "66–82 °F". */
  range: (lowC: number, highC: number) => string;
  /** January, in sentence case, in the player's language. */
  month: (index: number) => string;
  country: (code: string) => string;
  cityName: (city: SeedCity) => string;
  /** Three letters for a month column: "Sin". */
  abbreviation: (city: SeedCity) => string;
  /** "6 November" */
  date: (isoDate: string) => string;
  record: (r: DayRecord) => string;
  /** "7 h 12 min" */
  duration: (ms: number) => string;
}

const toF = (c: number): number => (c * 9) / 5 + 32;
const capitalize = (s: string): string => s.charAt(0).toLocaleUpperCase() + s.slice(1);

export function createFormatter(locale: Locale, unit: Unit): Formatter {
  const months = new Intl.DateTimeFormat(locale, { month: 'long', timeZone: 'UTC' });
  const dates = new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'long', timeZone: 'UTC' });
  const regions = new Intl.DisplayNames([locale], { type: 'region' });
  const convert = (c: number): number => Math.round(unit === 'f' ? toF(c) : c);
  return {
    temperature: (c) => `${String(convert(c))}°`,
    range: (lo, hi) => `${String(convert(lo))}–${String(convert(hi))} °${unit.toUpperCase()}`,
    month: (i) => capitalize(months.format(Date.UTC(2021, i, 1))),
    country: (code) => regions.of(code) ?? code,
    cityName: (c) => (locale === 'sl' ? (c.name.sl ?? c.name.en) : c.name.en),
    abbreviation: (c) => {
      const name = locale === 'sl' ? (c.name.sl ?? c.name.en) : c.name.en;
      return name.replace(/[^\p{L}]/gu, '').slice(0, 3);
    },
    date: (iso) => {
      const [y, m, d] = iso.split('-').map(Number) as [number, number, number];
      return dates.format(Date.UTC(y, m - 1, d));
    },
    record: (r) => `${String(r.w)}-${String(r.d)}-${String(r.l)}`,
    duration: (ms) => {
      const minutes = Math.max(0, Math.ceil(ms / 60000));
      return `${String(Math.floor(minutes / 60))} h ${String(minutes % 60)} min`;
    },
  };
}
