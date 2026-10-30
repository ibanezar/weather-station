/*
 * tools/test_podjetja_worker.mjs — preizkus POST/GET /api/povprasevanje na PRAVEM worker.js
 * (lažen R2, KV in Resend). Poganjanje: node tools/test_podjetja_worker.mjs
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'povprasevanje-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);
const mod = await import(pathToFileURL(file).href);

const KEY = 'feedback/povprasevanja.json';
const store = new Map(), kvm = new Map();
const mails = [];
const realFetch = globalThis.fetch;
globalThis.fetch = async (u, init) => {
  if (String(u).startsWith('https://api.resend.com/')) { mails.push(JSON.parse(init.body)); return new Response('{}'); }
  return realFetch(u, init);
};
const env = {
  DELETE_SECRET: 's3cret',
  RESEND_API_KEY: 'k',
  PHOTOS_R2: { get: async k => store.has(k) ? { text: async () => store.get(k) } : null, put: async (k, v) => { store.set(k, v); } },
  COUNTER_KV: { get: async k => kvm.get(k) ?? null, put: async (k, v) => { kvm.set(k, v); }, delete: async k => { kvm.delete(k); } },
};
const pending = [];
const ctx = { waitUntil(p) { pending.push(p); }, passThroughOnException() {} };
let fails = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };
let ipN = 0;
const call = (p, method = 'GET', body, headers = {}) => mod.default.fetch(new Request('https://w.test' + p, {
  method, headers: { Origin: 'https://meteorec.si', 'Content-Type': 'application/json', 'CF-Connecting-IP': '9.9.9.' + ipN, ...headers },
  body: body ? JSON.stringify(body) : undefined }), env, ctx);
const saved = () => JSON.parse(store.get(KEY) || '[]');

const ok = () => ({
  firma: 'Kmetija Test', kraj: 'sadovnjak nad vasjo', dejavnost: 'Kmetijstvo, sadjarstvo, vinogradništvo',
  postaj: '1', spremljati: ['pozeba', 'veter', 'izmišljeno'], wifi: 'Ne vem, preverite z mano',
  opomba: 'prosim za ogled', kontakt: 'janez@primer.si', soglasje: true, t: 15000, website: '',
  paket: 'pro', povezava: 'sim', segment: 'kmetija', utm_source: 'facebook', utm_campaign: 'jesen', utm_content: 'temno1', fbclid: 'abc',
});

let r = await call('/api/povprasevanje', 'POST', ok());
await Promise.all(pending);
check(r.status === 200, 'veljavno povpraševanje sprejeto');
let s = saved();
check(s.length === 1 && s[0].firma === 'Kmetija Test', 'shranjeno v R2');
check(JSON.stringify(s[0].spremljati) === JSON.stringify(['pozeba', 'veter']), 'neznane vrednosti »spremljati« odstranjene');
check(s[0].utm_content === 'temno1' && s[0].fbclid === 'abc' && s[0].paket === 'pro' && s[0].segment === 'kmetija', 'UTM, fbclid, paket in segment shranjeni');
check(!('ip' in s[0]) && !JSON.stringify(s[0]).includes('9.9.9'), 'IP se ne shrani');
check(mails.length === 1 && mails[0].to === 'filip.eremita@gmail.com' && mails[0].html.includes('Kmetija Test') && mails[0].html.includes('temno1'),
  'e-obvestilo lastniku vsebuje podatke in oglas');

ipN++;
r = await call('/api/povprasevanje', 'POST', { ...ok(), firma: 'Boter <b>', website: 'http://bot' });
check(r.status === 200 && saved().length === 1, 'honeypot: odgovor ok, a brez zapisa');
r = await call('/api/povprasevanje', 'POST', { ...ok(), firma: 'Prehiter', t: 800 });
check(r.status === 200 && saved().length === 1, 'prehitra oddaja (< 3 s): brez zapisa');
const brezT = ok(); delete brezT.t;
r = await call('/api/povprasevanje', 'POST', { ...brezT, firma: 'Brez časa' });
check(r.status === 200 && saved().length === 1, 'oddaja brez časa: brez zapisa');

const slabi = [
  [{ kontakt: '' }, 'brez kontakta'], [{ kontakt: 'nekaj' }, 'kontakt ni ne e-naslov ne telefon'],
  [{ kontakt: '123' }, 'prekratka telefonska'], [{ soglasje: false }, 'brez privolitve'], [{ soglasje: 'da' }, 'privolitev ni res true'],
  [{ firma: '  ' }, 'prazna firma'], [{ kraj: '' }, 'prazen kraj'], [{ dejavnost: 'Vesolje' }, 'neznana dejavnost'],
  [{ postaj: '99' }, 'neznano število postaj'], [{ wifi: 'morda' }, 'neznan WiFi odgovor'],
];
for (const [patch, ime] of slabi) {
  ipN++;
  r = await call('/api/povprasevanje', 'POST', { ...ok(), firma: 'X' + ime, ...patch });
  check(r.status === 400, 'zavrnjeno (400): ' + ime);
}
check(saved().length === 1, 'zavrnjena povpraševanja se ne shranijo');
for (const tel of ['041 123 456', '+386 41 123 456', '03/123-45-67']) {
  ipN++;
  r = await call('/api/povprasevanje', 'POST', { ...ok(), firma: 'Tel ' + tel, kontakt: tel });
  check(r.status === 200, 'telefonska številka sprejeta: ' + tel);
}
ipN++;
r = await call('/api/povprasevanje', 'POST', [1, 2]);
check(r.status === 400, 'telo, ki ni objekt, dá 400');
ipN++;
r = await mod.default.fetch(new Request('https://w.test/api/povprasevanje', { method: 'POST', headers: { Origin: 'https://meteorec.si', 'CF-Connecting-IP': '8.8.8.8' }, body: '{pokvarjeno' }), env, ctx);
check(r.status === 400, 'pokvarjen JSON dá 400');

ipN++;
const n0 = saved().length;
r = await call('/api/povprasevanje', 'POST', { ...ok(), firma: 'Dvojnik', kontakt: 'dvojnik@primer.si' });
r = await call('/api/povprasevanje', 'POST', { ...ok(), firma: 'Dvojnik', kontakt: 'dvojnik@primer.si' });
check(saved().length === n0 + 1, 'dvojni klik ne podvoji vnosa');

ipN++;
for (let i = 0; i < 6; i++) r = await call('/api/povprasevanje', 'POST', { ...ok(), firma: 'Omejitev ' + i });
check(r.status === 429, 'omejitev po IP (429 po 5 oddajah na uro)');

r = await call('/api/povprasevanje');
check(r.status === 401, 'GET brez žetona 401');
r = await call('/api/povprasevanje', 'GET', undefined, { Authorization: 'Bearer napacen' });
check(r.status === 401, 'GET s praznim žetonom 401');
r = await call('/api/povprasevanje', 'GET', undefined, { Authorization: 'Bearer s3cret' });
check(r.status === 200 && (await r.json()).povprasevanja.length >= 1, 'GET z žetonom vrne povpraševanja');
r = await mod.default.fetch(new Request('https://w.test/api/povprasevanje', { method: 'POST', headers: { Origin: 'https://zlobnez.si', 'Content-Type': 'application/json' }, body: JSON.stringify(ok()) }), env, ctx);
check(r.status === 403, 'tuj izvor zavrnjen');

fs.rmSync(dir, { recursive: true, force: true });
process.exit(fails ? 1 : 0);
