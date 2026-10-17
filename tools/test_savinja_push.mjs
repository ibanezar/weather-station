/*
 * tools/test_savinja_push.mjs — preizkus opozorila ob pragu Savinje iz worker.js.
 * Izreže razčlenjevalnik ARSO XML in blok »Savinja čez prag« in ju požene (prava koda).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
const pa = src.indexOf('// ── ARSO hidrološke postaje: razčlenitev');
const pb = src.indexOf('// ── Savinja čez prag visokih voda');
const sb = src.indexOf('// ── Začetek/konec dejanskih padavin');
assert(pa > 0 && pb > pa && sb > pb, 'bloka nista najdena');

const store = {};
const r2 = { get: async k => (k in store ? { text: async () => store[k] } : null), put: async (k, v) => { store[k] = v; } };
const pushed = [];
let xml = '', fetchOk = true;
const ctx = vm.createContext({
  console, JSON, Math, Date, Promise, Number, Array, String, Object, RegExp, parseInt,
  _pushAll: async (_e, payload, filter) => { pushed.push({ payload, n: JSON.parse(store['push/subs.json']).filter(filter).length }); return {}; },
  fetch: async () => ({ ok: fetchOk, status: fetchOk ? 200 : 503, text: async () => xml }),
});
vm.runInContext(src.slice(pa, sb) + '\nthis._parse=_parseArsoHidroXml; this._trans=_savinjaTransitions; this._cron=_cronCheckSavinja;', ctx);
const { _parse, _trans, _cron } = ctx;

const post = (sifra, ime, q, cet = '2026-10-17 17:00', vv = [310, 420, 530]) =>
  `<postaja  sifra="${sifra}"  wgs84_dolzina="14.95"  wgs84_sirina="46.32" ><reka>Savinja</reka><merilno_mesto>${ime}</merilno_mesto><ime_kratko>Savinja - ${ime}</ime_kratko>`
  + `<datum>${cet.replace(/ (\d\d)/, (_, h) => ' ' + String(+h + 1).padStart(2, '0'))}</datum><datum_cet>${cet}</datum_cet><vodostaj>36</vodostaj><pretok>${q}</pretok>`
  + (vv ? `<prvi_vv_pretok>${vv[0]}</prvi_vv_pretok><drugi_vv_pretok>${vv[1]}</drugi_vv_pretok><tretji_vv_pretok>${vv[2]}</tretji_vv_pretok>` : '<prvi_vv_vodostaj>385</prvi_vv_vodostaj>')
  + `<pretok_znacilni>mali pretok</pretok_znacilni><temp_vode>12.9</temp_vode></postaja>`;

// 1. razčlenjevalnik (šumniki, pragovi, postaja brez pragov pretoka)
const f = _parse('<xml>' + post('6060', 'Nazarje', 3.4) + post('6120', 'Medlog', 0, undefined, null) + '</xml>');
assert.equal(f.length, 2);
assert.equal(f[0].properties.vv1, 310); assert.equal(f[0].properties.vv3, 530); assert.equal(f[0].properties.datum_cet, '2026-10-17 17:00');
assert.equal(f[1].properties.vv1, null);
assert.equal(_parse('<postaja sifra="1" wgs84_dolzina="14.7" wgs84_sirina="46.4"><merilno_mesto>Sol&#x010D;ava I</merilno_mesto></postaja>')[0].properties.merilno_mesto, 'Solčava I');

// 2. prehodi: čas datum_cet je CET (+01:00) → 17:00 CET = 16:00 UTC
const now = Date.parse('2026-10-17T16:20:00Z');
const st = (q, extra) => _parse('<xml>' + post('6060', 'Nazarje', q, ...(extra || [])) + '</xml>');
let r = _trans(st(200), {}, now); assert.equal(r.events.length, 0); assert.equal(r.fresh, 1);
r = _trans(st(312), r.next, now); assert.equal(r.events.length, 1); assert.equal(r.events[0].lvl, 1); assert.equal(r.events[0].thr, 310); assert.equal(r.events[0].cas, '18:00');
r = _trans(st(315), r.next, now); assert.equal(r.events.length, 0, 'ista stopnja ne ponovi obvestila');
r = _trans(st(440), r.next, now); assert.equal(r.events[0].lvl, 2, 'višja stopnja takoj');
r = _trans(st(400), r.next, now); assert.equal(r.next['6060'].lvl, 2, 'histereza: 400 ≥ 90 % od 420');
r = _trans(st(300), r.next, now); assert.equal(r.next['6060'].lvl, 1, 'spust 2→1 pod 90 % drugega praga');
r = _trans(st(250), r.next, now); assert.equal(r.next['6060'].lvl, 0, 'spust 1→0 pod 90 % prvega praga');
r = _trans(st(312), r.next, now); assert.equal(r.events.length, 1, 'ponoven porast po spustu');
// preskoki: 0 → 3 gre z eno obvestilo za najvišjo stopnjo
r = _trans(st(600), {}, now); assert.equal(r.events.length, 1); assert.equal(r.events[0].lvl, 3);
// 3. zastarela meritev, postaja brez pragov, neznana postaja
r = _trans(st(900, ['2026-10-17 10:00']), {}, now); assert.equal(r.fresh, 0); assert.equal(r.events.length, 0);
r = _trans(_parse('<xml>' + post('6120', 'Medlog', 900, undefined, null) + '</xml>'), {}, now); assert.equal(r.fresh, 0);
r = _trans(_parse('<xml>' + post('9999', 'Druga', 900) + '</xml>'), {}, now); assert.equal(r.fresh, 0);

// 4. cron
const env = { PHOTOS_R2: r2, VAPID_PRIVATE: 'x' };
const RealDate = Date;
ctx.Date = class extends RealDate { constructor(...a) { super(...(a.length ? a : [now])); } static now() { return now; } static parse(s) { return RealDate.parse(s); } };
vm.runInContext('Date = this.Date', ctx);
xml = '<xml>' + post('6060', 'Nazarje', 450) + '</xml>';
store['push/subs.json'] = JSON.stringify([{ endpoint: 'a' }]);
let calls = 0; const of = ctx.fetch; ctx.fetch = async (...a) => { calls++; return of(...a); };
await _cron(env); assert.equal(calls, 0, 'brez naročnikov vira ne kliče');
store['push/subs.json'] = JSON.stringify([{ endpoint: 'a', savinja: true }, { endpoint: 'b' }]);
await _cron(env);
assert.equal(pushed.length, 1); assert.equal(pushed[0].n, 1);
assert.match(pushed[0].payload.body, /Nazarjah/); assert.match(pushed[0].payload.body, /2\. prag/); assert.match(pushed[0].payload.body, /450 m³\/s/); assert.match(pushed[0].payload.body, /ni uradno opozorilo/);
await _cron(env); assert.equal(pushed.length, 1, 'drugi tik istega stanja ne ponovi');
fetchOk = false; let res = await _cron(env); assert.equal(res.ok, false, 'napaka vira se javi');
fetchOk = true; xml = '<xml>' + post('6060', 'Nazarje', 450, '2026-10-16 10:00') + '</xml>'; res = await _cron(env);
assert.equal(res.ok, false, 'zastarela meritev se javi, ne molči'); assert.equal(pushed.length, 1);
console.log('test_savinja_push: OK');
