import { describe, expect, it } from 'vitest';
import en from '../../src/i18n/en.json';
import sl from '../../src/i18n/sl.json';
import eventsJson from '../../data/events.json';
import { createI18n, resolveLocale, translate, type MessageKey } from '../../src/i18n/index.ts';
import { ARCHETYPES } from '../../src/data/types.ts';
import { GRADE_IDS } from '../../src/engine/grades.ts';

const CATEGORY = /\.(zero|one|two|few|many|other)$/;
const catalogs = { en: en as Record<string, string>, sl: sl as Record<string, string> };

/** Keys without the plural category, so the two languages can have different numbers of forms. */
const bases = (c: Record<string, string>): string[] => [
  ...new Set(Object.keys(c).map((k) => k.replace(CATEGORY, ''))),
];

describe('i18n catalogs', () => {
  it('en and sl define the same messages (plural forms aside)', () => {
    expect(bases(catalogs.sl).sort()).toEqual(bases(catalogs.en).sort());
  });

  it('has no empty strings', () => {
    for (const catalog of Object.values(catalogs)) {
      for (const value of Object.values(catalog)) expect(value.trim()).not.toBe('');
    }
  });

  it('gives every plural message all the forms its language needs', () => {
    for (const [locale, catalog] of Object.entries(catalogs)) {
      const needed = new Intl.PluralRules(locale).resolvedOptions().pluralCategories;
      const pluralBases = [
        ...new Set(
          Object.keys(catalog)
            .filter((k) => CATEGORY.test(k))
            .map((k) => k.replace(CATEGORY, '')),
        ),
      ];
      for (const base of pluralBases) {
        for (const category of needed) {
          expect(catalog[`${base}.${category}`], `${locale} ${base}.${category}`).toBeDefined();
        }
      }
    }
  });

  it('uses the same placeholders in both languages', () => {
    const placeholders = (s: string): string[] =>
      [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1] ?? '').sort();
    for (const [key, text] of Object.entries(catalogs.en)) {
      const sl = catalogs.sl[key];
      if (sl !== undefined) expect(placeholders(sl), key).toEqual(placeholders(text));
    }
  });

  it('has a name for every grade, archetype and event, in both languages', () => {
    for (const catalog of Object.values(catalogs)) {
      for (const g of GRADE_IDS) expect(catalog[`grade.${g}`], g).toBeDefined();
      for (const a of ARCHETYPES) expect(catalog[`archetype.${a}`], a).toBeDefined();
      for (const e of eventsJson) {
        expect(catalog[`event.${e.id}.name`], e.id).toBeDefined();
        expect(catalog[`event.${e.id}.blurb`], e.id).toBeDefined();
      }
    }
  });

  it('keeps the English event text in data/events.json in step with the catalog', () => {
    for (const e of eventsJson) {
      expect(en[`event.${e.id}.name` as MessageKey]).toBe(e.name);
      expect(en[`event.${e.id}.blurb` as MessageKey]).toBe(e.blurb);
    }
  });
});

describe('i18n functions', () => {
  it('resolves locales with an English default', () => {
    expect(resolveLocale('sl-SI')).toBe('sl');
    expect(resolveLocale('en-GB')).toBe('en');
    expect(resolveLocale('de')).toBe('en');
    expect(resolveLocale(undefined)).toBe('en');
    expect(translate('sl', 'app.title')).toBe('365-0');
  });

  it('fills placeholders and leaves unknown ones visible', () => {
    const i = createI18n('en');
    expect(i.t('draft.round', { current: 3, total: 12 })).toBe('Round 3 of 12');
    expect(i.t('draft.round', { current: 3 })).toBe('Round 3 of {total}');
  });

  it('chooses English plural forms', () => {
    const i = createI18n('en');
    expect(i.plural('draft.scoutsLeft', 1)).toBe('1 scout left');
    expect(i.plural('draft.scoutsLeft', 0)).toBe('0 scouts left');
    expect(i.plural('draft.scoutsLeft', 3)).toBe('3 scouts left');
  });

  it('chooses Slovene plural forms, including the dual', () => {
    const i = createI18n('sl');
    expect(i.plural('home.streak', 1)).toBe('1 dan zapored');
    expect(i.plural('home.streak', 2)).toBe('2 dneva zapored');
    expect(i.plural('home.streak', 3)).toBe('3 dni zapored');
    expect(i.plural('home.streak', 4)).toBe('4 dni zapored');
    expect(i.plural('home.streak', 5)).toBe('5 dni zapored');
    expect(i.plural('home.streak', 101)).toBe('101 dan zapored');
    expect(i.plural('home.streak', 102)).toBe('102 dneva zapored');
  });
});
