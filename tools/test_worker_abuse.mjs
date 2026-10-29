/*
 * tools/test_worker_abuse.mjs — varovalke javnih vnosov v PRAVEM worker.js (lažen R2 in KV):
 *   - /push/subscribe sprejme samo naslove znanih push strežnikov (https) in je omejen po IP,
 *   - /napovej/vnos je omejen po IP (sicer bi mreža napovedi zasedla vrh lestvice),
 *   - /igra/rezultat in /crnivec/igra/rezultat sta omejena po IP, slovar igralcev ima zgornjo mejo,
 *   - telo, ki ni objekt, in polja, ki niso nizi, ne povzročijo 500.
 * Poganjanje: node tools/test_worker_abuse.mjs
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'abuse-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);
const mod = await import(pathToFileURL(file).href);

const store = new Map(), kvm = new Map();
const env = {
  PHOTOS_R2: { get: async k => store.has(k) ? { text: async () => store.get(k) } : null, put: async (k, v) => { store.set(k, v); } },
  COUNTER_KV: { get: async k => kvm.get(k) ?? null, put: async (k, v) => { kvm.set(k, v); }, delete: async k => { kvm.delete(k); } },
};
const ctx = { waitUntil() {}, passThroughOnException() {} };
let fails = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };
let ipN = 0;
const call = (p, method = 'GET', body, ip) => mod.default.fetch(new Request('https://w.test' + p, {
  method, headers: { Origin: 'https://meteorec.si', 'Content-Type': 'application/json', 'CF-Connecting-IP': ip || ('9.9.9.' + (++ipN)) },
  body: body === undefined ? undefined : (typeof body === 'string' ? body : JSON.stringify(body)) }), env, ctx);

const sub = ep => ({ subscription: { endpoint: ep, keys: { p256dh: 'p'.repeat(87), auth: 'a'.repeat(22) } } });

// ── push: samo znani strežniki ──
for (const ep of ['https://fcm.googleapis.com/fcm/send/abc', 'https://updates.push.services.mozilla.com/wpush/v2/x',
                  'https://wns2-par02p.notify.windows.com/w/?token=1', 'https://web.push.apple.com/Q1']) {
  const r = await call('/push/subscribe', 'POST', sub(ep));
  check(r.status === 200, 'sprejme ' + new URL(ep).hostname);
}
for (const ep of ['http://fcm.googleapis.com/x', 'https://evil.example/hook', 'https://fcm.googleapis.com.evil.example/x',
                  'https://fcm.googleapis.com:8443/x', 'https://127.0.0.1/x', 'javascript:alert(1)', 'https://web.push.apple.com/' + 'a'.repeat(1100)]) {
  const r = await call('/push/subscribe', 'POST', sub(ep));
  check(r.status === 400, 'zavrne ' + ep.slice(0, 50));
}
for (const site of ['crnivec', 'migrena']) {
  const r = await call('/push/subscribe', 'POST', { ...sub('https://evil.example/x'), site });
  check(r.status === 400, 'zavrne tuj naslov tudi za ' + site);
}
let r = await call('/push/subscribe', 'POST', 'null');
check(r.status === 400, 'telo null ni 500');
let last;
for (let i = 0; i < 31; i++) last = await call('/push/subscribe', 'POST', sub('https://fcm.googleapis.com/fcm/send/r' + i), '5.5.5.5');
check(last.status === 429, 'prijave omejene po IP (429)');

// ── napoved: omejitev po IP ──
const jutri = new Date(Date.now() + 86400000 + 3600000).toISOString().slice(0, 10);
const nap = i => `/napovej/vnos?datum=${jutri}&igralec=igralec${String(i).padStart(4, '0')}&tmax=12&tmin=3&dez=0`;
const ljJutri = (await call(nap(0), 'POST', undefined, '6.6.6.6')).status; // 200 ali 400 (datum po Ljubljani)
if (ljJutri === 400) {
  console.log('(preskočeno: datum jutrišnjega dne po Ljubljani se razlikuje, test ne meri omejitve)');
} else {
  let st;
  for (let i = 1; i <= 11; i++) st = (await call(nap(i), 'POST', undefined, '6.6.6.6')).status;
  check(st === 429, 'napovej/vnos omejen po IP (429)');
}

// ── igra: omejitev in zgornja meja slovarja ──
const dan = new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Ljubljana' });
const igr = i => `/igra/rezultat?koridor=crna&km=5&datum=${dan}&igralec=igralec${String(i).padStart(5, '0')}`;
r = await call(igr(1), 'POST', undefined, '7.7.7.7');
check(r.status === 200, 'rezultat igre sprejet');
for (let i = 2; i <= 61; i++) last = await call(igr(i), 'POST', undefined, '7.7.7.7');
check(last.status === 429, 'rezultati igre omejeni po IP (429)');
for (let i = 100; i < 1100; i++) await call(igr(i), 'POST', undefined, '8.8.' + (i % 250) + '.' + Math.floor(i / 250));
const obj = JSON.parse(kvm.get('igra:rekord:crna'));
check(Object.keys(obj).length <= 1000, 'slovar igralcev ima zgornjo mejo (' + Object.keys(obj).length + ')');
const crn = i => `/crnivec/igra/rezultat?datum=${dan}&cas=${200 + i}&igralec=crnigralec${String(i).padStart(4, '0')}`;
for (let i = 1; i <= 61; i++) last = await call(crn(i), 'POST', undefined, '4.4.4.4');
check(last.status === 429, 'črnivec igra omejena po IP (429)');

// ── besedilna polja, ki niso nizi ──
r = await call('/gobe/opazovanje', 'POST', { vrsta: { a: 1 }, obmocje: 5, kolicina: 'nekaj' });
check(r.status < 500, 'gobe/opazovanje: polje, ki ni niz, ni 500 (' + r.status + ')');
r = await call('/nevihte/porocilo', 'POST', { tip: 'naliv', regija: 'Savinjska', kraj: ['x'], opis: 7 });
check(r.status < 500, 'nevihte/porocilo: polje, ki ni niz, ni 500 (' + r.status + ')');
r = await call('/anketa', 'POST', 'null');
check(r.status === 400, 'anketa: telo null je 400');

// ── opažanja in komentarji: omejitev po IP ──
for (let i = 0; i < 11; i++) last = await call('/observations', 'POST', { type: 'soncno' }, '3.3.3.3');
check(last.status === 429, 'opažanja vremena omejena po IP (429)');
r = await call('/observations', 'POST', 'null');
check(r.status === 400, 'opažanja: telo null je 400');
for (let i = 0; i < 16; i++) last = await call('/blog-comments', 'POST', { slug: 'test-clanek', comment: 'komentar ' + i }, '2.2.2.2');
check(last.status === 429, 'komentarji omejeni po IP (429)');
r = await call('/blog-comments', 'POST', { slug: 'test-clanek', comment: { x: 1 } });
check(r.status < 500, 'komentar, ki ni niz, ni 500 (' + r.status + ')');

fs.rmSync(dir, { recursive: true, force: true });
process.exit(fails ? 1 : 0);
