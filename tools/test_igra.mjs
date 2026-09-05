/*
 * tools/test_igra.mjs — enotni testi modela igre /igra/ (igra/igra.js).
 *
 * Zakaj obstaja: igra obljublja, da jo poganja resnično vreme. To ni stvar
 * občutka, ampak trditev, ki se da izmeriti — sončen julijski nivo mora
 * leteti bistveno dlje kot mrtev zrak, in smer dneva mora izbrati veter. Če
 * ta test pade, igra ni več to, kar piše na strani. Isti pristop kot pri Horn
 * naklonu/ekspoziciji v meteogasilec/gasilec.js, ki je bil pred vklopom
 * testiran z Node na sintetičnih vhodih znane smeri.
 *
 * Regresijski dnevi tečejo po PRAVEM terenu koridorja iz igra/koridorji.json,
 * ne po rezervnem profilu v igri — sicer bi merili nekaj, česar igralec nikoli
 * ne vidi.
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
const seeded = (s) => M.mulberry32(s);

// ── Koridorji ────────────────────────────────────────────────────────────
const KOR_PATH = path.join(ROOT, 'igra', 'koridorji.json');
const korDoc = fs.existsSync(KOR_PATH) ? JSON.parse(fs.readFileSync(KOR_PATH, 'utf8')) : null;
const celje = korDoc && korDoc.koridorji.find((k) => k.id === 'celje');

// Sintetični nivo na pravem terenu koridorja: vreme si izmislimo, geometrijo ne.
function dan(over) {
  return Object.assign({
    datum: '2026-07-15', seme: 42,
    konec_km: celje ? celje.konec_km : 44,
    mejniki: celje ? celje.mejniki : undefined,
    teren: celje ? celje.teren : undefined,
    veter_tla_ms: 0.5, veter_180_ms: 1.0, veter_visoko_ms: 2.0,
    turbulenca: 0.25, padavine_mm: 0, koda_vremena: 1,
    strop_m: 2400, baza_m: 2350, termika_ms: 3.4, w_star: 2.1,
    sink_ms: 0.68, gostota_km: 2.6, z_i_m: 1900,
  }, over);
}

console.log('\n1. Polara padala');
{
  let best = Infinity, bestV = 0;
  for (let v = 6; v <= 18; v += 0.01) {
    const s = M.sinkAt(v);
    if (s < best) { best = s; bestV = v; }
  }
  ok('najmanjši spust pri ~8,5 m/s', near(bestV, 8.5, 0.05), `dobljeno ${bestV.toFixed(2)}`);
  ok('najmanjši spust ~0,95 m/s', near(best, 0.95, 0.01), `dobljeno ${best.toFixed(3)}`);
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
  const a = M.makeSim(dan({}));
  const b = M.makeSim(dan({}));
  const c = M.makeSim(dan({ seme: 999 }));
  const key = (s) => s.thermals.map((t) => `${t.km.toFixed(4)}:${t.moc.toFixed(4)}:${t.r0.toFixed(2)}`).join('|');
  ok('isto seme → isti stebri', key(a) === key(b));
  ok('drugo seme → drugi stebri', key(a) !== key(c));
  ok('stebri pokrijejo pot', a.thermals.length > 8 &&
    a.thermals[a.thermals.length - 1].km > a.endKm * 0.8, `${a.thermals.length} stebrov`);
}

console.log('\n3. Koridorji (igra/koridorji.json)');
{
  ok('datoteka obstaja', !!korDoc, 'poženi python3 tools/build_igra_corridors.py');
  if (korDoc) {
    ok('vsaj štirje koridorji', korDoc.koridorji.length >= 4, `${korDoc.koridorji.length}`);
    let vsiOk = true, azimuti = [];
    for (const k of korDoc.koridorji) {
      const h = k.teren.h;
      const dobro = k.id && k.ime && k.kratko && h.length > 40 &&
        h[0] === korDoc.vzletisce.visina &&          // vsi se začnejo na vzletišču
        k.mejniki.length >= 2 && k.mejniki[0].km === 0 &&
        k.odseki.length >= 1 && k.konec_km > k.dolzina_km;
      if (!dobro) { vsiOk = false; console.log(`      ✗ ${k.id}`); }
      azimuti.push(k.azimut);
    }
    ok('vsi koridorji so celi in se začnejo na 1400 m', vsiOk);
    // Smeri morajo biti razpršene, sicer izbira po vetru nima kaj izbirati.
    azimuti.sort((a, b) => a - b);
    let najvecjaVrzel = 360 - azimuti[azimuti.length - 1] + azimuti[0];
    for (let i = 1; i < azimuti.length; i++) {
      najvecjaVrzel = Math.max(najvecjaVrzel, azimuti[i] - azimuti[i - 1]);
    }
    ok('smeri pokrivajo rožo (največja vrzel < 150°)', najvecjaVrzel < 150,
      `${najvecjaVrzel.toFixed(0)}°  [${azimuti.map((a) => a.toFixed(0)).join(', ')}]`);
  }
}

console.log('\n4. Teren koridorja');
{
  const s = M.makeSim(dan({}));
  ok('vzletišče 1400 m', near(M.terrainAt(s, 0), 1400, 5), `${M.terrainAt(s, 0).toFixed(0)}`);
  ok('profil pada z Golt v dolino',
    M.terrainAt(s, 2) < M.terrainAt(s, 1) && M.terrainAt(s, 5) < M.terrainAt(s, 2));
  if (celje) {
    const recica = celje.mejniki.find((m) => m.ime === 'Rečica');
    ok('Rečica je v dnu doline (< 550 m)', M.terrainAt(s, recica.km) < 550,
      `${M.terrainAt(s, recica.km).toFixed(0)} m`);
  }
}

console.log('\n5. Veter po višini (trije izmerjeni nivoji)');
{
  const s = M.makeSim(dan({ veter_tla_ms: 1, veter_180_ms: 4, veter_visoko_ms: 8 }));
  ok('pri tleh = vrednost na 10 m', near(M.windAt(s, 5), 1, 1e-9));
  ok('na 180 m = vrednost na 180 m', near(M.windAt(s, 180), 4, 1e-9));
  ok('na 1500 m = vrednost na 1500 m', near(M.windAt(s, 1500), 8, 1e-9));
  ok('vmes narašča zvezno', M.windAt(s, 800) > 4 && M.windAt(s, 800) < 8,
    `${M.windAt(s, 800).toFixed(2)}`);
  ok('nad 1500 m ostane', near(M.windAt(s, 2500), 8, 1e-9));
  // Prav to je nova zmožnost: čelni veter pri tleh, hrbtnik na višini.
  const strig = M.makeSim(dan({ veter_tla_ms: -1.2, veter_180_ms: -1.7, veter_visoko_ms: 3.1 }));
  ok('čelno spodaj, v hrbet zgoraj (kar je 3. 9. 2026 res bilo)',
    M.windAt(strig, 100) < 0 && M.windAt(strig, 1400) > 0,
    `${M.windAt(strig, 100).toFixed(2)} → ${M.windAt(strig, 1400).toFixed(2)}`);
}

console.log('\n6. Dvigi in strop');
{
  const s = M.makeSim(dan({ veter_180_ms: 0, veter_visoko_ms: 0 }));
  const t = s.thermals[3];
  const g = M.terrainAt(s, t.km);
  ok('v jedru stebra dviguje', M.airVertical(s, t.km, g + 600) > 1);
  ok('daleč od stebra spušča', M.airVertical(s, t.km + 1.4, g + 600) < 0);
  ok('nad stropom ni dviga', M.airVertical(s, t.km, s.ceilASL + 50) < 0);
  ok('tik pod stropom dvig ugaša',
    M.airVertical(s, t.km, s.ceilASL - 20) < M.airVertical(s, t.km, s.ceilASL - 400));
  ok('tik nad tlemi je dvig šibek',
    M.airVertical(s, t.km, g + 20) < M.airVertical(s, t.km, g + 400));
  // Če je jedro šibkejše od spusta pri kroženju, kroženje sploh ne dviga in
  // igra izgubi svojo osrednjo potezo — to se je enkrat že zgodilo.
  const jedra = s.thermals.map((x) => x.moc).sort((a, b) => b - a);
  const mediana = jedra[Math.floor(jedra.length / 2)];
  ok('mediana jeder je nad spustom pri kroženju',
    mediana > M.sinkAt(M.V_CIRCLE) * M.BANK_PENALTY,
    `${mediana.toFixed(2)} vs ${(M.sinkAt(M.V_CIRCLE) * M.BANK_PENALTY).toFixed(2)} m/s`);
}

console.log('\n7. Konec leta');
{
  const s = M.makeSim(dan({}));
  s.km = 31; s.alt = M.terrainAt(s, 31) + 0.5;
  ok('dotik tal konča let',
    M.stepFixed(s, { mode: 'glide', nudge: 0 }, 1) === 'landed');
  const f = M.makeSim(dan({}));
  f.km = f.endKm - 0.001;
  ok('konec poti = dokončan prelet',
    M.stepFixed(f, { mode: 'glide', nudge: 0 }, 1) === 'finished');
}

console.log('\n8. Vreme res poganja razdaljo (regresija)');
{
  const leti = (level, strat) => {
    const s = M.makeSim(level, seeded(7));
    const c = { mode: 'glide', nudge: 0 };
    while (s.status === 'flying' && s.simTime < 6 * 3600) {
      const r = strat(s); c.mode = r.m; c.nudge = r.n || 0;
      M.stepFixed(s, c, 1 / 60);
    }
    return s.best;
  };
  const drsi = () => ({ m: 'glide' });
  const pilot = (s) => {
    const w = M.airVertical(s, s.km, s.alt);
    if (w > 0.6 && s.ceilASL - s.alt > 30) return { m: 'circle', n: 1 };
    if (w < -1.2) return { m: 'fast' };
    return { m: 'glide' };
  };

  // Merilo ni absolutna razdalja, ampak ZDRS: z vzletišča na 1400 m padalo v
  // mirnem zraku preleti nekaj kilometrov tudi brez enega samega dviga. Dan je
  // vreden toliko, kolikor doda NAD to.
  const mrtev = dan({
    strop_m: 500, baza_m: null, termika_ms: 0, w_star: 0.3, sink_ms: 0,
    gostota_km: 3, z_i_m: 400, turbulenca: 0,
    veter_tla_ms: 0, veter_180_ms: 0, veter_visoko_ms: 0,
  });
  const zdrs = leti(mrtev, drsi);
  ok('mrtev zrak da zdrs 5–10 km', zdrs > 5 && zdrs < 10, `${zdrs.toFixed(1)} km`);
  ok('v mrtvem zraku kroženje ne pomaga', leti(mrtev, pilot) <= zdrs + 0.5);

  const julij = leti(dan({ strop_m: 2600, baza_m: 2500, termika_ms: 4.0, w_star: 2.5,
    sink_ms: 0.76, gostota_km: 3.2, z_i_m: 2200 }), pilot);
  ok('julij, globoka konvekcija: > 3× zdrs', julij > zdrs * 3, `${julij.toFixed(1)} km`);

  const april = leti(dan({ strop_m: 1800, baza_m: 1750, termika_ms: 2.7, w_star: 1.7,
    sink_ms: 0.59, gostota_km: 2.2, z_i_m: 1400 }), pilot);
  ok('april: > 1,5× zdrs', april > zdrs * 1.5, `${april.toFixed(1)} km`);

  const megla = leti(dan({ strop_m: 600, baza_m: null, termika_ms: 0.3, w_star: 0.4,
    sink_ms: 0.35, gostota_km: 1.0, z_i_m: 250, koda_vremena: 45 }), pilot);
  ok('megla: ne preseže zdrsa', megla <= zdrs + 0.5, `${megla.toFixed(1)} km`);
  ok('julij > april > megla', julij > april && april > megla,
    `${julij.toFixed(1)} / ${april.toFixed(1)} / ${megla.toFixed(1)}`);

  // Znanje mora šteti: pameten pilot mora na spodobnem dnevu preseči zdrs.
  const aprilDrsi = leti(dan({ strop_m: 1800, baza_m: 1750, termika_ms: 2.7, w_star: 1.7,
    sink_ms: 0.59, gostota_km: 2.2, z_i_m: 1400 }), drsi);
  ok('kroženje se na spodobnem dnevu izplača', april > aprilDrsi * 1.2,
    `${april.toFixed(1)} vs ${aprilDrsi.toFixed(1)} km samo z drsenjem`);

  const hrbet = leti(dan({ veter_tla_ms: 2, veter_180_ms: 3, veter_visoko_ms: 5 }), pilot);
  const celo = leti(dan({ veter_tla_ms: -2, veter_180_ms: -3, veter_visoko_ms: -5 }), pilot);
  ok('hrbtnik nese dlje kot čelni veter', hrbet > celo,
    `${hrbet.toFixed(1)} vs ${celo.toFixed(1)}`);
}

console.log('\n9. Današnji nivo iz igra/nivo.json');
{
  const p = path.join(ROOT, 'igra', 'nivo.json');
  if (!fs.existsSync(p)) {
    ok('nivo.json obstaja', false, 'poženi python3 tools/generate_igra_page.py');
  } else {
    const level = JSON.parse(fs.readFileSync(p, 'utf8'));
    for (const k of ['datum', 'seme', 'strop_m', 'termika_ms', 'sink_ms', 'gostota_km',
      'veter_tla_ms', 'veter_180_ms', 'veter_visoko_ms', 'konec_km', 'teren',
      'mejniki', 'koridor']) {
      ok(`nivo.json ima ${k}`, level[k] !== undefined);
    }
    ok('koridor je eden od znanih',
      !korDoc || korDoc.koridorji.some((k) => k.id === level.koridor.id),
      level.koridor && level.koridor.id);
    ok('teren ima dovolj vzorcev', level.teren.h.length > 40, `${level.teren.h.length}`);
    const s = M.makeSim(level, seeded(7));
    const c = { mode: 'glide', nudge: 0 };
    while (s.status === 'flying' && s.simTime < 6 * 3600) {
      const w = M.airVertical(s, s.km, s.alt);
      c.mode = (w > 0.6 && s.ceilASL - s.alt > 30) ? 'circle' : 'glide';
      c.nudge = c.mode === 'circle' ? 1 : 0;
      M.stepFixed(s, c, 1 / 60);
    }
    console.log(`     → ${level.datum} · ${level.koridor.ime} · ` +
      `${s.best.toFixed(1)} km do ${s.reached || '—'} v ${(s.simTime / 60).toFixed(0)} min`);
    ok('današnji nivo je igralen (> 1 km)', s.best > 1, `${s.best.toFixed(1)} km`);

    // Vse štiri smeri, da igralec po koncu današnje proge lahko poskusi
    // ostale tri z istim dnevnim vremenom (glej opombo pri build_level()).
    const vse = level.vse_koridorje;
    ok('nivo.json ima vse_koridorje', !!vse);
    if (vse) {
      const ids = korDoc ? korDoc.koridorji.map((k) => k.id) : Object.keys(vse);
      ok('vse_koridorje ima vse znane koridorje', ids.every((id) => !!vse[id]),
        Object.keys(vse).join(', '));
      ok('današnji koridor je med njimi isti kot level.koridor',
        vse[level.koridor.id] && vse[level.koridor.id].konec_km === level.konec_km);
      for (const id of ids) {
        const l2 = vse[id];
        if (!l2) continue;
        // Strop/dvigi so od vremena, ne od smeri -- morajo biti IDENTIČNI.
        ok(`${id}: strop enak kot pri današnjem nivoju`, l2.strop_m === level.strop_m);
        ok(`${id}: dvigi enaki kot pri današnjem nivoju`, l2.termika_ms === level.termika_ms);
        ok(`${id}: ima svoj teren in konec_km`, l2.teren && l2.teren.h.length > 40 && l2.konec_km > 0);
        // Vsak igra do konca vsaj malo daleč -- isti preizkus kot za danes izbrani.
        const s2 = M.makeSim(l2, seeded(7));
        const c2 = { mode: 'glide', nudge: 0 };
        while (s2.status === 'flying' && s2.simTime < 6 * 3600) {
          const w2 = M.airVertical(s2, s2.km, s2.alt);
          c2.mode = (w2 > 0.6 && s2.ceilASL - s2.alt > 30) ? 'circle' : 'glide';
          c2.nudge = c2.mode === 'circle' ? 1 : 0;
          M.stepFixed(s2, c2, 1 / 60);
        }
        ok(`${id}: je igralen (> 1 km)`, s2.best > 1, `${s2.best.toFixed(1)} km`);
      }
    }
  }
}

console.log(failed === 0 ? '\n✅ Vsi testi so uspeli.\n' : `\n❌ ${failed} test(ov) ni uspelo.\n`);
process.exit(failed === 0 ? 0 : 1);
