/*
 * tools/test_g365_stat.mjs — anonimno štetje iger 365-0 v PRAVEM worker.js (lažen KV):
 *   - sprejme samo znane vrednosti (tema, način, ocena), vse ostalo je 400 in nič se ne zapiše,
 *   - ne shrani nič razen vsot (v KV ni IP ne oznake igralca),
 *   - omejitev po IP, branje samo z Bearer DELETE_SECRET (zaklep po IP),
 *   - G365_CHASES / G365_GRADES v workerju sta enaka kot v 365-0-game/src/engine (namerna podvojitev).
 * Poganjanje: node tools/test_g365_stat.mjs
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'g365-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);
const mod = await import(pathToFileURL(file).href);

const kvm = new Map();
const env = {
  DELETE_SECRET: 's3cret',
  COUNTER_KV: { get: async k => kvm.get(k) ?? null, put: async (k, v) => { kvm.set(k, v); }, delete: async k => { kvm.delete(k); } },
};
const ctx = { waitUntil() {}, passThroughOnException() {} };
let fails = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };
let ipN = 0;
const call = (p, method = 'GET', body, { ip, auth } = {}) => mod.default.fetch(new Request('https://w.test' + p, {
  method,
  headers: { Origin: 'https://meteorec.si', 'Content-Type': 'text/plain', 'CF-Connecting-IP': ip || ('7.7.7.' + (++ipN)),
    ...(auth ? { Authorization: auth } : {}) },
  body: body === undefined ? undefined : (typeof body === 'string' ? body : JSON.stringify(body)) }), env, ctx);
const stat = async () => (await (await call('/365-0/stat', 'GET', undefined, { auth: 'Bearer s3cret' })).json());

// ── sprejem ──
check((await call('/365-0/stat', 'POST', { ev: 'start', mode: 'daily', chase: 'snow' })).status === 200, 'začetek igre je sprejet');
check((await call('/365-0/stat', 'POST', { ev: 'finish', mode: 'daily', chase: 'snow', grade: 'sun-chaser', rerolls: 2 })).status === 200, 'konec igre je sprejet');
await call('/365-0/stat', 'POST', { ev: 'finish', mode: 'endless', chase: 'sun', grade: 'stormbound', rerolls: 0 });
let s = await stat();
check(s.stevci['start.daily.snow'] === 1, 'začetek je prešteto');
check(s.stevci['finish.daily.snow'] === 1 && s.stevci['grade.daily.snow.sun-chaser'] === 1, 'konec in ocena sta prešteta');
check(s.stevci['rerolls.daily.snow'] === 2 && s.stevci['rerolls.endless.sun'] === 0, 'druge priložnosti so seštete');
check(/^\d{4}-\d{2}$/.test(s.mesec), 'odgovor pove mesec');

// ── zavrnitve: nič se ne zapiše ──
const before = JSON.stringify(await stat());
const bad = [
  { ev: 'x', mode: 'daily', chase: 'sun' }, { ev: 'start', mode: 'weekly', chase: 'sun' }, { ev: 'start', mode: 'daily', chase: 'fog' },
  { ev: 'start', mode: 'daily' }, [], 'nič', 'null', '{"ev":"start"',
];
for (const b of bad) check((await call('/365-0/stat', 'POST', b)).status === 400, 'zavrne ' + JSON.stringify(b).slice(0, 50));
check(JSON.stringify(await stat()) === before, 'zavrnjeno ne spremeni vsot');
// neveljavna ocena in druge priložnosti se prezrejo, igra je vseeno prešteta
await call('/365-0/stat', 'POST', { ev: 'finish', mode: 'daily', chase: 'heat', grade: '__proto__', rerolls: 99 });
s = await stat();
check(s.stevci['finish.daily.heat'] === 1 && !Object.keys(s.stevci).some(k => k.startsWith('grade.daily.heat') || k.startsWith('rerolls.daily.heat')), 'neznana ocena in absurdne druge priložnosti se prezrejo');

// ── KV vsebuje samo vsote, nobenega IP ali oznake igralca ──
const monthKeys = [...kvm.keys()].filter(k => k.startsWith('g365:'));
check(monthKeys.length === 1 && !/\d+\.\d+\.\d+\.\d+/.test(kvm.get(monthKeys[0])), 'v shrambi so samo vsote');
check(Object.values(JSON.parse(kvm.get(monthKeys[0]))).every(v => Number.isInteger(v)), 'vse vrednosti so cela števila');

// ── omejitev po IP ──
let last = 0;
for (let i = 0; i < 125; i++) last = (await call('/365-0/stat', 'POST', { ev: 'start', mode: 'endless', chase: 'sun' }, { ip: '5.5.5.5' })).status;
check(last === 429, 'po 120 zahtevah z istega IP pride 429');

// ── branje samo za admina ──
check((await call('/365-0/stat')).status === 401, 'branje brez gesla je 401');
check((await call('/365-0/stat', 'GET', undefined, { auth: 'Bearer napacno' })).status === 401, 'branje z napačnim geslom je 401');
let st = 0;
for (let i = 0; i < 9; i++) st = (await call('/365-0/stat', 'GET', undefined, { ip: '6.6.6.6', auth: 'Bearer napacno' })).status;
check(st === 401 && (await call('/365-0/stat', 'GET', undefined, { ip: '6.6.6.6', auth: 'Bearer s3cret' })).status === 401, 'po 8 napakah je IP zaklenjen tudi z pravim geslom');

// ── namerna podvojitev z igro ──
const wsrc = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
const list = name => JSON.parse(wsrc.match(new RegExp('const ' + name + ' = (\\[[^\\]]*\\])'))[1]);
const chaseSrc = fs.readFileSync(path.join(ROOT, '365-0-game/src/engine/chase.ts'), 'utf8');
const gradeSrc = fs.readFileSync(path.join(ROOT, '365-0-game/src/engine/grades.ts'), 'utf8');
const quoted = (text, re) => [...text.match(re)[1].matchAll(/'([^']+)'/g)].map(m => m[1]);
const sameSet = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());
check(sameSet(list('G365_CHASES'), quoted(chaseSrc, /CHASE_IDS\s*=\s*\[([^\]]*)\]/)), 'G365_CHASES = CHASE_IDS v igri');
check(sameSet(list('G365_GRADES'), quoted(gradeSrc, /GRADE_IDS\s*=\s*\[([^\]]*)\]/)), 'G365_GRADES = GRADE_IDS v igri');

if (fails) { console.error('\n' + fails + ' napak'); process.exit(1); }
console.log('\nvse v redu');
