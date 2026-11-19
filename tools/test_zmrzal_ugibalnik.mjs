/*
 * tools/test_zmrzal_ugibalnik.mjs — preizkus končnih točk /zmrzal/ugibanje(a) na PRAVEM worker.js (lažen R2, KV, fetch in ura)
 * in nastavitev igre v zima/sneg-ugibalnik/ugibalnik.js (cfgFrom). Poganjanje: node tools/test_zmrzal_ugibalnik.mjs
 * Ura je lažna (razred FakeDate), zato preizkus ne zavisi od dneva: sezona se začne 1. avgusta, datum ugiba je od 1. 9. do 31. 12.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'zmrzal-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);

// lažna ura: new Date() in Date.now() vrneta NOW; ostalo je pravi Date
const RealDate = Date;
let NOW = RealDate.UTC(2027, 9, 5, 10, 0);
class FakeDate extends RealDate {
  constructor(...a) { if (a.length === 0) super(NOW); else super(...a); }
  static now() { return NOW; }
}
globalThis.Date = FakeDate;
const at = (y, m, d, h = 10) => { NOW = RealDate.UTC(y, m - 1, d, h, 0); };

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
  method, headers: { Origin: 'https://meteorec.si', 'Content-Type': 'application/json', 'CF-Connecting-IP': ip || '10.1.0.' + (++ipN) },
  body: body ? JSON.stringify(body) : undefined }), env, ctx);
let state = { sezona: 2027, prva_zmrzal: null };       // kaj vrne lažna statična datoteka data/zmrzal-ugibalnik.json
let stateFails = false;
globalThis.fetch = async () => { if (stateFails) throw new Error('omrežje'); return { ok: true, json: async () => state }; };
const G = (igralec, datum, extra = {}) => ({ igralec, datum, ...extra });

// ───────── sezona in okno ugibanja ─────────
at(2027, 7, 31);
let r = await call('/zmrzal/ugibanje', 'POST', G('igralec-aaaa1111', '2027-10-20'));
check(r.status === 409 && /mimo/.test((await r.json()).error), '31. 7. 2027: sezona 2026 je mimo (po 31. 12.), nova igra se začne 1. 8.');
at(2027, 8, 1);
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-aaaa1111', '2027-08-15'));
check(r.status === 400, '1. 8. 2027: sezona 2027 odprta, datum pred 1. 9. zavrnjen (zmrzal se šteje od 1. septembra)');
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-aaaa1111', '2027-09-01'));
check(r.status === 200, '1. 8. 2027: ugib za 1. 9. sprejet');
at(2027, 10, 5);
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-bbbb2222', '2027-10-04'));
check(r.status === 400 && /5\. 10\./.test((await r.json()).error), 'datum v preteklosti zavrnjen, sporočilo pove najzgodnejši dan');
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-bbbb2222', '2027-10-05'));
check(r.status === 200, 'današnji datum sprejet');
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-cccc3333', '2027-12-31'));
check(r.status === 200, '31. 12. sprejet');
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-dddd4444', '2028-01-01'));
check(r.status === 400, '1. 1. naslednjega leta zavrnjen');
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-dddd4444', '2027-02-30'));
check(r.status === 400, 'neveljaven koledarski datum zavrnjen');
r = await call('/zmrzal/ugibanje', 'POST', G('a b', '2027-10-20'));
check(r.status === 400, 'neveljavna oznaka igralca zavrnjena');
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-eeee5555', '2027-10-20', { website: 'x' }));
check(r.status === 200, 'honeypot: ok, a brez zapisa');
const key = 'feedback/zmrzal-ugibalnik-2027.json';
const saved = JSON.parse(store.get(key));
check(saved.length === 3 && !saved.some(i => i.id === 'igralec-eeee5555'), 'v shrambi so 3 ugibi, honeypot ni zapisan');
check(saved.every(i => i.id && i.datum && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(i.ts)), 'zapis: id, datum, čas');
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-bbbb2222', '2027-11-20'));
const dup = await r.json();
check(r.status === 409 && dup.datum === '2027-10-05', 'drugi ugib istega igralca zavrnjen, vrne prvi datum');
// seznam: brez id-jev, moj ugib
r = await call('/zmrzal/ugibanja?igralec=igralec-bbbb2222');
const list = await r.json();
check(list.n === 3 && list.sezona === 2027 && list.moj && list.moj.datum === '2027-10-05' && list.ugibi[0].length === 3
  && !JSON.stringify(list).includes('igralec-bbbb2222'), 'seznam sezone: brez id-jev, moj ugib najden');
check((await (await call('/zmrzal/ugibanja')).json()).moj === null, 'brez oznake igralca ni »mojega« ugiba');

// ───────── zaprtje po prvi zmrzali ─────────
state = { sezona: 2027, prva_zmrzal: '2027-10-14' };
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-ffff6666', '2027-11-01'));
check(r.status === 409 && /zaprto/.test((await r.json()).error), 'po prvi zmrzali je ugibanje zaprto');
state = { sezona: 2026, prva_zmrzal: '2026-10-23' };
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-ffff6666', '2027-11-01'));
check(r.status === 200, 'razrešena PREJŠNJA sezona (2026) ne zapre letošnje');
state = { sezona: 2027, prva_zmrzal: '2027-10-14' }; stateFails = true;
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-gggg7777', '2027-11-02'));
check(r.status === 200, 'vir stanja nedosegljiv: ne zapira (lestvica ugibe po zmrzali v vsakem primeru izloči)');
stateFails = false; state = { sezona: 2027, prva_zmrzal: null };

// ───────── omejitev po IP ─────────
let last;
for (let i = 0; i < 11; i++) last = await call('/zmrzal/ugibanje', 'POST', G('igralec-spam' + String(i).padStart(4, '0'), '2027-11-10'), '7.7.7.7');
check(last.status === 429, 'omejitev 10 ugibov na dan po IP');

// ───────── konec sezone ─────────
at(2028, 1, 5);
r = await call('/zmrzal/ugibanje', 'POST', G('igralec-hhhh8888', '2028-02-01'));
check(r.status === 409, '5. 1. 2028: ugibanje je mimo');
r = await call('/zmrzal/ugibanja');
check((await r.json()).sezona === 2027, 'do 1. 8. seznam še vedno kaže sezono 2027 (rezultat)');

// ───────── nastavitve igre na strani (cfgFrom v ugibalnik.js) ─────────
globalThis.Date = RealDate;
const M = createRequire(import.meta.url)(path.join(ROOT, 'zima', 'sneg-ugibalnik', 'ugibalnik.js'));
const ZATTR = { 'data-prefix': '/zmrzal', 'data-key': 'prva_zmrzal', 'data-id-key': 'wx-zmrzal-ugib-id', 'data-moj-key': 'wx-zmrzal-ugib-moj',
  'data-season-month': '8', 'data-max-md': '12-31', 'data-max-next': '0', 'data-min-md': '09-01', 'data-txt': JSON.stringify({ closed: 'zaprto zmrzal' }) };
const cfgZ = d => M.cfgFrom(n => ZATTR[n] ?? null, d);
let c = cfgZ('2027-10-05');
check(c.sezona === 2027 && c.maxDate === '2027-12-31' && c.minDate === '2027-10-05' && c.open === true && c.prefix === '/zmrzal' && c.key === 'prva_zmrzal', 'zmrzal 5. 10.: sezona 2027, do 31. 12., od danes');
check(cfgZ('2027-08-10').minDate === '2027-09-01', 'zmrzal 10. 8.: najzgodnejši datum je 1. 9.');
c = cfgZ('2028-01-05'); check(c.sezona === 2027 && c.open === false, 'zmrzal 5. 1.: še sezona 2027, ugibanje mimo');
c = cfgZ('2027-07-31'); check(c.sezona === 2026 && c.open === false, 'zmrzal 31. 7.: sezona 2026, mimo');
check(cfgZ('2027-08-01').sezona === 2027 && cfgZ('2027-08-01').open === true, 'zmrzal 1. 8.: nova sezona se odpre');
check(c.txt.closed === 'zaprto zmrzal' && c.txt.share === M.TXT.share, 'besedila: data-txt prepiše, ostalo ostane privzeto');
const cfgS = M.cfgFrom(n => ({ 'data-sezona': '2026' })[n] ?? null, '2026-11-19');
check(cfgS.prefix === '/sneg' && cfgS.key === 'prvi_sneg' && cfgS.sezona === 2026 && cfgS.maxDate === '2027-04-30' && cfgS.minDate === '2026-11-19' && cfgS.open, 'sneg: privzete nastavitve ostanejo (stran se ne spremeni)');
check(M.cfgFrom(n => ({ 'data-sezona': '2026' })[n] ?? null, '2027-05-02').open === false, 'sneg: po 30. 4. je ugibanje mimo (prej je obrazec ostal z min > max)');
check(M.cfgFrom(() => null, '2026-11-19').sezona === 2026 && M.cfgFrom(() => null, '2026-06-30').sezona === 2025, 'brez atributov: sezona sneg od julija');
check(M.cfgFrom(n => ({ 'data-txt': '{pokvarjeno' })[n] ?? null, '2026-11-19').txt.closed === M.TXT.closed, 'pokvarjen data-txt: privzeta besedila');
check(M.fill('Prvi sneg je padel {d}.', '3. decembra 2026') === 'Prvi sneg je padel 3. decembra 2026.', 'fill: vstavi datum');

// ───────── konstante: worker, razreševalnik, stran ─────────
const res = fs.readFileSync(path.join(ROOT, 'tools', 'zmrzal_ugibalnik_resolve.py'), 'utf8');
check(/SEASON_MONTH = 8\b/.test(res) && /END_MD = \(12, 31\)/.test(res), 'razreševalnik: sezona od avgusta do 31. 12.');
check(src.includes('getUTCMonth() >= 7 ? d.getUTCFullYear()'), 'worker: sezona od avgusta (mesec 7 v JS)');
const gen = path.join(ROOT, 'tools', 'generate_zmrzal_ugibalnik_page.py');
if (fs.existsSync(gen)) {
  const g = fs.readFileSync(gen, 'utf8');
  check(/data-season-month="8"/.test(g) && /data-max-md="12-31"/.test(g) && /data-min-md="09-01"/.test(g) && /data-prefix="\/zmrzal"/.test(g), 'generator strani: iste nastavitve kot worker in razreševalnik');
}
console.log(fails ? fails + ' napak' : 'zmrzal ugibalnik: OK');
process.exit(fails ? 1 : 0);
