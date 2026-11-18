// Test napovedi sončne elektrarne (model): sanitizacija vhodov, dnevne vsote, manjkajoče ure, preostanek dneva.
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const M = require('../sonce-elektrarna/elektrarna.js');
let bad = 0;
const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('NAPAKA', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
const near = (a, b, m) => { if (Math.abs(a - b) > 1e-9) { bad++; console.log('NAPAKA', m, a, '!=', b); } };
eq(M.inputs({}), { kwp: 5, tilt: 35, az: 0, pr: 0.8 }, 'privzete vrednosti');
eq(M.inputs({ kwp: '7,5' }).kwp, 7.5, 'decimalna vejica'); eq(M.inputs({ kwp: -3 }).kwp, 0.1, 'kWp spodnja meja'); eq(M.inputs({ kwp: 1e6 }).kwp, 1000, 'kWp zgornja');
eq(M.inputs({ tilt: 120 }).tilt, 90, 'naklon ≤ 90'); eq(M.inputs({ az: 400 }).az, 180, 'azimut ≤ 180'); eq(M.inputs({ pr: 2 }).pr, 0.95, 'PR zgornja'); eq(M.inputs({ kwp: 'abc' }).kwp, 5, 'neveljavno → privzeto');
// 2 dni po 24 ur; 1000 W/m² za eno uro = 1 kWh/m² → × 5 kWp × 0,8 = 4 kWh
const times = []; const g = [];
for (let d = 0; d < 2; d++) for (let h = 0; h < 24; h++) { times.push('2026-06-0' + (1 + d) + 'T' + (h < 10 ? '0' : '') + h + ':00'); g.push(0); }
g[12] = 1000; g[24 + 12] = 500; g[24 + 13] = null;
const r = M.daily(times, g, 5, 0.8);
eq(r.length, 2, 'dva dneva'); near(r[0].kwh, 4, 'dan 1 = 4 kWh'); eq(r[0].incomplete, false, 'dan 1 popoln'); near(r[1].kwh, 2, 'dan 2 = 2 kWh'); eq(r[1].incomplete, true, 'dan 2 ima manjkajočo uro');
g[5] = -50; near(M.daily(times, g, 5, 0.8)[0].kwh, 4, 'negativno sevanje se šteje kot 0');
near(M.remainingToday(times, g, 5, 0.8, 13), 0, 'po 12. uri danes ni več sevanja'); near(M.remainingToday(times, g, 5, 0.8, 12), 4, 'od 12. ure vključno');
near(M.daily(times, g, 10, 0.8)[0].kwh, 8, 'sorazmerno z močjo');
console.log(bad ? bad + ' napak' : 'elektrarna: OK'); process.exit(bad ? 1 : 0);
