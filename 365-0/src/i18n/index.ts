import en from './en.json';
import sl from './sl.json';

export type MessageKey = keyof typeof en;
export type Locale = 'en' | 'sl';

const catalogs: Record<Locale, Record<MessageKey, string>> = { en, sl };

/** Pick a supported locale from a browser language tag, defaulting to English. */
export function resolveLocale(tag: string | undefined): Locale {
  return tag?.toLowerCase().startsWith('sl') ? 'sl' : 'en';
}

export function translate(locale: Locale, key: MessageKey): string {
  return catalogs[locale][key];
}
