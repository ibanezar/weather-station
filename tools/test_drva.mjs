/*
 * tools/test_drva.mjs — model kalkulatorja drv (zima/poraba-drv/drva.js) in vdelani podatki na generirani strani.
 * Poganjanje: node tools/test_drva.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const M = createRequire(import.meta.url)(path.join(ROOT, 'zima', 'poraba-drv', 'drva.js'));
let fails = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };
const near = (a, b, e = 1e-6) => Math.abs(a - b) < e;

check(M.dayIndex('2026-10-01') === 0 && M.dayIndex('2026-11-17') === 47 && M.dayIndex('2026-12-31') === 91 && M.dayIndex('2027-01-01') === 92, 'dayIndex: od 1. 10. (jesen in januar)');
check(M.dayIndex('2027-04-30') === 211 && M.dayIndex('2027-05-01') === -1 && M.dayIndex('2026-09-30') === -1, 'dayIndex: konec sezone 211, maj–september −1');

const curve = [10, 20, 30];
check(M.remaining(curve, 30, 0) === 30 && M.remaining(curve, 30, 1) === 20 && M.remaining(curve, 30, 3) === 0, 'remaining: od 1. 10. cela, vmes odštete, na koncu 0');
check(M.remaining(curve, 30, 4) === 0 && M.remaining(curve, 30, -1) === 30, 'remaining: po koncu sezone 0, pred njo cela');

const data = { curves: { a: [10, 30], b: [20, 40], c: [5, 10] }, totals: { a: 30, b: 40, c: 10 } };
const sc = M.scenarios(data, 1);
check(sc.topla.leto === 'c' && sc.hladna.leto === 'b', 'scenarios: najtoplejša in najhladnejša po seštevku');
check(near(sc.povp.total, 80 / 3) && near(sc.povp.rem, 15) && sc.topla.rem === 5 && sc.hladna.rem === 20, 'scenarios: povprečje in preostanek po sezonah');

check(near(M.modeA(10, 2877, 0, 2565, 1), 10 * 2565 / 2877), 'modeA: sorazmerno s stopinjskimi dnevi');
check(near(M.modeA(10, 2877, 1, 1, 1), 10) && near(M.modeA(10, 2877, 0.2, 2877, 1), 10), 'modeA: ista sezona = ista poraba (tudi s stalnim deležem)');
check(near(M.modeA(10, 2877, 0.2, 1000, 0.5), 10 * (0.1 + 0.8 * 1000 / 2877)), 'modeA: stalni del se pri »od danes« razdeli po deležu sezone');
check(near(M.modeB(120, 150, 0.75, 2000, 2920, 2920), 12), 'modeB: 120 m² × 150 kWh / 0,75 / 2000 kWh = 12 prm');
check(near(M.modeB(120, 150, 0.75, 2000, 3281, 2920), 12 * 3281 / 2920) && near(M.modeB(120, 150, 0.5, 2000, 2920, 2920), 18), 'modeB: hladnejša zima in slabši izkoristek povečata porabo');
check(near(M.withReserve(10, 10), 11) && M.fmt(1234.5678, 1) === '1234,6' && M.fmt(3, 0) === '3', 'withReserve in fmt (decimalna vejica)');

// vdelani podatki na generirani strani
const html = fs.readFileSync(path.join(ROOT, 'zima', 'poraba-drv', 'index.html'), 'utf8');
const D = JSON.parse(html.match(/id="drva-data">(.*?)<\/script>/s)[1].replace(/<\\\//g, '</'));
check(JSON.stringify(Object.values(D.totals)) === '[3156,3281,2781,2565,2817]' && D.totalsAll['2025'] === 2877 && Math.round(D.mean) === 2920, 'vdelani podatki: seštevki sezon enaki kot v članku o stopinjskih dneh');
check(Object.entries(D.curves).every(([y, c]) => Math.round(c[c.length - 1]) === D.totals[y] && c.every((v, i) => i === 0 || v >= c[i - 1])), 'vdelane krivulje: naraščajoče, zadnja vrednost = seštevek');
check(Object.values(D.curves).every(c => c.length === 212 || c.length === 213), 'vdelane krivulje: 212 oz. 213 dni (prestopno leto)');
check(!/indoor/i.test(html), 'stran ne omenja notranjih meritev');
process.exit(fails ? 1 : 0);
