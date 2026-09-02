/*
 * tools/test_igra.mjs — enotni testi modela igre /igra/ (igra/igra.js).
 *
 * Zakaj obstaja: igra obljublja, da jo poganja resnično vreme. To ni stvar
 * občutka, ampak trditev, ki se da izmeriti — sončen julijski nivo mora
 * leteti bistveno dlje kot novembrska megla. Če ta test pade, igra ni več to,
 * kar piše na strani. Isti pristop kot pri Horn naklonu/ekspoziciji v
 * meteogasilec/gasilec.js, ki je bil pred vklopom testiran z Node na
 * sintetičnih vhodih znane smeri.
 *
 * Brez odvisnosti. Zaženi:  node tools/test_igra.mjs
 */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const M = require(path.join(ROOT, 'igra', 'igra.js'));

let failed = 0;
function ok(name, cond, detail) {
  if (cond) { console.log(`  ✓ ${name}`); return; }
  failed++;
  console.log(`  ✗ ${name}${detail ? '  — ' + detail : ''}`);
}
function near(a, b, tol) { return Math.abs(a - b) <= tol; }

// Sejano naključje, da so testi ponovljivi kljub turbulenci.
const seeded = (s) => M.mulberry32(s);

const baseLevel = {
  datum: '2026-07-15', seme: 12345, konec_km: 44,
  strop_m: 2400, strop_bl_m: 2450, baza_m: 2350,
  termika_ms: 3.2, w_star: 2.4, sink_ms: 0.65, gostota_km: 2.4,
  veter_tla_ms: 0.8, veter_180_ms: 1.8, veter_kmh: 10, veter_smer: 290,
  turbulenca: 0.25, padavine_mm: 0, koda_vremena: 1,
};
const lvl = (over) => Object.assign({}, baseLevel, over);

console.log('\n1. Polara padala');
{
  // Najmanjši spust mora biti pri 8,5 m/s.
  let best = Infinity, bestV = 0;
  for (let v = 6; v <= 18; v += 0.01) {
    const s = M.sinkAt(v);
    if (s < best) { best = s; bestV = v; }
  }
  ok('najmanjši spust pri ~8,5 m/s', near(bestV, 8.5, 0.05), `dobljeno ${bestV.toFixed(2)}`);
  ok('najmanjši spust ~0,95 m/s', near(best, 0.95, 0.01), `dobljeno ${best.toFixed(3)}`);

  // Najboljše drsenje (največje v/sink) pri ~10,5 m/s in ~9,9 : 1.
  let bg = 0, bgV = 0;
  for (let v = 6; v <= 18; v += 0.01) {
    const g = v / M.sinkAt(v);
    if (g > bg) { bg = g; bgV = v; }
  }
  ok('najboljše drsenje pri ~10,5 m/s', near(bgV, 10.5, 0.3), `dobljeno ${bgV.toFixed(2)}`);
  ok('najboljše drsenje ~9,9 : 1', near(bg, 9.9, 0.2), `dobljeno ${bg.toFixed(2)}`);
  ok('pospeševalnik slabše drsi', 14.4 / M.sinkAt(14.4) < bg);
}

console.log('\n2. Determinizem nivoja');
{
  const a = M.makeSim(lvl({}));
  const b = M.makeSim(lvl({}));
  const c = M.makeSim(lvl({ seme: 999 }));
  const key = (s) => s.thermals.map((t) => `${t.km.toFixed(4)}:${t.moc.toFixed(4)}:${t.r0.toFixed(2)}`).join('|');
  ok('isto seme → isti stebri', key(a) === key(b));
  ok('drugo seme → drugi stebri', key(a) !== key(c));
  ok('stebri pokrijejo pot', a.thermals.length > 8 &&
    a.thermals[a.thermals.length - 1].km > 35, `${a.thermals.length} stebrov`);
}

console.log('\n3. Teren');
{
  const s = M.makeSim(lvl({}));
  ok('vzletišče ~1400 m', near(M.terrainAt(s, 0), 1400, 5), `${M.terrainAt(s, 0).toFixed(0)}`);
  ok('Rečica (10,3 km) ~374 m', near(M.terrainAt(s, 10.3), 374, 12), `${M.terrainAt(s, 10.3).toFixed(0)}`);
  ok('Celje (41,7 km) ~241 m', near(M.terrainAt(s, 41.7), 241, 12), `${M.terrainAt(s, 41.7).toFixed(0)}`);
  ok('profil monotono pada z Golt v dolino',
    M.terrainAt(s, 2) < M.terrainAt(s, 1) && M.terrainAt(s, 5) < M.terrainAt(s, 2));
}

console.log('\n4. Veter po višini');
{
  const s = M.makeSim(lvl({ veter_tla_ms: 1, veter_180_ms: 4 }));
  ok('pri tleh = vrednost na 10 m', near(M.windAt(s, 5), 1, 1e-9));
  ok('na 180 m = vrednost na 180 m', near(M.windAt(s, 180), 4, 1e-9));
  ok('nad 180 m še krepi', M.windAt(s, 1500) > 4 && M.windAt(s, 1500) < 6,
    `${M.windAt(s, 1500).toFixed(2)}`);
  const h = M.makeSim(lvl({ veter_tla_ms: -1, veter_180_ms: -4 }));
  ok('čelni veter ostane negativen', M.windAt(h, 1000) < -4);
}

console.log('\n5. Dvigi in strop');
{
  const s = M.makeSim(lvl({ veter_180_ms: 0, w_star: 2.4 }));
  const t = s.thermals[3];
  const g = M.terrainAt(s, t.km);
  ok('v jedru stebra dviguje', M.airVertical(s, t.km, g + 600) > 1);
  ok('daleč od stebra spušča', M.airVertical(s, t.km + 1.4, g + 600) < 0);
  ok('nad stropom ni dviga', M.airVertical(s, t.km, s.ceilASL + 50) < 0);
  ok('tik pod stropom dvig ugaša',
    M.airVertical(s, t.km, s.ceilASL - 20) < M.airVertical(s, t.km, s.ceilASL - 400));
  ok('tik nad tlemi je dvig šibek',
    M.airVertical(s, t.km, g + 20) < M.airVertical(s, t.km, g + 400));
}

console.log('\n6. Konec leta');
{
  // Na položnem odseku (pri Žalcu), sicer bi tla pod padalom padala hitreje
  // od padala samega in stika ne bi bilo.
  const s = M.makeSim(lvl({}));
  s.km = 31;
  s.alt = M.terrainAt(s, 31) + 0.5;
  const st = M.stepFixed(s, { mode: 'glide', nudge: 0 }, 1);
  ok('dotik tal konča let', st === 'landed', st);

  const f = M.makeSim(lvl({}));
  f.km = f.endKm - 0.001;
  ok('konec poti = dokončan prelet',
    M.stepFixed(f, { mode: 'glide', nudge: 0 }, 1) === 'finished');
}

console.log('\n7. Vreme res poganja razdaljo (regresija)');
{
  const dan = (name, level, expect) => {
    const r = M.autoFly(level, { rand: seeded(7) });
    const s = `${r.km.toFixed(1)} km (${r.minutes.toFixed(0)} min, ${r.status})`;
    ok(`${name}: ${expect.label}`, expect.test(r.km), s);
    return r;
  };
  // Merilo ni absolutna razdalja, ampak ZDRS: z vzletišča na 1400 m do dna
  // doline na ~374 m padalo pri drsenju 9,9 : 1 v mirnem zraku preleti ~10 km
  // tudi brez enega samega dviga. Dan je vreden toliko, kolikor doda NAD to.
  const zdrs = dan('mrtev zrak (referenčni zdrs z Golt)',
    lvl({ strop_m: 500, termika_ms: 0.0, w_star: 0.3, sink_ms: 0.0, gostota_km: 3.0,
      baza_m: null, turbulenca: 0, veter_tla_ms: 0, veter_180_ms: 0 }),
    { label: '9–12 km', test: (k) => k > 9 && k < 12 });
  const julij = dan('julij, jasno, globoka konvekcija',
    lvl({ strop_m: 2600, termika_ms: 3.4, w_star: 2.5, sink_ms: 0.68, gostota_km: 2.6, baza_m: 2500 }),
    { label: '> 2,5× zdrs', test: (k) => k > zdrs.km * 2.5 });
  // April je namenoma umerjen tako, da NE doseže konca proge — sicer bi se
  // skupaj z julijem ustavil na 44 km in primerjava med njima ne bi ločila.
  const april = dan('april, kopasti oblaki',
    lvl({ strop_m: 1650, termika_ms: 1.8, w_star: 1.4, sink_ms: 0.5, gostota_km: 2.1,
      z_i_m: 1250, baza_m: 1600 }),
    { label: '> 1,3× zdrs, a ne do konca', test: (k) => k > zdrs.km * 1.3 && k < 44 });
  const nov = dan('november, megla (strop pod vzletiščem)',
    lvl({ strop_m: 600, termika_ms: 0.3, w_star: 0.4, sink_ms: 0.35, gostota_km: 1.0,
      baza_m: null, koda_vremena: 45 }),
    { label: '≤ zdrs', test: (k) => k <= zdrs.km + 0.5 });
  ok('julij > april > november', julij.km > april.km && april.km > nov.km,
    `${julij.km.toFixed(1)} / ${april.km.toFixed(1)} / ${nov.km.toFixed(1)}`);

  // Čelni veter mora skrajšati prelet.
  const hrbet = M.autoFly(lvl({ veter_tla_ms: 2, veter_180_ms: 4 }), { rand: seeded(7) });
  const celo = M.autoFly(lvl({ veter_tla_ms: -2, veter_180_ms: -4 }), { rand: seeded(7) });
  ok('hrbtnik nese dlje kot čelni veter', hrbet.km > celo.km,
    `${hrbet.km.toFixed(1)} vs ${celo.km.toFixed(1)}`);
}

console.log('\n8. Današnji nivo iz igra/nivo.json');
{
  const p = path.join(ROOT, 'igra', 'nivo.json');
  if (!fs.existsSync(p)) {
    ok('nivo.json obstaja', false, 'poženi python3 tools/generate_igra_page.py');
  } else {
    const level = JSON.parse(fs.readFileSync(p, 'utf8'));
    for (const k of ['datum', 'seme', 'strop_m', 'termika_ms', 'sink_ms', 'gostota_km',
      'veter_tla_ms', 'veter_180_ms', 'konec_km', 'teren', 'mejniki']) {
      ok(`nivo.json ima ${k}`, level[k] !== undefined);
    }
    ok('teren ima dovolj vzorcev', level.teren.h.length > 100, `${level.teren.h.length}`);
    const r = M.autoFly(level, { rand: seeded(7) });
    console.log(`     → današnji dan (${level.datum}, ${level.vir}): ` +
      `${r.km.toFixed(1)} km do ${r.reached || '—'} v ${r.minutes.toFixed(0)} min`);
    ok('današnji nivo je igralen (> 1 km)', r.km > 1, `${r.km.toFixed(1)} km`);
  }
}

console.log(failed === 0 ? '\n✅ Vsi testi so uspeli.\n' : `\n❌ ${failed} test(ov) ni uspelo.\n`);
process.exit(failed === 0 ? 0 : 1);
