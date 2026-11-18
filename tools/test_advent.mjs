// Test adventnega koledarja: model (datumi, odpiranje) + vdelani podatki (24 vrat, brez praznih polj, števila iz history.json).
import { createRequire } from 'module';
import fs from 'fs';
const require = createRequire(import.meta.url);
const M = require('../adventni-koledar/advent.js');
let bad = 0;
const eq = (a, b, m) => { if (a !== b) { bad++; console.log('NAPAKA', m, a, '!=', b); } };
eq(M.openUpTo({ m: 11, d: 30 }), 0, 'pred 1. 12.');
eq(M.openUpTo({ m: 12, d: 1 }), 1, '1. 12.');
eq(M.openUpTo({ m: 12, d: 17 }), 17, '17. 12.');
eq(M.openUpTo({ m: 12, d: 24 }), 24, '24. 12.');
eq(M.openUpTo({ m: 12, d: 30 }), 24, 'po 24.');
eq(M.openUpTo({ m: 1, d: 5 }), 24, 'januar');
eq(M.openUpTo({ m: 6, d: 5 }), 0, 'junij');
eq(M.openUpTo({ m: 11, d: 1 }, 5), 5, 'preglasitev ?dan=');
eq(M.openUpTo({ m: 11, d: 1 }, 99), 24, 'preglasitev omejena');
eq(M.ljDate(new Date('2026-12-01T23:30:00Z')).d, 2, 'Ljubljana je že 2. 12. ob 23:30 UTC');
const html = fs.readFileSync(new URL('../adventni-koledar/index.html', import.meta.url), 'utf8');
const data = JSON.parse(/id="adv-data">([\s\S]*?)<\/script>/.exec(html)[1]);
eq(Object.keys(data).length, 24, '24 vrat');
for (let d = 1; d <= 24; d++) {
  const r = data[d];
  if (!r || !r.h || !r.t || !r.p || /undefined|NaN|null|\d\.\d/.test(r.h + r.t + r.p)) { bad++; console.log('NAPAKA vrata', d, r); }
}
const hist = JSON.parse(fs.readFileSync(new URL('../history.json', import.meta.url), 'utf8')); const H = hist.days || hist;
// vrata 1 = »cold«: najnižja najnižja temperatura 1. 12. po letih brez ERA5
let mn = 99; for (const [k, v] of Object.entries(H)) if (k.slice(5) === '12-01' && v.src !== 'era5' && v.tempLow != null) mn = Math.min(mn, v.tempLow);
eq(data[1].h, mn.toFixed(1).replace('.', ',').replace('-', '−') + ' °C', 'vrata 1 = izmerjen minimum');
console.log(bad ? `${bad} napak` : 'advent: OK'); process.exit(bad ? 1 : 0);
