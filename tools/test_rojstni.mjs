// Test rojstnodnevnega vremena: model + vdelani podatki proti history.json.
import { createRequire } from 'module';
import fs from 'fs';
const require = createRequire(import.meta.url);
const M = require('../rojstnodnevno-vreme/rojstni.js');
let bad = 0;
const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('NAPAKA', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
// sintetični niz: 2020-02-27 .. 2021-03-02 (prestopno leto 2020)
const start = '2020-02-27', t = [], n = [], p = [];
for (let i = 0; i < 400; i++) { t.push(10 + i * 0.01); n.push(i * 0.01); p.push(i % 7 === 0 ? 2 : 0); }
n[2] = null; // 29. 2. 2020 je indeks 2: manjkajoča meritev
const data = { start, t, n, p };
eq(M.byDate(data, 2, 29).length, 0, '29. 2. z manjkajočim poljem odpade');
eq(M.byDate(data, 2, 28).map(r => r.y), [2020, 2021], '28. 2. v obeh letih (niz sega do marca 2021)');
eq(M.byDate(data, 3, 1).map(r => r.y), [2020, 2021], '1. 3. v obeh letih');
eq(M.validDate(2, 29), true, '29. 2. je veljaven koledarski dan'); eq(M.validDate(2, 30), false, '30. 2.'); eq(M.validDate(4, 31), false, '31. 4.'); eq(M.validDate(13, 1), false, 'mesec 13');
const rows = M.byDate(data, 3, 1);
const s = M.summary(rows, 2021); eq(s.exact.y, 2021, 'točno leto'); eq(s.n, 2, 'število let');
eq(M.summary(rows, 1999).exact, null, 'leto pred meritvami nima točnega zapisa');
eq(M.summary([], 2020), null, 'prazno');
eq(s.warm.y, 2021, 'najtoplejše je novejše leto (t narašča)'); eq(s.cold.y, 2020, 'najhladneje je starejše leto (n narašča)');
// vdelani podatki proti history.json
const html = fs.readFileSync(new URL('../rojstnodnevno-vreme/index.html', import.meta.url), 'utf8');
const D = JSON.parse(/id="rd-data">([\s\S]*?)<\/script>/.exec(html)[1]);
const hist = JSON.parse(fs.readFileSync(new URL('../history.json', import.meta.url), 'utf8')); const H = hist.days || hist;
let cnt = 0;
for (const [k, v] of Object.entries(H)) {
  if (v.src === 'era5') continue;
  const i = Math.round((Date.parse(k) - Date.parse(D.start)) / 864e5);
  if (i < 0 || i >= D.t.length) { bad++; console.log('NAPAKA izven niza', k); continue; }
  const full = v.tempHigh != null && v.tempLow != null && v.precipTotal != null;
  if (full ? (D.t[i] !== Math.round(v.tempHigh * 10) / 10 || D.n[i] !== Math.round(v.tempLow * 10) / 10) : D.t[i] !== null) { bad++; console.log('NAPAKA vrednost', k); }
  cnt++;
}
if (cnt < 2000) { bad++; console.log('premalo dni', cnt); }
if (/indoor|tempinf/i.test(html)) { bad++; console.log('NAPAKA notranji ključi'); }
console.log(bad ? bad + ' napak' : 'rojstni: OK'); process.exit(bad ? 1 : 0);
