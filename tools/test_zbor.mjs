/*
 * tools/test_zbor.mjs — preizkus /zbor/* (Zamudometer zbora Rečiški pobi) na PRAVEM worker.js
 * (lažen R2 in KV). Poganjanje: node tools/test_zbor.mjs
 *
 * Najpomembnejše: brez gesla se ne da NIČESAR ne prebrati ne zapisati, in ob nenastavljeni skrivnosti
 * je vse zaprto (ne odprto). Preverja tudi, da izbirnik dogodka na strani ustreza seznamu v workerju.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'zbor-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);
const mod = await import(pathToFileURL(file).href);

const store = new Map(), kvm = new Map();
const mkEnv = (secret) => ({
  ...(secret ? { ZBOR_GESLO: secret } : {}),
  PHOTOS_R2: { get: async k => store.has(k) ? { text: async () => store.get(k) } : null, put: async (k, v) => { store.set(k, v); } },
  COUNTER_KV: { get: async k => kvm.get(k) ?? null, put: async (k, v) => { kvm.set(k, v); }, delete: async k => { kvm.delete(k); } },
});
const env = mkEnv('gesloZborov');
const ctx = { waitUntil() {}, passThroughOnException() {} };
let fails = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };
const OK = { Authorization: 'Bearer gesloZborov' };
const call = (e, p, method = 'GET', body, headers = {}, ip = '1.2.3.4') => mod.default.fetch(new Request('https://w.test' + p, {
  method, headers: { Origin: 'https://meteorec.si', 'Content-Type': 'application/json', 'CF-Connecting-IP': ip, ...headers },
  body: body ? JSON.stringify(body) : undefined }), e, ctx);
const KEY = 'feedback/zbor-zamude.json';
const danes = new Date().toISOString().slice(0, 10);
const veljaven = { kdo: '  Janez   Bas ', zakaj: ' Krava je prečkala cesto. ', datum: danes, dogodek: 'vaja', minute: 12, kazen: 'Prinese pijačo' };

// ── Brez skrivnosti na strežniku je vse zaprto (tudi z glavo, ki bi ujemala niz "undefined") ──
let r = await call(mkEnv(null), '/zbor/zamude', 'GET', undefined, { Authorization: 'Bearer undefined' });
check(r.status === 503, 'skrivnost ni nastavljena: 503, ne odprto');
r = await call(mkEnv(null), '/zbor/zamuda', 'POST', veljaven, { Authorization: 'Bearer undefined' });
check(r.status === 503 && !store.has(KEY), 'skrivnost ni nastavljena: zapis zavrnjen');

// ── Brez gesla ali z napačnim se ne da ničesar ──
r = await call(env, '/zbor/zamude');
check(r.status === 401, 'branje brez gesla: 401');
r = await call(env, '/zbor/zamude', 'GET', undefined, { Authorization: 'Bearer napacno' });
check(r.status === 401, 'branje z napačnim geslom: 401');
r = await call(env, '/zbor/zamuda', 'POST', veljaven);
check(r.status === 401 && !store.has(KEY), 'zapis brez gesla: 401, nič shranjeno');
r = await call(env, '/zbor/izbrisi', 'POST', { id: 'x' });
check(r.status === 401, 'brisanje brez gesla: 401');
r = await call(env, '/zbor/zamude', 'GET', undefined, { Authorization: 'Bearer gesloZborovX' });
check(r.status === 401, 'geslo z drugačno dolžino: 401');

// ── Pravilna pot ──
r = await call(env, '/zbor/zamude', 'GET', undefined, OK);
check(r.status === 200 && (await r.json()).zapisi.length === 0, 'prazen seznam');
r = await call(env, '/zbor/zamuda', 'POST', veljaven, OK);
check(r.status === 200, 'veljaven vnos sprejet');
let saved = JSON.parse(store.get(KEY));
check(saved.length === 1 && saved[0].kdo === 'Janez Bas' && saved[0].zakaj === 'Krava je prečkala cesto.'
  && saved[0].minute === 12 && saved[0].kazen === 'Prinese pijačo' && !('ip' in saved[0]) && saved[0].id, 'shranjeno obrezano, brez IP');
r = await call(env, '/zbor/zamuda', 'POST', veljaven, OK);
check(JSON.parse(store.get(KEY)).length === 1, 'dvojni klik ne podvoji');
r = await call(env, '/zbor/zamuda', 'POST', { ...veljaven, kdo: 'Tone', minute: undefined, izostal: true, zakaj: 'Duh vaje' }, OK);
saved = JSON.parse(store.get(KEY));
check(r.status === 200 && saved[0].kdo === 'Tone' && saved[0].izostal === true && saved[0].minute === 0, 'izostanek: minute 0, najnovejši prvi');
r = await call(env, '/zbor/zamude', 'GET', undefined, OK);
const list = (await r.json()).zapisi;
check(list.length === 2 && list[0].kdo === 'Tone' && list[1].kdo === 'Janez Bas', 'GET vrne oba, najnovejši prvi');

// ── Preverjanje vnosa ──
const bad = async (patch, msg) => {
  const rr = await call(env, '/zbor/zamuda', 'POST', { ...veljaven, zakaj: 'drug izgovor ' + Math.random(), ...patch }, OK);
  check(rr.status === 400, msg);
};
await bad({ kdo: '   ' }, 'prazno ime zavrnjeno');
await bad({ zakaj: '  ' }, 'prazen izgovor zavrnjen');
await bad({ datum: '2026-13-40' }, 'neobstoječ datum zavrnjen');
await bad({ datum: '25. 11. 2026' }, 'napačna oblika datuma zavrnjena');
await bad({ datum: '2019-12-31' }, 'predaven datum zavrnjen');
await bad({ datum: new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10) }, 'datum v prihodnosti zavrnjen');
await bad({ dogodek: 'pijanka' }, 'neznan dogodek zavrnjen');
await bad({ minute: 0 }, 'zamuda 0 min brez izostanka zavrnjena');
await bad({ minute: 241 }, 'zamuda nad 240 min zavrnjena');
await bad({ minute: 'dolgo' }, 'zamuda ni število: zavrnjena');
r = await call(env, '/zbor/zamuda', 'POST', { ...veljaven, zakaj: 'x'.repeat(500), kdo: 'k'.repeat(200) }, OK);
saved = JSON.parse(store.get(KEY));
check(r.status === 200 && saved[0].zakaj.length === 200 && saved[0].kdo.length === 40, 'predolgo besedilo obrezano (200 / 40)');
const nBefore = JSON.parse(store.get(KEY)).length;
r = await call(env, '/zbor/zamuda', 'POST', { ...veljaven, website: 'spam', zakaj: 'honeypot' }, OK);
check(r.status === 200 && JSON.parse(store.get(KEY)).length === nBefore, 'honeypot: ok, a brez zapisa');
r = await call(env, '/zbor/zamude', 'POST', {}, OK);
check(r.status === 405, 'napačna metoda: 405');

// ── Brisanje ──
const id = JSON.parse(store.get(KEY))[1].id;
const nPred = JSON.parse(store.get(KEY)).length;
r = await call(env, '/zbor/izbrisi', 'POST', { id }, OK);
const po = JSON.parse(store.get(KEY));
check(r.status === 200 && po.length === nPred - 1 && !po.some(i => i.id === id), 'brisanje odstrani natanko en zapis');
r = await call(env, '/zbor/izbrisi', 'POST', { id }, OK);
check(r.status === 404, 'ponovno brisanje istega: 404');
r = await call(env, '/zbor/izbrisi', 'POST', {}, OK);
check(r.status === 404 && JSON.parse(store.get(KEY)).length === po.length, 'brisanje brez id ne izbriše ničesar');

// ── Pohvala za pravočasnost (tip: "pravocasen"): brez minut, izgovora in kazni; ena na osebo, dan in dogodek ──
const pohv = { tip: 'pravocasen', kdo: ' Miha  Tenor ', datum: danes, dogodek: 'vaja', minute: 99, zakaj: 'ne shrani', kazen: 'ne shrani', izostal: true };
r = await call(env, '/zbor/zamuda', 'POST', pohv);
check(r.status === 401, 'pohvala brez gesla: 401');
const nP0 = JSON.parse(store.get(KEY)).length;
r = await call(env, '/zbor/zamuda', 'POST', pohv, OK);
let pz = JSON.parse(store.get(KEY));
check(r.status === 200 && pz.length === nP0 + 1 && pz[0].tip === 'pravocasen' && pz[0].kdo === 'Miha Tenor' && pz[0].minute === 0
  && pz[0].izostal === false && pz[0].zakaj === '' && !('kazen' in pz[0]), 'pohvala: minute 0, brez izgovora in kazni (ne verjame odjemalcu)');
r = await call(env, '/zbor/zamuda', 'POST', { ...pohv, kdo: 'MIHA TENOR' }, OK);
check(r.status === 200 && JSON.parse(store.get(KEY)).length === nP0 + 1, 'pohvala: dvojnik (osebe, dan, dogodek) se ne zapiše');
r = await call(env, '/zbor/zamuda', 'POST', { ...pohv, dogodek: 'nastop' }, OK);
check(JSON.parse(store.get(KEY)).length === nP0 + 2, 'pohvala: drug dogodek istega dne se zapiše');
r = await call(env, '/zbor/zamuda', 'POST', { tip: 'pravocasen', kdo: ' ', datum: danes, dogodek: 'vaja' }, OK);
check(r.status === 400, 'pohvala brez imena: 400');
r = await call(env, '/zbor/zamuda', 'POST', { tip: 'pravocasen', kdo: 'X', datum: '2026-13-40', dogodek: 'vaja' }, OK);
check(r.status === 400, 'pohvala z neveljavnim datumom: 400');
r = await call(env, '/zbor/zamuda', 'POST', { tip: 'pravocasen', kdo: 'X', datum: danes, dogodek: 'pijanka' }, OK);
check(r.status === 400, 'pohvala z neznanim dogodkom: 400');

// ── Kazenska blagajna: POST /zbor/placilo ──
const vsi = JSON.parse(store.get(KEY));
const zam = vsi.find(i => i.tip !== 'pravocasen'), poh = vsi.find(i => i.tip === 'pravocasen');
r = await call(env, '/zbor/placilo', 'POST', { ids: [zam.id], placano: true });
check(r.status === 401 && !JSON.parse(store.get(KEY)).some(i => i.placano), 'plačilo brez gesla: 401, nič spremenjeno');
r = await call(env, '/zbor/placilo', 'GET', undefined, OK);
check(r.status === 405, 'plačilo z GET: 405');
r = await call(env, '/zbor/placilo', 'POST', { ids: [zam.id], placano: 'da' }, OK);
check(r.status === 400, 'plačilo: placano mora biti boolean');
r = await call(env, '/zbor/placilo', 'POST', { ids: [], placano: true }, OK);
check(r.status === 400, 'plačilo: prazen seznam ids: 400');
r = await call(env, '/zbor/placilo', 'POST', { ids: Array.from({ length: 51 }, (_, i) => 'id' + i), placano: true }, OK);
check(r.status === 400, 'plačilo: več kot 50 id-jev: 400');
r = await call(env, '/zbor/placilo', 'POST', { ids: ['nepoznan'], placano: true }, OK);
check(r.status === 404, 'plačilo neznanega zapisa: 404');
r = await call(env, '/zbor/placilo', 'POST', { ids: [poh.id], placano: true }, OK);
check(r.status === 404 && !JSON.parse(store.get(KEY)).find(i => i.id === poh.id).placano, 'pohvala ne more biti plačana');
r = await call(env, '/zbor/placilo', 'POST', { ids: [zam.id, poh.id], placano: true }, OK);
let po1 = JSON.parse(store.get(KEY)).find(i => i.id === zam.id);
check(r.status === 200 && (await r.json()).spremenjenih === 1 && po1.placano === true && /^\d{4}-/.test(po1.placanoTs), 'plačilo: zapis označen, čas plačila zapisan');
r = await call(env, '/zbor/placilo', 'POST', { ids: [zam.id], placano: false }, OK);
po1 = JSON.parse(store.get(KEY)).find(i => i.id === zam.id);
check(r.status === 200 && !('placano' in po1) && !('placanoTs' in po1), 'plačilo: preklic spet odpre kazen');
r = await call(env, '/zbor/zamuda', 'POST', { ...veljaven, zakaj: 'odjemalec ne sme sam plačati', placano: true }, OK);
check(!('placano' in JSON.parse(store.get(KEY))[0]), 'novi zapis ne more priti kot že plačan');

// ── Poškodovana shramba se ne prepiše ──
const dobra = store.get(KEY);
store.set(KEY, '{pokvarjeno');
r = await call(env, '/zbor/zamuda', 'POST', { ...veljaven, zakaj: 'po okvari' }, OK);
check(r.status === 500 && store.get(KEY) === '{pokvarjeno', 'poškodovana shramba: 500 in ni prepisana');
store.set(KEY, dobra);

// ── Prihajajoči termini: /zbor/dogodki, /zbor/dogodek, /zbor/dogodek-izbrisi (ločena shramba od zamud) ──
const DKEY = 'feedback/zbor-dogodki.json';
const dan = (n) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);
const IPD = '5.5.5.5';
const zamudeSkupaj = store.get(KEY);
r = await call(env, '/zbor/dogodki', 'GET', undefined, undefined, IPD);
check(r.status === 401, 'termini: branje brez gesla 401');
r = await call(env, '/zbor/dogodek', 'POST', { dogodek: 'nastop', datum: dan(1), ura: '15:00' }, {}, IPD);
check(r.status === 401 && !store.has(DKEY), 'termini: zapis brez gesla 401, nič shranjeno');
r = await call(env, '/zbor/dogodek-izbrisi', 'POST', { id: 'x' }, {}, IPD);
check(r.status === 401, 'termini: brisanje brez gesla 401');
r = await call(mkEnv(null), '/zbor/dogodki', 'GET', undefined, { Authorization: 'Bearer undefined' }, IPD);
check(r.status === 503, 'termini: brez skrivnosti na strežniku je zaprto (503)');
r = await call(env, '/zbor/dogodki', 'GET', undefined, OK, IPD);
check(r.status === 200 && (await r.json()).dogodki.length === 0, 'termini: prazen seznam');
r = await call(env, '/zbor/dogodek', 'POST', { dogodek: 'vaja', datum: dan(5), ura: '19:30', kje: ' Dvorana  ', opomba: 'Prinesi note' }, OK, IPD);
check(r.status === 200, 'termini: veljaven vnos sprejet');
r = await call(env, '/zbor/dogodek', 'POST', { dogodek: 'nastop', datum: dan(1), ura: '15:00' }, OK, IPD);
check(r.status === 200, 'termini: drug vnos sprejet');
let dg = JSON.parse(store.get(DKEY));
check(dg.length === 2 && dg.find(d => d.ura === '19:30').kje === 'Dvorana' && !('ip' in dg[0]) && dg[0].id && !('kje' in dg.find(d => d.ura === '15:00')), 'termini: shranjeno obrezano, neobvezno polje samo če je vpisano, brez IP');
r = await call(env, '/zbor/dogodki', 'GET', undefined, OK, IPD);
let dl = (await r.json()).dogodki;
check(dl.length === 2 && dl[0].datum === dan(1) && dl[1].datum === dan(5), 'termini: GET vrne najbližjega prvega');
r = await call(env, '/zbor/dogodek', 'POST', { dogodek: 'nastop', datum: dan(1), ura: '15:00' }, OK, IPD);
check(r.status === 200 && JSON.parse(store.get(DKEY)).length === 2, 'termini: isti datum, dogodek in ura se ne podvoji');
const badD = async (patch, msg) => {
  const rr = await call(env, '/zbor/dogodek', 'POST', { dogodek: 'vaja', datum: dan(3), ura: '18:00', ...patch }, OK, IPD);
  check(rr.status === 400, msg);
};
await badD({ datum: dan(-2) }, 'termini: datum v preteklosti zavrnjen');
await badD({ datum: '2026-13-40' }, 'termini: neobstoječ datum zavrnjen');
await badD({ datum: '1. 12. 2026' }, 'termini: napačna oblika datuma zavrnjena');
await badD({ datum: dan(900) }, 'termini: datum čez dve leti zavrnjen');
await badD({ dogodek: 'pijanka' }, 'termini: neznan dogodek zavrnjen');
for (const u of ['', '7:00', '24:00', '15:60', '15.00', 1500]) await badD({ ura: u }, 'termini: ura "' + u + '" zavrnjena');
r = await call(env, '/zbor/dogodek', 'POST', { dogodek: 'vaja', datum: dan(9), ura: '20:15', kje: 'k'.repeat(200), opomba: 'o'.repeat(500) }, OK, IPD);
dg = JSON.parse(store.get(DKEY));
const dolgi = dg.find(d => d.datum === dan(9));
check(r.status === 200 && dolgi.kje.length === 60 && dolgi.opomba.length === 140, 'termini: predolgo besedilo obrezano (60 / 140)');
const nD = dg.length;
r = await call(env, '/zbor/dogodek', 'POST', { dogodek: 'vaja', datum: dan(11), ura: '19:00', website: 'spam' }, OK, IPD);
check(r.status === 200 && JSON.parse(store.get(DKEY)).length === nD, 'termini: honeypot ok, a brez zapisa');
r = await call(env, '/zbor/dogodki', 'POST', {}, OK, IPD);
check(r.status === 405, 'termini: napačna metoda 405');
r = await call(env, '/zbor/dogodek', 'GET', undefined, OK, IPD);
check(r.status === 405, 'termini: GET na /zbor/dogodek 405');
// starih terminov (> 14 dni) ob zapisu ne hranimo; mlajši (včeraj) ostanejo
store.set(DKEY, JSON.stringify([
  { id: 'star', ts: '2026-01-01T00:00:00Z', dogodek: 'vaja', datum: dan(-30), ura: '19:00' },
  { id: 'vceraj', ts: '2026-01-01T00:00:00Z', dogodek: 'vaja', datum: dan(-1), ura: '19:00' }]));
await call(env, '/zbor/dogodek', 'POST', { dogodek: 'vaja', datum: dan(2), ura: '19:00' }, OK, IPD);
const ids = JSON.parse(store.get(DKEY)).map(d => d.id);
check(!ids.includes('star') && ids.includes('vceraj') && ids.length === 2, 'termini: pretekli (nad 14 dni) odrezani, včerajšnji ostane');
const idD = JSON.parse(store.get(DKEY)).find(d => d.id !== 'vceraj').id;
r = await call(env, '/zbor/dogodek-izbrisi', 'POST', { id: idD }, OK, IPD);
check(r.status === 200 && !JSON.parse(store.get(DKEY)).some(d => d.id === idD), 'termini: brisanje odstrani natanko en termin');
r = await call(env, '/zbor/dogodek-izbrisi', 'POST', { id: idD }, OK, IPD);
check(r.status === 404, 'termini: ponovno brisanje 404');
r = await call(env, '/zbor/dogodek-izbrisi', 'POST', {}, OK, IPD);
check(r.status === 404 && JSON.parse(store.get(DKEY)).length === 1, 'termini: brisanje brez id ne izbriše ničesar');
const dobriD = store.get(DKEY);
store.set(DKEY, '{pokvarjeno');
r = await call(env, '/zbor/dogodek', 'POST', { dogodek: 'vaja', datum: dan(4), ura: '19:00' }, OK, IPD);
check(r.status === 500 && store.get(DKEY) === '{pokvarjeno', 'termini: poškodovana shramba 500 in ni prepisana');
store.set(DKEY, dobriD);
check(store.get(KEY) === zamudeSkupaj, 'termini ne dotaknejo dnevnika zamud');

// ── Zaklep po IP: 10 napačnih, nato niti pravo geslo ne pomaga (drug IP ni prizadet) ──
for (let i = 0; i < 10; i++) await call(env, '/zbor/zamude', 'GET', undefined, { Authorization: 'Bearer ugibam' + i }, '9.9.9.9');
r = await call(env, '/zbor/zamude', 'GET', undefined, OK, '9.9.9.9');
check(r.status === 401, 'po 10 napačnih poskusih je IP zaklenjen (tudi pravo geslo 401)');
r = await call(env, '/zbor/zamude', 'GET', undefined, OK, '8.8.8.8');
check(r.status === 200, 'drug IP ni zaklenjen');
// uspešna prijava izbriše števec napačnih poskusov
for (let i = 0; i < 3; i++) await call(env, '/zbor/zamude', 'GET', undefined, { Authorization: 'Bearer ne' + i }, '7.7.7.7');
await call(env, '/zbor/zamude', 'GET', undefined, OK, '7.7.7.7');
check(!kvm.has('zbor_fail:7.7.7.7'), 'uspešna prijava ponastavi števec');

// ── Omejitev vnosov po IP (60/uro) ──
let zadnji;
for (let i = 0; i < 70; i++) zadnji = await call(env, '/zbor/zamuda', 'POST', { ...veljaven, zakaj: 'rl ' + i }, OK, '6.6.6.6');
check(zadnji.status === 429, 'omejitev vnosov po IP (429)');

// ── Izbirnik dogodka na strani ↔ seznam v workerju ──
const html = fs.readFileSync(path.join(ROOT, 'reciskipobi', 'index.html'), 'utf8');
const workerList = /const ZBOR_DOGODKI = \[([^\]]*)\]/.exec(src)[1].match(/"([^"]+)"/g).map(s => s.slice(1, -1));
const pageList = [...html.matchAll(/name="dogodek" value="([^"]+)"/g)].map(m => m[1]);
check(JSON.stringify(workerList) === JSON.stringify(pageList), 'dogodki na strani = dogodki v workerju (' + pageList.join(', ') + ')');
const dgSel = /<select id="dgTip">([\s\S]*?)<\/select>/.exec(html);
const dgList = dgSel ? [...dgSel[1].matchAll(/<option value="([^"]+)"/g)].map(m => m[1]) : [];
check(JSON.stringify(workerList) === JSON.stringify(dgList), 'izbirnik terminov na strani = dogodki v workerju');
check(/api\("\/zbor\/dogodki"/.test(html) && /api\("\/zbor\/dogodek","POST"/.test(html) && /api\("\/zbor\/dogodek-izbrisi","POST"/.test(html), 'stran kliče vse tri končne točke terminov');
const seedM = /var SEED=\[(\{[^\]]*\})\];/.exec(html);
check(!!seedM && /dogodek:"nastop"/.test(seedM[1]) && /datum:"2026-11-29"/.test(seedM[1]) && /ura:"15:00"/.test(seedM[1]) && /zacetni:true/.test(seedM[1]), 'začetni vnos: nastop 29. 11. 2026, zbor ob 15:00 (ne more se izbrisati)');
check(/<meta name="robots" content="noindex,nofollow">/.test(html), 'stran je noindex');
check(!/indoor|tempinf|notranji senzor/i.test(html), 'stran ne omenja notranjih meritev');
// Polži: lestvica iz minut (ista funkcija določa komentar po vnosu, polže v dnevniku in seštevek na zidu)
const zvSrc = /function zvezdice\(min,izostal\)\{[\s\S]*?\n\}/.exec(html);
const zvezdice = zvSrc && new Function(zvSrc[0] + '; return zvezdice;')();
check(!!zvezdice, 'funkcija zvezdice je na strani');
if (zvezdice) {
  const tabela = [[1, 1], [5, 1], [6, 2], [15, 2], [16, 3], [30, 3], [31, 4], [60, 4], [61, 5], [240, 5]];
  check(tabela.every(([m, z]) => zvezdice(m, false) === z), 'polži po minutah: 1–5→1, 6–15→2, 16–30→3, 31–60→4, nad 60→5');
  check(zvezdice(0, true) === 5, 'duh vaje dobi 5 polžev');
  const maxZv = Math.max(...[1, 10, 20, 45, 90].map(m => zvezdice(m, false)));
  check(maxZv === 5 && /ZVEZDE_IME=\[("[^"]+",?){5}\]/.test(html), 'pet imen stopenj, nobenih zajcev');
  check([1, 2, 3, 4, 5].every((i) => html.includes('<symbol id="gz' + i + '"')) && html.includes('"#gz"+(i%5+1)'), 'pet različnih polžev, i-ti v vrsti je i-ta stopnja');
  check(html.includes('gzDist(lvVse)') && html.includes('gzTotal(a.zv,a.lv)') && html.includes('GZ_RAZPON'), 'zid sramote: polži po stopnjah (skupno in pri vsakem pevcu)');
}
// ── Model na strani (blok MODEL): cenik, serije, tedni, dnevi. Izrezano iz prave strani, brez DOM-a ──
const modelSrc = /\/\*MODEL:START\*\/([\s\S]*?)\/\*MODEL:END\*\//.exec(html);
check(!!modelSrc, 'stran ima blok MODEL (čiste funkcije za cenik, serije in grafe)');
if (modelSrc) {
  const help = ['p2', 'ymd', 'parse'].map(n => new RegExp('function ' + n + '\\([^)]*\\)\\{[^\\n]*\\}').exec(html)?.[0] ?? '').join('\n');
  const M = new Function('NBSP', help + modelSrc[1] + '; return {zvezdice,CENIK_C,cenaC,fmtE,jeZ,dolgC,serijaTocnosti,mondayOf,tedni,dnevi,ymd,parse,prihajajoci,dniDo,kdajBes,zlij};')(' ');
  check(JSON.stringify(M.CENIK_C) === '[50,100,200,300,500]', 'cenik: 0,50 / 1 / 2 / 3 / 5 €');
  check(M.cenaC(3, false) === 50 && M.cenaC(12, false) === 100 && M.cenaC(20, false) === 200 && M.cenaC(45, false) === 300 && M.cenaC(0, true) === 500 && M.cenaC(120, false) === 500, 'cena sledi polžu (duh vaje in čez 60 min = 5 €)');
  check(M.fmtE(150) === '1,50 €' && M.fmtE(500) === '5,00 €' && M.fmtE(50) === '0,50 €', 'denar: decimalna vejica, nelomljiv presledek pred €');
  check(M.dolgC({ minute: 20, placano: true }) === 0 && M.dolgC({ minute: 20 }) === 200 && M.dolgC({ tip: 'pravocasen', minute: 0 }) === 0, 'dolg: plačana kazen in pohvala ne štejeta');
  // serije pravočasnosti: od zadnje vaje nazaj do prve zamude; druge vrste dogodkov ne štejejo
  const Z = (kdo, datum, extra = {}) => ({ kdo, datum, dogodek: 'vaja', minute: 5, ...extra }), P = (kdo, datum, extra = {}) => ({ kdo, datum, dogodek: 'vaja', minute: 0, tip: 'pravocasen', ...extra });
  const ser = Object.fromEntries(M.serijaTocnosti([
    P('Anže', '2026-11-03'), P('Anže', '2026-11-10'), Z('Anže', '2026-10-27'), P('Anže', '2026-10-20'),
    Z('Miha', '2026-11-10'), P('Miha', '2026-11-03'),
    P('Tone', '2026-11-10', { dogodek: 'nastop' }), P('Tone', '2026-11-03'),
    P('Peter', '2026-11-10'), Z('Peter', '2026-11-10'),
  ]).map(x => [x.ime, x.serija]));
  check(ser['Anže'] === 2 && ser['Miha'] === 0 && ser['Tone'] === 1 && ser['Peter'] === 0, 'serija pravočasnosti: zamuda jo prekine, nastop se ne šteje, zamuda istega dne zmaga');
  // tedni: pon–ned, 12 tednov, tekoči zadnji; točke = minute + 60 za duha; pohvale ne štejejo
  const danesD = new Date(2026, 10, 26);   // četrtek 26. 11. 2026
  const t = M.tedni([Z('A', '2026-11-23', { minute: 20 }), Z('A', '2026-11-29', { minute: 10 }), Z('B', '2026-11-22', { minute: 7 }), Z('C', '2026-11-25', { minute: 0, izostal: true }), P('D', '2026-11-24')], danesD, 12);
  check(t.length === 12 && t[11].start === '2026-11-23' && t[10].start === '2026-11-16' && t[0].start === '2026-09-07', 'tedni: 12 tednov, začetek ob ponedeljkih, tekoči zadnji');
  check(t[11].tocke === 90 && t[11].n === 3 && t[10].tocke === 7 && t[10].n === 1, 'tedni: nedelja spada v prejšnji teden, duh šteje 60, pohvala ne šteje');
  const dn = M.dnevi([Z('A', '2026-11-20', { minute: 3 }), Z('B', '2026-11-20', { minute: 50 }), P('C', '2026-11-20'), P('C', '2026-11-21')]);
  check(dn['2026-11-20'].lvl === 4 && dn['2026-11-20'].n === 2 && dn['2026-11-20'].p === 1 && dn['2026-11-21'].lvl === 0 && dn['2026-11-21'].p === 1, 'koledar: najhujši polž dneva, pohvale posebej');
  // prihajajoči termini: današnji še šteje, pretekli ne, najbližji prvi (najprej po datumu, nato po uri)
  const T = (datum, ura, dogodek = 'vaja') => ({ datum, ura, dogodek });
  const pr = M.prihajajoci([T('2026-11-27', '19:00'), T('2026-12-03', '19:00'), T('2026-11-29', '15:00', 'nastop'), T('2026-11-26', '19:00'), T('2026-11-29', '10:00'), T('2026-11-28', '09:00')], '2026-11-28');
  check(pr.length === 4 && pr[0].datum === '2026-11-28' && pr[1].ura === '10:00' && pr[2].dogodek === 'nastop' && pr[3].datum === '2026-12-03', 'termini: današnji šteje, pretekli ne, urejeno po datumu in uri');
  check(M.kdajBes('2026-11-28', '2026-11-28') === 'danes' && M.kdajBes('2026-11-29', '2026-11-28') === 'jutri' && M.kdajBes('2026-12-03', '2026-11-28') === 'čez 5 dni' && M.kdajBes('2026-12-01', '2026-11-28') === 'čez 3 dni', 'termini: danes, jutri, čez N dni (tudi čez mejo meseca)');
  check(M.dniDo('2027-01-02', '2026-12-30') === 3, 'termini: dnevi do termina čez novo leto');
  const zl = M.zlij([T('2026-11-29', '15:00', 'nastop')], [T('2026-11-29', '15:00', 'nastop'), T('2026-11-29', '15:00', 'vaja')]);
  check(zl.length === 2 && zl.filter(d => d.dogodek === 'nastop').length === 1, 'termini: začetni vnos zamenja strežniški (isti datum, dogodek, ura), drugačen ostane');
}
check(/data-tip="pravocasen"/.test(html) && /tip:"pravocasen"/.test(html), 'stran ima vnos pravočasnosti');
check(/api\("\/zbor\/placilo"/.test(html) && /id="p-blagajna"/.test(html), 'stran ima kazensko blagajno');
check(/prefers-reduced-motion:no-preference/.test(html) && !/\.anim [^{]*\{animation:[^}]*infinite[^}]*\}[^@]*@media/.test(html), 'animacije polžev so samo ob dovoljenem gibanju');
check(['grafTedni', 'grafKoledar', 'grafPevci', 'podij', 'naslovi'].every(f => new RegExp('function ' + f + '\\(').test(html)), 'zid: grafi, podij in naslovi');
const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'reciskipobi', 'manifest.json'), 'utf8'));
check(manifest.scope === '/reciskipobi/' && manifest.start_url === '/reciskipobi/' && manifest.display === 'standalone', 'manifest ima lasten obseg /reciskipobi/');
check(manifest.icons.every(i => i.src === 'icon.svg' || fs.existsSync(path.join(ROOT, 'reciskipobi', i.src))), 'ikone iz manifesta obstajajo');
check(/id="namesti"/.test(html) && /beforeinstallprompt/.test(html) && /rel="manifest"/.test(html), 'gumb za namestitev in povezava na manifest');

fs.rmSync(dir, { recursive: true, force: true });
process.exit(fails ? 1 : 0);
