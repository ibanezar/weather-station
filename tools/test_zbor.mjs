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

// ── Poškodovana shramba se ne prepiše ──
const dobra = store.get(KEY);
store.set(KEY, '{pokvarjeno');
r = await call(env, '/zbor/zamuda', 'POST', { ...veljaven, zakaj: 'po okvari' }, OK);
check(r.status === 500 && store.get(KEY) === '{pokvarjeno', 'poškodovana shramba: 500 in ni prepisana');
store.set(KEY, dobra);

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
check(/<meta name="robots" content="noindex,nofollow">/.test(html), 'stran je noindex');
check(!/indoor|tempinf|notranji senzor/i.test(html), 'stran ne omenja notranjih meritev');
// Črne pike (zvezdice): lestvica iz minut (ista funkcija določa komentar po vnosu, zvezdice v dnevniku in seštevek na zidu)
const zvSrc = /function zvezdice\(min,izostal\)\{[\s\S]*?\n\}/.exec(html);
const zvezdice = zvSrc && new Function(zvSrc[0] + '; return zvezdice;')();
check(!!zvezdice, 'funkcija zvezdice je na strani');
if (zvezdice) {
  const tabela = [[1, 1], [5, 1], [6, 2], [15, 2], [16, 3], [30, 3], [31, 4], [60, 4], [61, 5], [240, 5]];
  check(tabela.every(([m, z]) => zvezdice(m, false) === z), 'zvezdice po minutah: 1–5→1, 6–15→2, 16–30→3, 31–60→4, nad 60→5');
  check(zvezdice(0, true) === 5, 'duh vaje dobi 5 črnih pik');
  const maxZv = Math.max(...[1, 10, 20, 45, 90].map(m => zvezdice(m, false)));
  check(maxZv === 5 && /ZVEZDE_IME=\[("[^"]+",?){5}\]/.test(html), 'pet imen stopenj, nobene bele pike');
}
const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'reciskipobi', 'manifest.json'), 'utf8'));
check(manifest.scope === '/reciskipobi/' && manifest.start_url === '/reciskipobi/' && manifest.display === 'standalone', 'manifest ima lasten obseg /reciskipobi/');
check(manifest.icons.every(i => i.src === 'icon.svg' || fs.existsSync(path.join(ROOT, 'reciskipobi', i.src))), 'ikone iz manifesta obstajajo');
check(/id="namesti"/.test(html) && /beforeinstallprompt/.test(html) && /rel="manifest"/.test(html), 'gumb za namestitev in povezava na manifest');

fs.rmSync(dir, { recursive: true, force: true });
process.exit(fails ? 1 : 0);
