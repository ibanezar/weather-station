/*
 * tools/test_crnivec_igra.mjs — enotni testi modela igre »Čez Črnivec«
 * (crnivec-igra/voznja.js, crnivec.si/igra/).
 *
 * Zakaj obstaja: igra obljublja, da jo poganjajo prave razmere na cesti in da
 * je odločitev o verigah res odločitev. To se da izmeriti z vozniki-roboti:
 * na suhem mora biti brez verig hitreje, na ledu mora biti z verigami hitreje
 * (in brez njih mora prehiter voznik končati v jarku). Če ta test pade, igra
 * ni več to, kar piše na strani. Isti pristop kot tools/test_igra.mjs.
 *
 * Brez odvisnosti. Zaženi:  node tools/test_crnivec_igra.mjs
 */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const M = require(path.join(ROOT, 'crnivec-igra', 'voznja.js'));

let failed = 0;
function ok(name, cond, detail) {
  if (cond) { console.log(`  ✓ ${name}`); return; }
  failed++;
  console.log(`  ✗ ${name}${detail ? '  — ' + detail : ''}`);
}

// Sintetični nivo: vsi odseki z isto površino (profil je približek pravega).
const PROFIL = [[0, 430], [11.5, 902], [24.5, 428]];
function zKm(km) {
  for (let i = 1; i < PROFIL.length; i++) {
    const [k0, z0] = PROFIL[i - 1], [k1, z1] = PROFIL[i];
    if (km <= k1) return z0 + (z1 - z0) * (km - k0) / (k1 - k0);
  }
  return PROFIL[PROFIL.length - 1][1];
}
function nivo(povrsina, extra = {}) {
  const odseki = [];
  for (let km = 0; km < 24.5; km++) {
    odseki.push({ od_km: km, z_od: zKm(km), z_do: zKm(Math.min(24.5, km + 1)), povrsina,
      led_delez: povrsina === 'led' ? 1 : 0, megla: false, ...(extra.odsek || {}) });
  }
  return { datum: '2026-01-15', odseki, sunki_kmh: extra.sunki_kmh || null };
}

// Voznik-robot. `mu` je oprijem, na katerega računa (previden voznik vzame
// pravega, predrzen suhega). Gleda 70 m naprej in zavira pravočasno.
function bot(sim, { mu, rezerva = 0.8, verige = false } = {}) {
  if (verige) M.menjajVerige(sim);
  let n = 0;
  const dt = 1 / 120;
  while (!sim.done && n < 120 * 900) {
    const muR = mu == null ? M.muAt(sim, sim.s) : mu;
    let vCilj = sim.verige ? M.VMAX_VERIGE : M.VMAX;
    for (let a = 0; a < 70; a += 2) {
      const k = M.kAt(sim, sim.s + a);
      const muA = mu == null ? M.muAt(sim, sim.s + a) : mu;
      const vk = M.varnaHitrost(muA * rezerva, k);
      // hitrost, s katere lahko do tja še zaviramo
      const vz = Math.sqrt(vk * vk + 2 * Math.min(M.BRAKE, muR * M.G) * 0.7 * a);
      vCilj = Math.min(vCilj, vz);
    }
    // Volan mora sam slediti cesti (avto ne zavije brez njega): ukrivljenost
    // ceste malo naprej + popravek odmika in smeri.
    const kNaprej = M.kAt(sim, sim.s + Math.max(2, sim.v * 0.25));
    const volan = Math.max(-1, Math.min(1, (kNaprej - 0.05 * sim.d - 0.3 * sim.psi) / M.KMAX));
    M.step(sim, { plin: sim.v < vCilj - 0.3 ? 1 : 0, zavora: sim.v > vCilj + 0.3 ? 1 : 0, volan }, dt);
    n++;
  }
  return sim;
}

console.log('Proga');
const t1 = M.buildTrack(), t2 = M.buildTrack();
ok('proga je deterministična', t1.k.every((v, i) => v === t2.k[i]));
ok('dolžina proge ustreza 24,5 km', t1.L === Math.round(24500 / M.SCALE));
const tight = Array.from(t1.k).filter((k) => Math.abs(k) > 1 / 25).length;
ok('pod vrhom so serpentine', tight > 200, `metrov serpentin: ${tight}`);

console.log('Površine');
const mix = nivo('led', { odsek: { led_delez: 0.3 } });
const sm = M.makeSim(mix);
const nLed = Array.from(sm.surf).filter((c) => c === 3).length;
const delez = nLed / sm.surf.length;
ok('»ponekod led« je res ponekod (15–45 %)', delez > 0.15 && delez < 0.45, `delež ${delez.toFixed(2)}`);
const sm2 = M.makeSim(mix);
ok('led je isti dan na istem mestu', sm.surf.every((v, i) => v === sm2.surf[i]));
const mix3 = { ...mix, datum: '2026-01-16' };
ok('drug dan je led drugje', !M.makeSim(mix3).surf.every((v, i) => v === sm.surf[i]));

console.log('Suho');
const suho = nivo('suho');
const sBrez = bot(M.makeSim(suho), { mu: null });
const sZ = bot(M.makeSim(suho), { mu: null, verige: true });
ok('previden voznik pride čez brez jarka', sBrez.done && sBrez.jarki === 0, `jarki ${sBrez.jarki}`);
ok('čas na suhem je 2–4 minute', sBrez.t > 120 && sBrez.t < 240, `t=${sBrez.t.toFixed(1)}`);
ok('na suhem so verige počasnejše', M.koncniCas(sZ) > M.koncniCas(sBrez) + 10,
  `brez ${M.koncniCas(sBrez)} z ${M.koncniCas(sZ)}`);
ok('čas ni pod mejo strežnika (L / VMAX)', M.koncniCas(sBrez) >= M.L / M.VMAX);

console.log('Led');
const led = nivo('led');
const predrzen = bot(M.makeSim(led), { mu: 1.0 });
ok('kdor na ledu vozi kot na suhem, konča v jarku', predrzen.jarki >= 3, `jarki ${predrzen.jarki}`);
const lBrez = bot(M.makeSim(led), { mu: null });
const lZ = bot(M.makeSim(led), { mu: null, verige: true });
ok('previden voznik na ledu pride čez', lBrez.done && lBrez.jarki === 0, `jarki ${lBrez.jarki}`);
ok('na ledu so verige hitrejše', M.koncniCas(lZ) < M.koncniCas(lBrez) - 20,
  `brez ${M.koncniCas(lBrez)} z ${M.koncniCas(lZ)}`);
ok('led je počasnejši od suhega', M.koncniCas(lBrez) > M.koncniCas(sBrez) + 30);

console.log('Sneg');
const sneg = nivo('sneg');
const nBrez = bot(M.makeSim(sneg), { mu: null });
const nZ = bot(M.makeSim(sneg), { mu: null, verige: true });
ok('na snegu so verige hitrejše', M.koncniCas(nZ) < M.koncniCas(nBrez), `brez ${M.koncniCas(nBrez)} z ${M.koncniCas(nZ)}`);

console.log('Verige');
const v = M.makeSim(suho);
ok('na startu so verige zastonj', M.menjajVerige(v) && v.pen === 0 && v.verige);
M.step(v, { plin: 1, zavora: 0, volan: 0 }, 0.5);
ok('v vožnji se verig ne da menjati', !M.menjajVerige(v));
for (let i = 0; i < 600; i++) M.step(v, { plin: 0, zavora: 1, volan: 0 }, 1 / 120);
ok('ustavljen jih lahko snameš, s kaznijo', M.menjajVerige(v) && v.pen === M.VERIGE_S && !v.verige);
const vv = M.makeSim(suho, { verige: true });
for (let i = 0; i < 120 * 30; i++) {
  const volan = Math.max(-1, Math.min(1, (M.kAt(vv, vv.s + 3) - 0.05 * vv.d - 0.3 * vv.psi) / M.KMAX));
  M.step(vv, { plin: 1, zavora: 0, volan }, 1 / 120);
}
ok('z verigami ne gre čez 50 km/h', vv.v <= M.VMAX_VERIGE + 0.2, `v=${(vv.v * 3.6).toFixed(1)} km/h`);

console.log('Volan');
const nv = M.makeSim(suho);
for (let i = 0; i < 120 * 60 && !nv.jarki; i++) {
  M.step(nv, { plin: nv.v < 10 ? 1 : 0, zavora: 0, volan: 0 }, 1 / 120);
}
ok('brez volana avto v prvem ovinku zapelje v jarek', nv.jarki > 0, `s=${nv.s.toFixed(0)}`);

console.log('Veter');
const vet = nivo('suho');
vet.sunki_kmh = 80;
const wv = bot(M.makeSim(vet), { mu: null });
ok('ob sunkih previden voznik še pride čez', wv.done && wv.jarki === 0, `jarki ${wv.jarki}`);

console.log('Današnji nivo');
const NIVO = path.join(ROOT, 'crnivec-site', 'igra', 'nivo.json');
if (fs.existsSync(NIVO)) {
  const lv = JSON.parse(fs.readFileSync(NIVO, 'utf8'));
  ok('nivo ima odsek za vsak kilometer', lv.odseki.length === Math.ceil(M.L_REAL_KM), `${lv.odseki.length}`);
  ok('nivo pove svetlobo (noc/somrak/dan)', ['noc', 'somrak', 'dan'].includes(lv.svetloba), String(lv.svetloba));
  ok('odseki imajo padavine in snežno odejo', lv.odseki.every((o) => 'pada' in o && typeof o.odeja === 'boolean'));
  ok('pada je samo dez/sneg/null', lv.odseki.every((o) => [null, 'dez', 'sneg'].includes(o.pada)));
  const d = bot(M.makeSim(lv), { mu: null });
  ok('današnji nivo je prevozen', d.done && d.jarki === 0, `jarki ${d.jarki}, t=${d.t.toFixed(1)}`);
} else {
  console.log('  (nivo.json še ne obstaja — preskočeno)');
}

if (failed) { console.log(`\n✗ ${failed} test(ov) ni uspelo`); process.exit(1); }
console.log('\n✓ vsi testi uspešni');
