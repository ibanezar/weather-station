/*
 * tools/test_frost_push.mjs — preizkus večernega opozorila na zmrzal iz worker.js.
 * Izreže blok »Zmrzal nocoj« in ga požene z lažnim R2 in lažnim pošiljanjem (prava koda).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
const a = src.indexOf('// ── Zmrzal nocoj (Web Push');
const b = src.indexOf('// ── Začetek/konec dejanskih padavin');
assert(a > 0 && b > a, 'blok Zmrzal nocoj ni najden');

const store = {};
const r2 = { get: async k => (k in store ? { text: async () => store[k] } : null), put: async (k, v) => { store[k] = v; } };
const pushed = [];
let model = null, fetches = 0;
const ctx = vm.createContext({
  console, JSON, Math, Date, Promise, Number, Array, String, Object, Intl,
  _ljDatum: d => d.toLocaleDateString('sv-SE', { timeZone: 'Europe/Ljubljana' }),
  _pushAll: async (_e, payload, filter) => { pushed.push({ payload, n: JSON.parse(store['push/subs.json']).filter(filter).length }); return {}; },
  fetch: async () => { fetches++; return { ok: true, json: async () => model }; },
});
vm.runInContext(block(), ctx);
function block() { return src.slice(a, b) + '\nthis._pick=_frostPick; this._cron=_cronCheckFrost;'; }
const { _pick, _cron } = ctx;
const H = 3600 * 1000;
const now = Date.parse('2026-10-18T17:30:00Z');          // 19:30 po naši uri
const gen = new Date(now - 10 * H).toISOString();
const mk = (p, extra = {}) => ({ generated_at: gen, days: [{ date: '2026-10-18', p_frost: 0, tmin: 7 }, { date: '2026-10-19', p_frost: p, tmin: -1.4, ...extra }] });

// 1. izbira dneva po datumu, prag, zaokroževanje na 5 %
assert.equal(_pick(mk(0.62), '2026-10-19', now).pct, 60);
assert.equal(_pick(mk(0.63), '2026-10-19', now).pct, 65);
assert.equal(_pick(mk(0.39), '2026-10-19', now).send, false, 'pod pragom');
assert.equal(_pick(mk(0.40), '2026-10-19', now).send, true, 'natanko na pragu');
assert.equal(_pick(mk(0.9), '2026-10-20', now).ok, false, 'dan brez vnosa ni »ni zmrzali«');
assert.equal(_pick({ generated_at: new Date(now - 40 * H).toISOString(), days: mk(0.9).days }, '2026-10-19', now).ok, false, 'zastarela datoteka');
assert.equal(_pick(mk(0.9, { p_frost: undefined }), '2026-10-19', now).ok, false, 'brez p_frost');
assert.equal(_pick(null, '2026-10-19', now).ok, false);

// 2. cron: ura, naročniki, enkrat na dan
const env = { PHOTOS_R2: r2, VAPID_PRIVATE: 'x' };
const RealDate = Date;
function at(ms) { ctx.Date = class extends RealDate { constructor(...a) { super(...(a.length ? a : [ms])); } static now() { return ms; } }; vm.runInContext('Date = this.Date', ctx); }
store['push/subs.json'] = JSON.stringify([{ endpoint: 'a', frost: true }, { endpoint: 'b' }]);
model = mk(0.7);
at(now - 3 * H);                                          // 16:30 — prezgodaj
await _cron(env); assert.equal(pushed.length, 0); assert.equal(fetches, 0);
at(now);
await _cron(env);
assert.equal(pushed.length, 1); assert.equal(pushed[0].n, 1, 'samo naročnik s kljukico');
assert.match(pushed[0].payload.body, /70 %/); assert.match(pushed[0].payload.body, /-1,4/); assert.match(pushed[0].payload.body, /ne uradno/);
await _cron(env); assert.equal(pushed.length, 1, 'enkrat na jutrišnji datum');
// 3. zastarela napoved: ne pošlje, ne zaklene dneva — naslednji tik poskusi znova
delete store['push/frost_state.json'];
model = { ...mk(0.7), generated_at: new RealDate(now - 50 * H).toISOString() };
const r = await _cron(env); assert.equal(r.ok, false); assert.equal(pushed.length, 1); assert.ok(!store['push/frost_state.json']);
// 4. nizka verjetnost: dan se zaklene, obvestila ni
model = mk(0.1); await _cron(env);
assert.equal(pushed.length, 1); assert.equal(JSON.parse(store['push/frost_state.json']).sent, false);
// 5. brez naročnikov vira ne kliče
delete store['push/frost_state.json']; store['push/subs.json'] = JSON.stringify([{ endpoint: 'b' }]);
const f0 = fetches; await _cron(env); assert.equal(fetches, f0);
console.log('test_frost_push: OK');
