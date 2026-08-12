#!/usr/bin/env node
/**
 * Fails if the locale files don't all declare the same set of keys.
 *
 * The architecture audit found en.json/ru.json in sync (593 keys each) but
 * kk.json silently drifted to 576, with real structural divergence (its
 * `systemSettings.backup` section held a different, non-overlapping set of
 * keys than the English/Russian ones — not just missing translations, a
 * different schema someone wrote once and never reconciled). Nothing
 * caught that until a human happened to read all three files side by
 * side. This runs in CI (see .github/workflows/ci.yml) so the next
 * divergence fails the build instead of shipping silently.
 */
import { readFileSync, readdirSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = join(__dirname, '..', 'src', 'i18n', 'locales');

function flatten(obj, prefix = '') {
  const keys = new Set();
  for (const [key, value] of Object.entries(obj)) {
    const full = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      for (const k of flatten(value, full)) keys.add(k);
    } else {
      keys.add(full);
    }
  }
  return keys;
}

const localeFiles = readdirSync(LOCALES_DIR).filter((f) => f.endsWith('.json'));

if (localeFiles.length < 2) {
  console.log(`Only ${localeFiles.length} locale file(s) found — nothing to compare.`);
  process.exit(0);
}

const keysByLocale = {};
for (const file of localeFiles) {
  const locale = file.replace(/\.json$/, '');
  const content = JSON.parse(readFileSync(join(LOCALES_DIR, file), 'utf-8'));
  keysByLocale[locale] = flatten(content);
}

const [baseLocale, ...otherLocales] = Object.keys(keysByLocale).sort();
const baseKeys = keysByLocale[baseLocale];

let hasMismatch = false;

for (const locale of otherLocales) {
  const keys = keysByLocale[locale];
  const missing = [...baseKeys].filter((k) => !keys.has(k)).sort();
  const extra = [...keys].filter((k) => !baseKeys.has(k)).sort();

  if (missing.length === 0 && extra.length === 0) {
    console.log(`✓ ${locale}.json matches ${baseLocale}.json (${keys.size} keys)`);
    continue;
  }

  hasMismatch = true;
  console.error(`✗ ${locale}.json (${keys.size} keys) does not match ${baseLocale}.json (${baseKeys.size} keys)`);
  if (missing.length > 0) {
    console.error(`  Missing in ${locale}.json (${missing.length}):`);
    for (const k of missing) console.error(`    - ${k}`);
  }
  if (extra.length > 0) {
    console.error(`  Extra in ${locale}.json, not in ${baseLocale}.json (${extra.length}):`);
    for (const k of extra) console.error(`    + ${k}`);
  }
}

if (hasMismatch) {
  console.error('\ni18n key check failed.');
  process.exit(1);
}

console.log('\nAll locale files have matching key sets.');
