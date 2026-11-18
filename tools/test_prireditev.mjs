/*
 * tools/test_prireditev.mjs — model strani »Vreme za poroko in prireditve« (vreme-za-prireditev/prireditev.js)
 * in skladnost vdelanih podatkov z history.json. Poganjanje: node tools/test_prireditev.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const M = createRequire(import.meta.url)(path.join(ROOT, 'vreme-za-prireditev', 'prireditev.js'));
let fails = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };
const near = (a, b, e = 1e-9) => Math.abs(a - b) < e;

// umetni podatki: 3 leta (2024 prestopno), vsak dan t=20, n=10, p=0; izjeme spodaj
const start = '2023-01-01', N = 365 + 366 + 365;
const t = Array(N).fill(20), n = Array(N).fill(10), p = Array(N).fill(0);
const idx = (iso) => Math.round((Date.parse(iso + 'T00:00:00Z') - Date.parse(start + 'T00:00:00Z')) / 86400000);
p[idx('2023-06-15')] = 5; p[idx('2024-06-16')] = 0.1; p[idx('2025-06-14')] = 0.2; t[idx('2023-06-14')] = 35;
t[idx('2024-06-10')] = null;                                     // manjkajoč podatek: dan se ne šteje
const map = M.buildDays({ start, t, n, p });
const crit = { rain: 0.2, tmaxLo: 18, tmaxHi: 30, nmin: null };
check(Object.keys(map).length === N - 1, 'buildDays: dan z manjkajočim podatkom izpuščen');
check(M.ok({ t: 20, n: 10, p: 0.1 }, crit) && !M.ok({ t: 20, n: 10, p: 0.2 }, crit), 'ok: padavine strogo pod pragom (0,2 mm ni primerno)');
check(M.ok({ t: 18, n: 0, p: 0 }, crit) && M.ok({ t: 30, n: 0, p: 0 }, crit) && !M.ok({ t: 17.9, n: 0, p: 0 }, crit) && !M.ok({ t: 30.1, n: 0, p: 0 }, crit), 'ok: meji najvišje temperature sta vključeni');
check(!M.ok({ t: 20, n: 8, p: 0 }, { ...crit, nmin: 9 }) && M.ok({ t: 20, n: 9, p: 0 }, { ...crit, nmin: 9 }), 'ok: najnižja temperatura ≥ meja');
const s = M.share(map, 6, 15, 1, crit);
// leta 2023, 2024, 2025: okno 14.–16. 6. = 9 dni; neprimerni: 2023-06-14 (35 °C), 2023-06-15 (5 mm), 2025-06-14 (0,2 mm); 2024-06-16 (0,1 mm) je primeren
check(s.n === 9 && s.k === 6 && near(s.p, 6 / 9) && s.per.length === 3, 'share: 6 od 9 dni, 3 leta');
check(M.share(map, 6, 10, 0, crit).n === 2 && M.share(map, 6, 10, 0, crit).k === 2, 'share: izpuščen dan se ne šteje (2024-06-10), ostali leti prideta');
const leap = M.share(map, 2, 29, 0, crit);
check(leap.n === 1 && leap.per.length === 1 && leap.per[0].y === 2024, 'share: 29. 2. obstaja samo v prestopnem letu');
check(M.share(map, 6, 15, 7, crit).n === 3 * 15 - 1, 'share: okno ±7 = 15 dni na leto (minus manjkajoči 10. 6. 2024)');
const ex = M.exact(map, 6, 15, crit);
check(ex.length === 3 && ex[0].y === 2023 && ex[0].p === 5 && ex[0].ok === false && ex[1].ok === true, 'exact: po letih, s primernostjo');
const [lo, hi] = M.wilson(6, 9);
check(lo < 6 / 9 && hi > 6 / 9 && lo > 0.3 && hi < 0.95, 'wilson: interval obdaja delež');
check(M.wilson(0, 0)[0] === null && M.wilson(10, 10)[1] === 1, 'wilson: brez podatkov null, 10/10 zgoraj 1');
const bs = M.best(map, 6, 15, 3, 0, crit, 3);
check(bs.length === 3 && bs[0].p === 1 && Math.abs(bs[0].off) <= Math.abs(bs[1].off) + 3 && bs.every(x => x.p <= 1), 'best: najboljši po deležu, tri');
// izenačenje: bližji izbranemu datumu pride prej
const tie = M.best(M.buildDays({ start: '2023-01-01', t: Array(365).fill(20), n: Array(365).fill(10), p: Array(365).fill(0) }), 6, 15, 5, 0, crit, 3);
check(tie[0].off === 0 && Math.abs(tie[1].off) === 1, 'best: pri izenačenju bližji datum prej');
check(M.fmt(12.345, 1) === '12,3' && M.fmt(-3.6, 1) === '\u20133,6' && M.dm(6, 5) === '5. 6.', 'fmt (decimalna vejica, negativne z dolgim pomišljajem), dm');

// vdelani podatki ↔ history.json
const html = fs.readFileSync(path.join(ROOT, 'vreme-za-prireditev', 'index.html'), 'utf8');
const D = JSON.parse(html.match(/id="pr-data">(.*?)<\/script>/s)[1].replace(/<\\\//g, '</'));
const H = JSON.parse(fs.readFileSync(path.join(ROOT, 'history.json'), 'utf8')); const days = H.days || H;
const t0 = Date.parse(D.start + 'T00:00:00Z');
let diffs = 0, checked = 0, eraSkipped = 0;
for (const [k, v] of Object.entries(days)) {
  const i = Math.round((Date.parse(k + 'T00:00:00Z') - t0) / 86400000);
  if (v.src === 'era5') { eraSkipped++; if (D.t[i] != null) diffs++; continue; }
  if (v.tempHigh == null || v.tempLow == null || v.precipTotal == null) { if (D.t[i] != null) diffs++; continue; }
  checked++;
  if (!near(D.t[i], Math.round(v.tempHigh * 10) / 10, 0.051) || !near(D.n[i], Math.round(v.tempLow * 10) / 10, 0.051) || !near(D.p[i], Math.round(v.precipTotal * 10) / 10, 0.051)) diffs++;
}
check(checked > 2400 && diffs === 0, `vdelani podatki: ${checked} dni enakih history.json (zaokroženo na 0,1), dnevi ERA5 izpuščeni (${eraSkipped}), razlik: ${diffs}`);
check(D.t.length === D.n.length && D.n.length === D.p.length, 'vdelani podatki: enako dolgi nizi');
check(!/indoor/i.test(html), 'stran ne omenja notranjih meritev');
process.exit(fails ? 1 : 0);
