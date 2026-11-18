/*
 * tools/test_tedenski.mjs — preizkus končnih točk /tedenski/* (»Dolina v tednu«) na PRAVEM worker.js
 * (lažen R2, KV, Resend prek fetch). Poganjanje: node tools/test_tedenski.mjs
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tedenski-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);
const mod = await import(pathToFileURL(file).href);

const store = new Map(), kvm = new Map(), mails = [], pend = [];
const env = {
  RESEND_API_KEY: 'k', SUBSCRIBE_SECRET: 's3cret',
  PHOTOS_R2: { get: async k => store.has(k) ? { text: async () => store.get(k) } : null, put: async (k, v) => { store.set(k, v); } },
  COUNTER_KV: { get: async k => kvm.get(k) ?? null, put: async (k, v) => { kvm.set(k, v); }, delete: async k => { kvm.delete(k); } },
};
const ctx = { waitUntil: p => pend.push(p), passThroughOnException() {} };
globalThis.fetch = async (url, opts) => { mails.push({ url: String(url), ...JSON.parse(opts.body), hdr: opts.headers }); return { ok: true }; };
let fails = 0, ipN = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };
const call = async (p, method = 'GET', body, ip) => {
  const r = await mod.default.fetch(new Request('https://w.test' + p, { method,
    headers: { Origin: 'https://meteorec.si', 'Content-Type': 'application/json', 'CF-Connecting-IP': ip || '10.1.0.' + (++ipN) },
    body: body ? JSON.stringify(body) : undefined }), env, ctx);
  await Promise.all(pend.splice(0));
  return r;
};
const HTML = '<p>Povzetek</p><a href="{{ODJAVA}}">Odjava</a>';
const pending = () => JSON.parse(store.get('subscribers/tedenski-pending.json') || '[]');
const confirmed = () => JSON.parse(store.get('subscribers/tedenski-confirmed.json') || '[]');

// ───────── prijava ─────────
let r = await call('/tedenski/prijava', 'POST', { email: ' Ana@Example.si ' });
check(r.status === 200 && pending().length === 1 && pending()[0].email === 'ana@example.si', 'prijava: e-naslov normaliziran, čaka na potrditev');
check(mails.length === 1 && mails[0].to === 'ana@example.si' && /tedenski\/potrdi\?token=[0-9a-f]{32}/.test(mails[0].html), 'prijava: potrditvena e-pošta z žetonom');
check(!JSON.stringify(await (await call('/tedenski/prijava', 'POST', { email: 'ana@example.si' })).json()).includes(pending()[0].token), 'prijava: odgovor ne razkrije žetona');
check(pending().length === 1, 'prijava: isti e-naslov ne podvoji zapisa');
r = await call('/tedenski/prijava', 'POST', { email: 'ni-naslov' });
check(r.status === 400, 'prijava: neveljaven e-naslov 400');
const n0 = pending().length;
r = await call('/tedenski/prijava', 'POST', { email: 'bot@example.si', website: 'x' });
check(r.status === 200 && pending().length === n0, 'prijava: honeypot brez zapisa');
for (let i = 0; i < 6; i++) r = await call('/tedenski/prijava', 'POST', { email: `x${i}@example.si` }, '7.7.7.7');
check(r.status === 429, 'prijava: omejitev 5/uro po IP');

// ───────── potrditev ─────────
const tok = pending().find(s => s.email === 'ana@example.si').token;
r = await call('/tedenski/potrdi?token=' + tok);
check(r.status === 200 && confirmed().length === 1 && !pending().some(s => s.token === tok), 'potrdi: prestavi med potrjene');
r = await call('/tedenski/potrdi?token=' + tok);
check(r.status === 200 && /že aktivna/.test(await r.text()), 'potrdi: drugič »že potrjeno«');
check((await call('/tedenski/potrdi?token=napacen')).status === 404 && (await call('/tedenski/potrdi')).status === 400, 'potrdi: neznan žeton 404, brez žetona 400');
await call('/tedenski/prijava', 'POST', { email: 'bor@example.si' });
await call('/tedenski/potrdi?token=' + pending().find(s => s.email === 'bor@example.si').token);
check(confirmed().length === 2, 'potrdi: drugi naročnik');
check(!('ip' in confirmed()[0]) && Object.keys(confirmed()[0]).sort().join() === 'email,token,ts', 'zapis naročnika: samo e-naslov, žeton in čas');

// ───────── pošiljanje ─────────
const before = mails.length;
check((await call('/tedenski/poslji', 'POST', { week: '2026-11-09', subject: 'Z', html: HTML })).status === 401, 'poslji: brez gesla 401');
check((await call('/tedenski/poslji', 'POST', { secret: 'napacno', week: '2026-11-09', subject: 'Z', html: HTML })).status === 401, 'poslji: napačno geslo 401');
for (const bad of [{ week: 'x' }, { subject: '' }, { html: '<p>brez odjave</p>' }, { html: 'a'.repeat(100001) + '{{ODJAVA}}' }, { subject: 'a'.repeat(151) }]) {
  r = await call('/tedenski/poslji', 'POST', { secret: 's3cret', week: '2026-11-09', subject: 'Zadeva', html: HTML, ...bad });
  check(r.status === 400, 'poslji: neveljavna vsebina zavrnjena ' + Object.keys(bad)[0]);
}
check(mails.length === before, 'poslji: zavrnjene zahteve ne pošljejo ničesar');
r = await call('/tedenski/poslji', 'POST', { secret: 's3cret', week: '2026-11-09', subject: 'Dolina v tednu', html: HTML });
let j = await r.json();
const sent = mails.slice(before);
check(r.status === 200 && j.sent === 2 && sent.length === 2, 'poslji: obe potrjeni naslovnici prejmeta e-pošto');
check(sent.every(m => !m.html.includes('{{ODJAVA}}') && /tedenski\/odjava\?token=[0-9a-f]{32}/.test(m.html)), 'poslji: {{ODJAVA}} nadomeščen z osebno povezavo');
check(sent.every(m => m.headers && /^<https:\/\/w\.test\/tedenski\/odjava\?token=/.test(m.headers['List-Unsubscribe'])), 'poslji: glava List-Unsubscribe');
check(sent[0].html.includes(confirmed()[0].token) !== sent[1].html.includes(confirmed()[0].token), 'poslji: vsak naslovnik dobi svojo povezavo');
r = await call('/tedenski/poslji', 'POST', { secret: 's3cret', week: '2026-11-09', subject: 'Dolina v tednu', html: HTML });
j = await r.json();
check(j.sent === 0 && j.already === true && mails.length === before + 2, 'poslji: isti teden drugič ne pošlje (že poslano)');
r = await call('/tedenski/poslji', 'POST', { secret: 's3cret', week: '2026-11-09', subject: 'Dolina v tednu', html: HTML, force: true });
check((await r.json()).sent === 2, 'poslji: force ponovno pošlje');
r = await call('/tedenski/poslji', 'POST', { secret: 's3cret', week: '2026-11-16', subject: 'Dolina v tednu', html: HTML });
check((await r.json()).sent === 2, 'poslji: drug teden normalno');

// ───────── odjava ─────────
const ana = confirmed().find(s => s.email === 'ana@example.si');
r = await call('/tedenski/odjava?token=' + ana.token);
check(r.status === 200 && confirmed().length === 1 && !confirmed().some(s => s.email === 'ana@example.si'), 'odjava: odstrani naročnika');
await call('/tedenski/odjava');
check(confirmed().length === 1, 'odjava: brez žetona ne odstrani nikogar');
r = await call('/tedenski/poslji', 'POST', { secret: 's3cret', week: '2026-11-23', subject: 'Dolina v tednu', html: HTML });
check((await r.json()).sent === 1, 'poslji: odjavljeni ne prejme več');
check((await call('/tedenski/neznano', 'GET')).status === 405, 'neznana pot 405');
fs.rmSync(dir, { recursive: true, force: true });
process.exit(fails ? 1 : 0);
