/*
 * tools/test_worker_auth.mjs — avtorizacija končnih točk v PRAVEM worker.js (lažen KV/R2):
 *   /premium/data (sync ključ), /premium/webhook (Paddle HMAC), /premium/verify + /forecast (žeton, potek),
 *   /premium/subscribers, /gallery/pending, /nevihte/porocila/cakajoca + moderacija (admin, zaklep po IP),
 *   /push/send, /blog-subscribe/notify, /gobe/alarm-notify (skrivnosti).
 * Brez tega bi tiha sprememba (npr. odstranjen preizkus podpisa) pomenila brezplačen premium ali javno moderacijo.
 * Poganjanje: node tools/test_worker_auth.mjs
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auth-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);
globalThis.fetch = async () => new Response('{}', { status: 200 });   // pošiljanje e-pošte ipd. ne sme v omrežje
const mod = await import(pathToFileURL(file).href);

const kvm = new Map(), meta = new Map(), r2m = new Map();
const kv = {
  get: async (k, o) => { const v = kvm.get(k); if (v == null) return null; const t = typeof o === 'string' ? o : o && o.type;
    return t === 'json' ? JSON.parse(typeof v === 'string' ? v : new TextDecoder().decode(v)) : v; },
  getWithMetadata: async (k) => ({ value: kvm.get(k) ?? null, metadata: meta.get(k) ?? null }),
  put: async (k, v, o) => { kvm.set(k, v); if (o && o.metadata) meta.set(k, o.metadata); },
  delete: async (k) => { kvm.delete(k); },
  list: async ({ prefix = '' } = {}) => ({ keys: [...kvm.keys()].filter(k => k.startsWith(prefix)).map(name => ({ name })), list_complete: true }),
};
const r2 = {
  get: async k => r2m.has(k) ? { text: async () => r2m.get(k) } : null,
  put: async (k, v) => { r2m.set(k, v); },
  list: async () => ({ objects: [], truncated: false }),
  delete: async k => { r2m.delete(k); },
};
const env = { COUNTER_KV: kv, PHOTOS_R2: r2, DELETE_SECRET: 'adm1n-secret', PREMIUM_SYNC_KEY: 'sync-key-123',
  PADDLE_WEBHOOK_SECRET: 'whsec_test', SUBSCRIBE_SECRET: 'sub-secret', VAPID_PRIVATE: 'x' };
const ctx = { waitUntil() {}, passThroughOnException() {} };
let fails = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };
let ipN = 0;
const call = (p, method = 'GET', body, headers = {}, e = env, ip) => mod.default.fetch(new Request('https://w.test' + p, {
  method, headers: { Origin: 'https://meteorec.si', 'CF-Connecting-IP': ip || ('7.7.7.' + (++ipN)), ...headers },
  body: body === undefined ? undefined : (typeof body === 'string' || body instanceof Uint8Array ? body : JSON.stringify(body)) }), e, ctx);

// ── /premium/data ──
const goodPayload = JSON.stringify({ generated: '2026-10-29T08:00', locations_count: 3, locations: [] });
let r = await call('/premium/data', 'POST', goodPayload);
check(r.status === 401, 'premium/data brez ključa: 401');
r = await call('/premium/data', 'POST', goodPayload, { Authorization: 'Bearer napacen' });
check(r.status === 401, 'premium/data napačen ključ: 401');
r = await call('/premium/data', 'POST', goodPayload, { Authorization: 'Bearer sync-key-123' }, { ...env, PREMIUM_SYNC_KEY: undefined });
check(r.status === 401, 'premium/data brez nastavljenega ključa na strežniku: 401 (ne odprto)');
r = await call('/premium/data', 'POST', JSON.stringify({ locations_count: 0 }), { Authorization: 'Bearer sync-key-123' });
check(r.status === 422, 'premium/data brez lokacij: 422');
r = await call('/premium/data', 'POST', 'ni gzip', { Authorization: 'Bearer sync-key-123', 'X-Premium-Gzip': '1' });
check(r.status === 400, 'premium/data neveljaven gzip: 400');
r = await call('/premium/data', 'POST', goodPayload, { Authorization: 'Bearer sync-key-123' });
check(r.status === 200 && kvm.has('premium:data') && meta.get('premium:data').generated === '2026-10-29T08:00', 'premium/data pravilen vnos: 200 in zapis v KV');
r = await call('/premium/data?kind=today', 'POST', JSON.stringify({ locations: 5 }), { Authorization: 'Bearer sync-key-123' });
check(r.status === 422, 'premium/data kind=today z neveljavnimi lokacijami: 422');

// ── /premium/webhook ──
const sign = (raw, secret = 'whsec_test', ts = String(Math.floor(Date.now() / 1000))) =>
  ({ 'Paddle-Signature': `ts=${ts};h1=${crypto.createHmac('sha256', secret).update(`${ts}:${raw}`).digest('hex')}` });
const evt = JSON.stringify({ event_type: 'transaction.completed', data: { custom_data: { email: 'Kupec@Example.si' }, customer_id: 'ctm_1', items: [] } });
r = await call('/premium/webhook', 'POST', evt, sign(evt), { ...env, PADDLE_WEBHOOK_SECRET: undefined });
check(r.status === 503, 'webhook brez nastavljene skrivnosti: 503 (ne sprejme)');
r = await call('/premium/webhook', 'POST', evt);
check(r.status === 401, 'webhook brez podpisa: 401');
r = await call('/premium/webhook', 'POST', evt, sign(evt, 'druga_skrivnost'));
check(r.status === 401 && !kvm.has('premium:sub:kupec@example.si'), 'webhook s tujim podpisom: 401 in brez naročnine');
r = await call('/premium/webhook', 'POST', evt, sign(evt + ' '));
check(r.status === 401, 'webhook s podpisom drugega telesa: 401');
const other = JSON.stringify({ event_type: 'subscription.created', data: {} });
r = await call('/premium/webhook', 'POST', other, sign(other));
check(r.status === 200 && (await r.json()).ignored === 'subscription.created', 'webhook: drug dogodek je prezrt');
r = await call('/premium/webhook', 'POST', '{ni json', sign('{ni json'));
check(r.status === 400, 'webhook: veljaven podpis, neveljaven JSON: 400');
r = await call('/premium/webhook', 'POST', evt, sign(evt));
const sub = JSON.parse(kvm.get('premium:sub:kupec@example.si') || 'null');
check(r.status === 200 && sub && sub.email === 'kupec@example.si' && new Date(sub.expires) > new Date(), 'webhook: pravilen podpis ustvari naročnino (e-naslov z malimi črkami, rok v prihodnosti)');

// ── žeton: /premium/verify, /premium/forecast ──
r = await call('/premium/verify');
check(r.status === 401, 'premium/verify brez žetona: 401');
r = await call('/premium/forecast');
check(r.status === 401, 'premium/forecast brez žetona: 401');
r = await call('/premium/forecast', 'GET', undefined, { Authorization: 'Bearer izmisljen' });
check(r.status === 401, 'premium/forecast z izmišljenim žetonom: 401');
kvm.set('premium:tok:aaa', JSON.stringify({ email: 'kupec@example.si' }));
r = await call('/premium/verify', 'GET', undefined, { Authorization: 'Bearer aaa' });
check(r.status === 200 && (await r.json()).ok === true, 'premium/verify z veljavnim žetonom in naročnino: 200');
kvm.set('premium:sub:kupec@example.si', JSON.stringify({ email: 'kupec@example.si', plan: 'mesecna', expires: '2020-01-01T00:00:00Z' }));
r = await call('/premium/verify', 'GET', undefined, { Authorization: 'Bearer aaa' });
check(r.status === 401, 'premium/verify s potekla naročnino: 401');
r = await call('/premium/forecast', 'GET', undefined, { Authorization: 'Bearer aaa' });
check(r.status === 401, 'premium/forecast s potekla naročnino: 401');

// ── admin: zaklep po IP ──
r = await call('/premium/subscribers');
check(r.status === 401, 'premium/subscribers brez skrivnosti: 401');
r = await call('/premium/subscribers', 'GET', undefined, { Authorization: 'Bearer adm1n-secret' });
check(r.status === 200, 'premium/subscribers z admin skrivnostjo: 200');
r = await call('/gallery/pending');
check(r.status === 401, 'gallery/pending brez skrivnosti: 401');
r = await call('/gallery/pending', 'GET', undefined, { Authorization: 'Bearer adm1n-secret' });
check(r.status === 200, 'gallery/pending z admin skrivnostjo: 200');
r = await call('/nevihte/porocila/cakajoca');
check(r.status === 401, 'nevihte/cakajoca brez skrivnosti: 401');
r = await call('/nevihte/porocila/moderacija', 'POST', { id: 'x', odlocitev: 'odobri' });
check(r.status === 401, 'nevihte/moderacija brez skrivnosti: 401');
r = await call('/nevihte/porocila/moderacija', 'POST', { id: 'x', odlocitev: 'odobri' }, { Authorization: 'Bearer adm1n-secret' });
check(r.status === 404, 'nevihte/moderacija z admin skrivnostjo: pot odprta (poročila ni: 404)');
const atk = '66.66.66.66';
for (let i = 0; i < 8; i++) await call('/premium/subscribers', 'GET', undefined, { Authorization: 'Bearer napacno' + i }, env, atk);
r = await call('/premium/subscribers', 'GET', undefined, { Authorization: 'Bearer adm1n-secret' }, env, atk);
check(r.status === 429, 'po 8 napačnih poskusih je IP zaklenjen tudi z pravilno skrivnostjo (429)');
r = await call('/premium/subscribers', 'GET', undefined, { Authorization: 'Bearer adm1n-secret' }, env, '5.5.5.5');
check(r.status === 200, 'zaklep velja samo za napadalčev IP');

// ── skrivnosti v telesu / glavi ──
r = await call('/push/send', 'POST', { secret: 'napacno', title: 'x' });
check(r.status === 401, 'push/send s napačno skrivnostjo: 401');
r = await call('/push/send', 'POST', { title: 'x' });
check(r.status === 401, 'push/send brez skrivnosti: 401');
r = await call('/blog-subscribe/notify', 'POST', { secret: 'napacno' });
check(r.status === 401, 'blog-subscribe/notify s napačno skrivnostjo: 401');
r = await call('/gobe/alarm-notify', 'POST', undefined, { Authorization: 'Bearer napacno' });
check(r.status === 401, 'gobe/alarm-notify napačen ključ: 401');
r = await call('/gobe/alarm-notify', 'POST', undefined, {}, { ...env, PREMIUM_SYNC_KEY: undefined });
check(r.status === 401, 'gobe/alarm-notify brez nastavljenega ključa: 401');

fs.rmSync(dir, { recursive: true, force: true });
process.exit(fails ? 1 : 0);
