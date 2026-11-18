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
console.log(bad ? bad + ' napak' : 'nebo: OK'); process.exit(bad ? 1 : 0);
