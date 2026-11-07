import { describe, expect, it } from 'vitest';
import en from '../../src/i18n/en.json';
import sl from '../../src/i18n/sl.json';
import { resolveLocale, translate } from '../../src/i18n/index.ts';

describe('i18n catalogs', () => {
  it('en and sl define exactly the same keys', () => {
    expect(Object.keys(sl).sort()).toEqual(Object.keys(en).sort());
  });

  it('has no empty strings', () => {
    for (const catalog of [en, sl]) {
      for (const value of Object.values(catalog)) expect(value.trim()).not.toBe('');
    }
  });

  it('resolves locales with an English default', () => {
    expect(resolveLocale('sl-SI')).toBe('sl');
    expect(resolveLocale('en-GB')).toBe('en');
    expect(resolveLocale('de')).toBe('en');
    expect(resolveLocale(undefined)).toBe('en');
    expect(translate('sl', 'app.title')).toBe('365-0');
  });
});
