// Test žiga na fotografiji (model): dnevni zapis, vrstice, manjkajoči podatki, velikosti; vdelani niz proti history.json.
import { createRequire } from 'module';
import fs from 'fs';
const require = createRequire(import.meta.url);
const M = require('../vreme-na-fotografiji/zig.js');
let bad = 0;
const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('NAPAKA', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
const data = { start: '2026-01-30', t: [3.04, 5, null, -1.2], n: [-4.5, 0, 1, -8], p: [0, 2.3, 0, 0.1] };
eq(M.dayOf(data, '2026-01-30'), { t: 3.04, n: -4.5, p: 0 }, 'prvi dan');
eq(M.dayOf(data, '2026-02-01'), null, 'manjkajoča polja');
eq(M.dayOf({ start: '2026-01-01', t: [1], n: [null], p: [0] }, '2026-01-01'), null, 'manjka najnižja'); eq(M.dayOf({ start: '2026-01-01', t: [1], n: [0], p: [null] }, '2026-01-01'), null, 'manjkajo padavine');
eq(M.dayOf(data, '2026-01-29'), null, 'pred nizom'); eq(M.dayOf(data, '2026-02-03'), null, 'po nizu');
eq(M.lines(data, '2026-01-30'), ['30. 1. 2026 · Rečica ob Savinji', '−4,5 do 3,0 °C · brez padavin', 'IREICA1 · meteorec.si'], 'vrstice, minus in vejica');
eq(M.lines(data, '2026-01-31')[1], '0,0 do 5,0 °C · 2,3 mm', 'z dežjem');
eq(M.lines(data, '2026-02-02')[1], '−8,0 do −1,2 °C · 0,1 mm'.replace('0,1 mm', 'brez padavin') , 'padavine < 0,2 mm = brez');
eq(M.lines(data, '2025-01-01'), null, 'brez meritve žiga ne izmišljamo');
eq(M.metrics(100).fs, 14, 'najmanjša pisava'); eq(M.metrics(2800).fs, 100, 'pisava sledi širini');
const html = fs.readFileSync(new URL('../vreme-na-fotografiji/index.html', import.meta.url), 'utf8');
const D = JSON.parse(/id="zg-data">([\s\S]*?)<\/script>/.exec(html)[1]);
const hist = JSON.parse(fs.readFileSync(new URL('../history.json', import.meta.url), 'utf8')); const H = hist.days || hist;
const k = '2026-08-05', v = H[k]; const i = Math.round((Date.parse(k) - Date.parse(D.start)) / 864e5);
eq([D.t[i], D.n[i]], [Math.round(v.tempHigh * 10) / 10, Math.round(v.tempLow * 10) / 10], 'vdelan niz = history.json');
if (/indoor|tempinf/i.test(html)) { bad++; console.log('NAPAKA notranji ključi'); }
console.log(bad ? bad + ' napak' : 'zig: OK'); process.exit(bad ? 1 : 0);
