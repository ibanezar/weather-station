// Test strani »Nebo nocoj«: luna, presoja Kp/oblačnosti, roji (model).
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const M = require('../nebo-nocoj/nebo.js');
let bad = 0;
const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('NAPAKA', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
const near = (a, b, tol, m) => { if (Math.abs(a - b) > tol) { bad++; console.log('NAPAKA', m, a, 'ni blizu', b); } };
// znani mlaj 6. 1. 2000 18:14 UTC → osvetljenost ≈ 0; polna luna 21. 1. 2000 ≈ 1; 12. 12. 2026 je mlaj/prvi krajec območje?
near(M.moonIllum(Date.UTC(2000, 0, 6, 18, 14)), 0, 0.01, 'mlaj 2000');
near(M.moonIllum(Date.UTC(2000, 0, 21, 4, 40)), 1, 0.03, 'polna luna 21. 1. 2000');
near(M.moonIllum(Date.UTC(2026, 11, 24, 0, 0)), 1, 0.15, 'okoli polne lune 24. 12. 2026');
eq(M.kpVerdict(7).lvl, 'go', 'Kp 7'); eq(M.kpVerdict(6).lvl, 'edge', 'Kp 6'); eq(M.kpVerdict(5).lvl, 'no', 'Kp 5'); eq(M.kpVerdict(null).lvl, 'none', 'Kp null'); eq(/Kp 7,3\)/.test(M.kpVerdict(7.33).txt), true, 'Kp z vejico');
// NOAA Kp napoved: danes SEZNAM OBJEKTOV {time_tag, kp, ...} (19. 11. 2026: stran je brala samo seznam seznamov in Kp nikoli ni prišel do presoje); stara oblika z glavo še velja
{
  const now = Date.UTC(2026, 10, 19, 12, 0);
  const obj = [{ time_tag: '2026-11-19T09:00:00', kp: 1.33, observed: 'observed', noaa_scale: null },
               { time_tag: '2026-11-19T18:00:00', kp: '5.67', observed: 'predicted', noaa_scale: 'G1' },
               { time_tag: '2026-11-21T00:00:00', kp: 8, observed: 'predicted', noaa_scale: 'G4' },   // zunaj okna +24 h
               { time_tag: '2026-11-18T00:00:00', kp: 9, observed: 'observed', noaa_scale: null }];   // starejše od −3 h
  const arr = [['time_tag', 'kp', 'observed', 'noaa_scale'], ['2026-11-19 09:00:00', '1.33', 'observed', null], ['2026-11-19 18:00:00', '5.67', 'predicted', 'G1'], ['2026-11-21 00:00:00', '8', 'predicted', 'G4']];
  eq(M.kpMaxFrom(obj, now), 5.67, 'NOAA objekti (sedanja oblika)'); eq(M.kpMaxFrom(arr, now), 5.67, 'NOAA seznami z glavo (stara oblika)');
  eq(M.kpMaxFrom([], now), null, 'prazen seznam'); eq(M.kpMaxFrom(null, now), null, 'ni seznam'); eq(M.kpMaxFrom([{ time_tag: 'x', kp: 'y' }], now), null, 'neveljavne vrednosti');
  eq(M.kpMaxFrom([{ time_tag: '2026-11-19T11:00:00Z', kp: 6 }], now), 6, 'čas že z Z');
}
eq(M.cloudVerdict(10).lvl, 'go', 'jasno'); eq(M.cloudVerdict(30).lvl, 'edge', 'meja 30'); eq(M.cloudVerdict(69).lvl, 'edge', '69'); eq(M.cloudVerdict(70).lvl, 'no', 'meja 70');
eq(M.nightCloud([{ h: 12, c: 100 }, { h: 21, c: 10 }, { h: 3, c: 30 }, { h: 6, c: 100 }]), 20, 'samo nočne ure 20–5');
eq(M.nightCloud([{ h: 12, c: 50 }]), null, 'brez nočnih ur');
eq(M.auroraTonight(8, 10).go, true, 'sij: močan Kp + jasno');
eq(M.auroraTonight(8, 90).go, false, 'sij: oblačno');
eq(M.auroraTonight(4, 0).go, false, 'sij: nizek Kp');
eq(M.auroraTonight(null, 0).go, false, 'sij: brez Kp ne trdi možnosti');
// naslednji roj: 18. 11. 2026 → Geminidi 14. 12.; 20. 12. → Ursidi; 25. 12. → Kvadrantidi 3. 1. 2027; 15. 11. → Leonidi
const nm = t => M.nextShower(Date.UTC(...t)).s.id;
eq(nm([2026, 10, 18, 12]), 'geminidi', '18. 11. opoldne: Leonidi so že mimo, naslednji Geminidi');
eq(nm([2026, 10, 17, 12]), 'leonidi', '17. 11. opoldne: Leonidi še niso mimo');
eq(nm([2026, 11, 20, 12]), 'ursidi', '20. 12.: Ursidi');
eq(nm([2026, 11, 25, 12]), 'kvadrantidi', '25. 12.: Kvadrantidi 3. 1.');
eq(M.nextShower(Date.UTC(2026, 11, 25, 12)).t, Date.UTC(2027, 0, 3, 22), 'Kvadrantidi so v naslednjem letu');
eq(M.showerMoon(Date.UTC(2026, 11, 14, 22)).bad, false, 'Geminidi 2026: luna (blizu mlaja) ne moti');
eq(M.showerMoon(Date.UTC(2000, 0, 15, 22)).bad, true, 'luna 68 % moti');
eq(M.showerMoon(Date.UTC(2000, 0, 6, 22)).bad, false, 'mlaj ne moti');
eq(M.auroraTonight(6, 0).go, false, 'Kp 6 je mejno: ne trdi, da je sij možen');
console.log(bad ? bad + ' napak' : 'nebo: OK'); process.exit(bad ? 1 : 0);
