/*
 * tools/test_anketa.mjs — preizkus POST /anketa in GET /anketa/rezultati na PRAVEM worker.js
 * (lažen R2 in KV). Poganjanje: node tools/test_anketa.mjs
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'anketa-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);
const mod = await import(pathToFileURL(file).href);

const store = new Map(), kvm = new Map();
const env = {
  DELETE_SECRET: 's3cret',
  PHOTOS_R2: { get: async k => store.has(k) ? { text: async () => store.get(k) } : null, put: async (k, v) => { store.set(k, v); } },
  COUNTER_KV: { get: async k => kvm.get(k) ?? null, put: async (k, v) => { kvm.set(k, v); }, delete: async k => { kvm.delete(k); } },
};
const ctx = { waitUntil() {}, passThroughOnException() {} };
let fails = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };
const call = (p, method = 'GET', body, headers = {}) => mod.default.fetch(new Request('https://w.test' + p, {
  method, headers: { Origin: 'https://meteorec.si', 'Content-Type': 'application/json', 'CF-Connecting-IP': '1.2.3.4', ...headers },
  body: body ? JSON.stringify(body) : undefined }), env, ctx);

let r = await call('/anketa', 'POST', { q1: 'gobe', q3: 'google', q4: '  več krajev ' });
check(r.status === 200, 'veljaven vnos sprejet');
const saved = JSON.parse(store.get('feedback/anketa.json'));
check(saved.length === 1 && saved[0].q1 === 'gobe' && saved[0].q4 === 'več krajev' && !('ip' in saved[0]), 'shranjeno brez IP, besedilo obrezano');
r = await call('/anketa', 'POST', { q5: 'iphone' });
check(JSON.parse(store.get('feedback/anketa.json'))[0].q5 === 'iphone', 'q5 shranjena');
r = await call('/anketa', 'POST', { q1: 'napaka', q5: 'windows' });
check(r.status === 400, 'neveljavna vrednost in prazen odgovor zavrnjena');
r = await call('/anketa', 'POST', { q1: 'gobe', website: 'x' });
check(r.status === 200 && JSON.parse(store.get('feedback/anketa.json')).length === 2, 'honeypot: ok, a brez zapisa');
r = await call('/anketa', 'POST', { q1: 'gobe', q3: 'google', q4: 'več krajev' });
check(JSON.parse(store.get('feedback/anketa.json')).length === 2, 'dvojni klik ne podvoji');
for (let i = 0; i < 6; i++) r = await call('/anketa', 'POST', { q2: 'radar', q4: 'a' + i });
check(r.status === 429, 'omejitev po IP (429)');
r = await call('/anketa/rezultati');
check(r.status === 401, 'GET brez žetona 401');
r = await call('/anketa/rezultati', 'GET', undefined, { Authorization: 'Bearer s3cret' });
check(r.status === 200 && (await r.json()).odgovori.length >= 1, 'GET z žetonom vrne odgovore');
fs.rmSync(dir, { recursive: true, force: true });
process.exit(fails ? 1 : 0);
