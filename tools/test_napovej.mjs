/*
 * tools/test_napovej.mjs — enotni testi modela igre /napovej/ (napovej/napovej.js).
 *
 * Zakaj obstaja: igra obljublja, da igralca meri po ISTEM pravilu kot modele na
 * semaforju /tocnost-napovedi/. To ni stvar občutka, ampak trditev, ki se da
 * izmeriti — natančnejša napoved mora dobiti več točk, modeli morajo biti merjeni
 * samo na dnevih, ki jih je igralec igral, in oddana napoved se ne sme prepisati.
 * Če ta test pade, stran obljublja nekaj, česar igra ne dela. Isti pristop kot pri
 * tools/test_igra.mjs in pri Horn naklonu v meteogasilec/gasilec.js.
 *
 * Brez odvisnosti. Zaženi:  node tools/test_napovej.mjs
 */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const M = require(path.join(ROOT, 'napovej', 'napovej.js'));

let failed = 0;
function ok(name, cond, detail) {
  if (cond) { console.log(`  ✓ ${name}`); return; }
  failed++;
  console.log(`  ✗ ${name}${detail ? '  — ' + detail : ''}`);
}
const near = (a, b, tol) => Math.abs(a - b) <= tol;

// ── Napaka in točke ───────────────────────────────────────────────────────
console.log('\nOcenjevanje');
ok('napaka je absolutna', M.napaka(20, 22) === 2 && M.napaka(24, 22) === 2);
ok('manjkajoča vrednost ne da napake', M.napaka(null, 22) === null && M.napaka(20, null) === null);
ok('popoln zadetek je 100 točk', M.tocke(0, M.TOL_T) === 100);
ok('napaka toliko kot toleranca je 0 točk', M.tocke(M.TOL_T, M.TOL_T) === 0);
ok('nad toleranco ne gre pod 0', M.tocke(12, M.TOL_T) === 0);
ok('vmes pada linearno', M.tocke(2.5, M.TOL_T) === 50);

// ── Isto pravilo za igralca in za model ───────────────────────────────────
const dej = { tmax: 25.0, tmin: 12.0, dez: 0.0 };
const tocna = { tmax: 25.0, tmin: 12.0, dez: 0.0 };
const groba = { tmax: 28.0, tmin: 15.0, dez: 4.0 };
ok('natančnejša napoved dobi več točk',
  M.oceni(tocna, dej).skupaj > M.oceni(groba, dej).skupaj,
  `${M.oceni(tocna, dej).skupaj} vs ${M.oceni(groba, dej).skupaj}`);
ok('ocena je povprečje obeh temperatur',
  M.oceni({ tmax: 25.0, tmin: 14.5 }, dej).skupaj === 75,
  String(M.oceni({ tmax: 25.0, tmin: 14.5 }, dej).skupaj));
ok('dež ne vpliva na skupno oceno (ARSO in MTR ga nimata v mm)',
  M.oceni({ tmax: 25, tmin: 12, dez: 40 }, dej).skupaj === M.oceni(tocna, dej).skupaj);

// ── Mokro/suho: milimetri, verjetnost, nič ────────────────────────────────
console.log('\nMokro ali suho');
ok('milimetri nad pragom pomenijo moker dan', M.mokro({ dez: 1.2 }) === true);
ok('milimetri pod pragom pomenijo suh dan', M.mokro({ dez: 0.1 }) === false);
ok('verjetnost >= 0,5 je moker dan (MTR nima milimetrov)', M.mokro({ pop: 0.6 }) === true);
ok('verjetnost < 0,5 je suh dan', M.mokro({ pop: 0.3 }) === false);
ok('vir brez padavin ne trdi ničesar', M.mokro({ tmax: 20, tmin: 10 }) === null);
ok('zadetek mokrega dne se prizna',
  M.oceni({ tmax: 25, tmin: 12, dez: 3 }, { tmax: 25, tmin: 12, dez: 5 }).zadel_mokro === true);
ok('zgrešen moker dan se ne prizna',
  M.oceni({ tmax: 25, tmin: 12, dez: 0 }, { tmax: 25, tmin: 12, dez: 5 }).zadel_mokro === false);

// ── Lestvica dneva ────────────────────────────────────────────────────────
console.log('\nLestvica dneva');
const dan = {
  dejansko: { tmax: 25.0, tmin: 12.0, dez: 0.0 },
  modeli: {
    arso: { tmax: 22.0, tmin: 16.0 },                 // grdo mimo
    open_meteo: { tmax: 25.5, tmin: 14.0, dez: 0.0 }, // solidno
    meteorec: { tmax: 25.1, tmin: 12.2, pop: 0.1 },   // najbolje
    aifs: { tmax: 23.0, tmin: 15.0, dez: 1.0 }
  }
};
const mojaDobra = { tmax: 25.0, tmin: 12.1, dez: 0.0 };
let vr = M.lestvica(dan, mojaDobra);
ok('na lestvici so igralec in vsi modeli', vr.length === 5, String(vr.length));
ok('urejeno po oceni navzdol', vr.every((r, i) => i === 0 || vr[i - 1].o.skupaj >= r.o.skupaj));
ok('najboljša napoved je prva', vr[0].jaz === true, vr[0].ime);
let p = M.premagani(vr);
ok('igralec je premagal vse štiri', p.premagal === 4 && p.od === 4 && p.mesto === 1);

const mojaSlaba = { tmax: 18.0, tmin: 20.0, dez: 0.0 };
p = M.premagani(M.lestvica(dan, mojaSlaba));
ok('slaba napoved ne premaga nikogar', p.premagal === 0 && p.mesto === 5);

// Vir, ki tistega dne ni napovedal, ne sme pristati na dnu lestvice, kot da bi
// se zmotil — na njej ga sploh ni.
const danBrezArso = { dejansko: dan.dejansko, modeli: { open_meteo: dan.modeli.open_meteo } };
vr = M.lestvica(danBrezArso, mojaDobra);
ok('manjkajoč vir ne tekmuje', vr.length === 2 && !vr.some((r) => r.id === 'arso'));

ok('brez meritve ni lestvice', M.lestvica({ dejansko: null, modeli: dan.modeli }, mojaDobra).length === 0);

// ── Sezona: modeli merjeni samo na igranih dnevih ──────────────────────────
console.log('\nSezonska statistika');
const razreseni = {
  '2026-09-01': { dejansko: { tmax: 25, tmin: 12, dez: 0 }, modeli: { open_meteo: { tmax: 26, tmin: 13, dez: 0 } } },
  '2026-09-02': { dejansko: { tmax: 30, tmin: 15, dez: 0 }, modeli: { open_meteo: { tmax: 24, tmin: 21, dez: 0 } } },
  '2026-09-03': { dejansko: { tmax: 20, tmin: 10, dez: 0 }, modeli: { open_meteo: { tmax: 20, tmin: 10, dez: 0 } } }
};
// Igralec je igral samo prva dva dneva — tretji (kjer je model popoln) ne sme šteti.
const vnosi = {
  '2026-09-01': { tmax: 25, tmin: 12, dez: 0 },
  '2026-09-02': { tmax: 30, tmin: 15, dez: 0 }
};
const s = M.sezona(razreseni, vnosi);
const om = s.vrstice.find((z) => z.id === 'open_meteo');
const ti = s.vrstice.find((z) => z.id === 'ti');
ok('šteje samo igrane dni', s.n === 2 && om.n === 2, `n=${s.n}, om.n=${om.n}`);
ok('model ni nagrajen za dan, ki ga igralec ni igral',
  near(om.mae_tmax, 3.5, 0.01), String(om.mae_tmax));
ok('popoln igralec ima napako 0', ti.mae_tmax === 0 && ti.mae_tmin === 0);
ok('igralec je obakrat prvi', s.zmage === 2, String(s.zmage));
ok('brez oddanih napovedi ni sezone', M.sezona(razreseni, {}).n === 0);

// ── Niz ───────────────────────────────────────────────────────────────────
console.log('\nNiz in koledar');
ok('zaporedni dnevi tvorijo niz', M.niz({ '2026-09-01': {}, '2026-09-02': {}, '2026-09-03': {} }) === 3);
ok('vrzel niz prekine', M.niz({ '2026-09-01': {}, '2026-09-03': {}, '2026-09-04': {} }) === 2);
ok('niz čez mesec drži', M.niz({ '2026-08-31': {}, '2026-09-01': {} }) === 2);
ok('brez vnosov ni niza', M.niz({}) === 0);
ok('plusDni čez mesec', M.plusDni('2026-08-31', 1) === '2026-09-01');

// ── Odprtost kroga ────────────────────────────────────────────────────────
// Za dan, ki že teče, napoved ni napoved — igra jo mora zavrniti.
const zdaj = new Date(2026, 8, 3, 12, 0, 0);   // 3. 9. 2026 lokalno
ok('krog za jutri je odprt', M.odprt({ tarca: '2026-09-04' }, zdaj) === true);
ok('krog za danes je zaprt', M.odprt({ tarca: '2026-09-03' }, zdaj) === false);
ok('včerajšnji krog je zaprt', M.odprt({ tarca: '2026-09-02' }, zdaj) === false);
ok('brez kroga ni oddaje', M.odprt(null, zdaj) === false);

// ── Objavljeni krog ───────────────────────────────────────────────────────
// Če je krog na disku, se mora dati oceniti z isto kodo, ki teče v brskalniku.
console.log('\nObjavljeni krog');
const KROG = path.join(ROOT, 'napovej', 'krog.json');
if (fs.existsSync(KROG)) {
  const k = JSON.parse(fs.readFileSync(KROG, 'utf8'));
  ok('krog ima tarčni datum', /^\d{4}-\d{2}-\d{2}$/.test(k.tarca || ''), String(k.tarca));
  const idji = Object.keys(k.modeli || {});
  ok('nasprotniki so znani viri', idji.every((id) => M.VIRI.some((v) => v.id === id)), idji.join(','));
  const dnevi = Object.keys(k.razreseni || {});
  ok('razrešeni dnevi imajo meritev', dnevi.every((d) => k.razreseni[d].dejansko.tmax !== null));
  const zadnji = dnevi.sort().pop();
  if (zadnji) {
    const l = M.lestvica(k.razreseni[zadnji], { tmax: 25, tmin: 12, dez: 0 });
    ok('pravi dan se da oceniti', l.length >= 2 && l.every((r) => r.o.skupaj !== null),
      `${zadnji}: ${l.length} vrstic`);
  }
} else {
  console.log('  – krog.json še ni ustvarjen, preskočeno');
}

console.log(failed ? `\n${failed} test(ov) ni uspelo.\n` : '\nVsi testi so uspeli.\n');
process.exit(failed ? 1 : 0);
