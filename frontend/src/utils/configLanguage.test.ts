import { describe, it, expect } from 'vitest';
import { getConfigLanguage, getConfigLanguageName } from './configLanguage';

describe('getConfigLanguage', () => {
  it('maps known vendors to their Monaco language', () => {
    expect(getConfigLanguage('cisco')).toBe('shell');
    expect(getConfigLanguage('juniper')).toBe('xml');
    expect(getConfigLanguage('paloalto')).toBe('xml');
  });

  it('is case-insensitive', () => {
    expect(getConfigLanguage('Cisco')).toBe('shell');
    expect(getConfigLanguage('JUNIPER')).toBe('xml');
  });

  it('falls back to plaintext for an unknown vendor', () => {
    expect(getConfigLanguage('some-unknown-vendor')).toBe('plaintext');
  });

  it('falls back to plaintext for an empty/falsy vendor', () => {
    expect(getConfigLanguage('')).toBe('plaintext');
  });
});

describe('getConfigLanguageName', () => {
  it('maps known vendors to a human-readable name', () => {
    expect(getConfigLanguageName('cisco')).toBe('Cisco IOS');
    expect(getConfigLanguageName('mikrotik')).toBe('MikroTik RouterOS');
  });

  it('falls back to "Plain Text" for an unknown vendor', () => {
    expect(getConfigLanguageName('some-unknown-vendor')).toBe('Plain Text');
  });
});
