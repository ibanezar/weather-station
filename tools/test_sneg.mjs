/*
 * tools/test_sneg.mjs — preizkus končnih točk /sneg/porocilo(a) in /sneg/ugibanje(a) na PRAVEM worker.js
 * (lažen R2, KV in fetch). Poganjanje: node tools/test_sneg.mjs
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sneg-'));
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
  method, headers: { Origin: 'https://meteorec.si', 'Content-Type': 'application/json', 'CF-Connecting-IP': ip || '10.0.0.' + (++ipN) },
  body: body ? JSON.stringify(body) : undefined }), env, ctx);
let resolved = null;                         // datum prvega snega, ki ga vrne lažna statična datoteka
const sezonaNow = () => { const d = new Date(); return d.getUTCMonth() >= 6 ? d.getUTCFullYear() : d.getUTCFullYear() - 1; };
globalThis.fetch = async () => ({ ok: true, json: async () => ({ sezona: sezonaNow(), prvi_sneg: resolved }) });

// ───────── poročila ─────────
const P = { stanje: 'lezi', pas: 'p1', regija: 'Savinjska' };
let r = await call('/sneg/porocilo', 'POST', P, '1.1.1.1');
check(r.status === 200, 'veljavno poročilo sprejeto');
const saved = JSON.parse(store.get('feedback/sneg-porocila.json'));
check(saved.length === 1 && Object.keys(saved[0]).sort().join() === 'pas,regija,stanje,ts', 'zapis brez IP, id-ja in prostega besedila');
check(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00Z$/.test(saved[0].ts), 'čas zaokrožen na minuto');
r = await call('/sneg/porocilo', 'POST', P, '1.1.1.1');
check(r.status === 429, 'ista celica z iste naprave v 2 urah zavrnjena');
r = await call('/sneg/porocilo', 'POST', { ...P, pas: 'p2' }, '1.1.1.1');
check(r.status === 200, 'druga celica z iste naprave sprejeta');
for (const bad of [{ ...P, stanje: 'toca' }, { ...P, pas: 'p9' }, { ...P, regija: 'Mars' }, {}]) {
  r = await call('/sneg/porocilo', 'POST', bad);
  check(r.status === 400, 'neveljavna vrednost zavrnjena: ' + JSON.stringify(bad));
}
const n0 = JSON.parse(store.get('feedback/sneg-porocila.json')).length;
r = await call('/sneg/porocilo', 'POST', { ...P, website: 'x' });
check(r.status === 200 && JSON.parse(store.get('feedback/sneg-porocila.json')).length === n0, 'honeypot: ok, a brez zapisa');

// splošna omejitev: 30 poročil na uro z iste naprave (v različna območja), 31. zavrnjeno
{
  const REG = ['Savinjska', 'Koroška', 'Gorenjska', 'Osrednjeslovenska', 'Zasavska', 'Posavska', 'Jugovzhodna Slovenija', 'Primorsko-notranjska'];
  let last;
  for (let i = 0; i < 31; i++) last = await call('/sneg/porocilo', 'POST', { stanje: 'brez', pas: 'p' + (i % 4), regija: REG[Math.floor(i / 4)] }, '9.9.9.9');
  check(last.status === 429, 'omejitev 30 poročil na uro po IP');
}

// sodba šele od 3 poročil in 60 % soglasja
const cellOf = (d, regija, pas) => d.celice.find(c => c.regija === regija && c.pas === pas);
for (const [reg, stanja] of [['Koroška', ['lezi', 'lezi', 'brez']], ['Gorenjska', ['lezi', 'brez', 'lezi', 'brez']], ['Podravska', ['pada', 'pada']]]) {
  for (const s of stanja) await call('/sneg/porocilo', 'POST', { stanje: s, pas: 'p0', regija: reg });
}
r = await call('/sneg/porocila?ur=24');
let d = await r.json();
check(cellOf(d, 'Koroška', 'p0').sodba === 'lezi' && cellOf(d, 'Koroška', 'p0').n === 3, '2 od 3 (67 %) → sodba »leži«');
check(cellOf(d, 'Gorenjska', 'p0').sodba === null, '2 : 2 → brez sodbe');
check(cellOf(d, 'Podravska', 'p0').sodba === null && cellOf(d, 'Podravska', 'p0').n === 2, 'manj kot 3 poročila → brez sodbe');
check(!JSON.stringify(d).includes('1.1.1.1'), 'odgovor ne vsebuje IP');
// starejše od okna se ne štejejo
const arr = JSON.parse(store.get('feedback/sneg-porocila.json'));
arr.push({ ts: new Date(Date.now() - 30 * 3600000).toISOString(), regija: 'Pomurska', pas: 'p0', stanje: 'lezi' });
store.set('feedback/sneg-porocila.json', JSON.stringify(arr));
d = await (await call('/sneg/porocila?ur=24')).json();
check(!cellOf(d, 'Pomurska', 'p0'), 'poročilo starejše od 24 h izločeno');
d = await (await call('/sneg/porocila?ur=72')).json();
check(!!cellOf(d, 'Pomurska', 'p0'), 'v oknu 72 h je poročilo vključeno');

// ───────── ugibalnik ─────────
const m = new Date().getUTCMonth();
if (m === 4 || m === 5) {
  console.log('(izven sezone: preizkusi ugibanja preskočeni)');
} else {
  const day = (add) => { const x = new Date(Date.now() + add * 86400000); return x.toLocaleDateString('sv-SE', { timeZone: 'Europe/Ljubljana' }); };
  const apr30 = (sezonaNow() + 1) + '-04-30';
  const target = day(10) <= apr30 ? day(10) : apr30;
  const G = { igralec: 'igralec-aaaa1111', datum: target, ime: ' Ana <b>' };
  r = await call('/sneg/ugibanje', 'POST', G, '2.2.2.2');
  check(r.status === 200, 'veljavno ugibanje sprejeto');
  r = await call('/sneg/ugibanje', 'POST', { ...G, datum: day(11) > apr30 ? apr30 : day(11) }, '2.2.2.3');
  check(r.status === 409 && (await r.json()).datum === target, 'drugič z istim igralcem: 409 in prvotni datum');
  r = await call('/sneg/ugibanje', 'POST', { igralec: 'igralec-bbbb2222', datum: day(-1) });
  check(r.status === 400, 'datum v preteklosti zavrnjen');
  r = await call('/sneg/ugibanje', 'POST', { igralec: 'igralec-bbbb2222', datum: (sezonaNow() + 1) + '-05-01' });
  check(r.status === 400, 'datum po 30. aprilu zavrnjen');
  r = await call('/sneg/ugibanje', 'POST', { igralec: 'igralec-bbbb2222', datum: '2026-02-30' });
  check(r.status === 400, 'neobstoječ datum zavrnjen');
  r = await call('/sneg/ugibanje', 'POST', { igralec: 'a b', datum: target });
  check(r.status === 400, 'neveljaven id zavrnjen');
  r = await call('/sneg/ugibanje', 'POST', { igralec: 'igralec-cccc3333', datum: target, website: 'x' });
  check(r.status === 200, 'honeypot: ok');
  const key = 'feedback/sneg-ugibalnik-' + sezonaNow() + '.json';
  const st = JSON.parse(store.get(key));
  check(st.length === 1 && st[0].ime === 'Ana b' && !('ip' in st[0]), 'honeypot brez zapisa, ime očiščeno znakov < >');
  r = await call('/sneg/ugibanja?igralec=igralec-aaaa1111');
  d = await r.json();
  check(d.n === 1 && d.moj && d.moj.datum === target && d.ugibi[0].length === 3 && !JSON.stringify(d.ugibi).includes('igralec-aaaa1111'), 'seznam brez id-jev, »moj« vrne lastno ugibanje');
  resolved = day(0);
  r = await call('/sneg/ugibanje', 'POST', { igralec: 'igralec-dddd4444', datum: target });
  check(r.status === 409, 'po prvem snegu je ugibanje zaprto');
  resolved = null;
  for (let i = 0; i < 11; i++) r = await call('/sneg/ugibanje', 'POST', { igralec: 'igralec-spam' + String(i).padStart(4, '0'), datum: target }, '3.3.3.3');
  check(r.status === 429, 'omejitev po IP (10 na dan)');
}
// ───────── model ugibalnika (zima/sneg-ugibalnik/ugibalnik.js, brez DOM-a) ─────────
const { createRequire } = await import('node:module');
const M = createRequire(import.meta.url)(path.join(ROOT, 'zima', 'sneg-ugibalnik', 'ugibalnik.js'));
check(M.dayDiff('2026-12-01', '2026-12-04') === 3 && M.dayDiff('2026-12-04', '2026-12-01') === -3, 'dayDiff: razlika v dneh s predznakom');
check(M.dayDiff('2026-12-31', '2027-01-02') === 2, 'dayDiff: prehod leta');
check(M.ljDate('2026-12-02T23:30:00Z') === '2026-12-03', 'ljDate: 23.30 UTC je že naslednji dan po lokalni uri');
const ug = [['2026-12-02', 'Ana', '2026-11-20T10:00:00Z'], ['2026-12-05', 'Boris', '2026-11-21T10:00:00Z'],
  ['2026-11-30', '', '2026-11-22T10:00:00Z'], ['2026-12-04', 'Cene', '2026-11-19T10:00:00Z'], ['2026-12-03', 'Prepozen', '2026-12-03T09:00:00Z']];
let rk = M.ranking(ug, '2026-12-03');
check(rk.length === 4 && !rk.some(g => g.ime === 'Prepozen'), 'ranking: ugib, oddan na dan snega, se ne šteje');
check(rk[0].razlika === 1 && rk[0].ime === 'Cene' && rk[1].ime === 'Ana', 'ranking: najmanjša razlika, pri izenačenju prej oddan (Cene pred Ano)');
check(rk.map(g => g.razlika).join() === '1,1,2,3' && rk[0].pred === 1 && rk[3].pred === -3, 'ranking: razlike in predznak (pred/po)');
check(M.ranking(ug, null).length === 0, 'ranking: brez razrešitve ni lestvice');
check(M.validGuesses(ug, null).length === 5, 'validGuesses: brez razrešitve šteje vse');
check(M.median(['2026-12-01', '2026-12-05', '2026-12-03']) === '2026-12-03' && M.median(['2026-12-01', '2026-12-04']) === '2026-12-03' && M.median([]) === null, 'median: liho, sodo (okrogljeno), prazno');
check(M.mondayOf('2026-11-22') === '2026-11-16' && M.mondayOf('2026-11-23') === '2026-11-23', 'mondayOf: nedelja → prejšnji ponedeljek');
const wb = M.weekBins(['2026-11-17', '2026-11-18', '2026-12-08']);
check(wb.length === 4 && wb[0].n === 2 && wb[1].n === 0 && wb[2].n === 0 && wb[3].n === 1, 'weekBins: tedni brez lukenj');
check(M.dnevi(1) === '1 dan' && M.dnevi(2) === '2 dneva' && M.dnevi(3) === '3 dni' && M.dnevi(11) === '11 dni', 'dnevi: slovnica');
check(M.fmt('2026-12-03') === '3. 12.' && M.fmtLong('2026-12-03') === '3. decembra 2026', 'fmt/fmtLong');

fs.rmSync(dir, { recursive: true, force: true });
process.exit(fails ? 1 : 0);
