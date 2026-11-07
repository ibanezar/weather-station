import en from './en.json';
import sl from './sl.json';

export type MessageKey = keyof typeof en;
export type Locale = 'en' | 'sl';
export const LOCALES: readonly Locale[] = ['en', 'sl'];

const catalogs: Record<Locale, Record<string, string>> = { en, sl };

/** Pick a supported locale from a browser language tag, defaulting to English. */
export function resolveLocale(tag: string | undefined): Locale {
  return tag?.toLowerCase().startsWith('sl') ? 'sl' : 'en';
}

export type Params = Record<string, string | number>;

function fill(text: string, params?: Params): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => {
    const v = params[name];
    return v === undefined ? whole : String(v);
  });
}

/** Plural keys are written key.one / key.two / key.few / key.other (CLDR categories). */
export type PluralKey = {
  [K in MessageKey]: K extends `${infer Base}.other` ? Base : never;
}[MessageKey];

export interface I18n {
  locale: Locale;
  /** Translate a key; `{name}` placeholders are filled from params. */
  t: (key: MessageKey, params?: Params) => string;
  /** Translate a plural key for the count n, using Intl.PluralRules (Slovene has dual forms). */
  plural: (key: PluralKey, n: number, params?: Params) => string;
}

export function createI18n(locale: Locale): I18n {
  const catalog = catalogs[locale];
  const rules = new Intl.PluralRules(locale);
  const lookup = (key: string): string => {
    const text = catalog[key] ?? catalogs.en[key];
    if (text === undefined) throw new Error(`missing translation ${key}`);
    return text;
  };
  return {
    locale,
    t: (key, params) => fill(lookup(key), params),
    plural: (key, n, params) => {
      const category = rules.select(n);
      const text =
        catalog[`${key}.${category}`] ?? catalog[`${key}.other`] ?? lookup(`${key}.other`);
      return fill(text, { n, ...params });
    },
  };
}

/** Kept for the placeholder screen and older callers. */
export function translate(locale: Locale, key: MessageKey): string {
  return createI18n(locale).t(key);
}
