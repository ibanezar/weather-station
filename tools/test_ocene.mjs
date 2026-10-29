/*
 * tools/test_ocene.mjs — preizkus »Opozoril po ocenah« (Web Push) iz worker.js.
 * Iz worker.js izreže blok med »── Opozorila po ocenah« in »── Migrenski alarm« in ga požene z lažnim R2 in lažnim
 * pošiljanjem (prava koda, ne kopija).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
const a = src.indexOf('// ── Opozorila po ocenah (Web Push');
const b = src.indexOf('// ── Migrenski alarm (Web Push');
assert(a > 0 && b > a, 'blok Opozorila po ocenah ni najden');
const block = src.slice(a, b);

const store = {};
const r2 = { get: async k => (k in store ? { text: async () => store[k] } : null), put: async (k, v) => { store[k] = v; } };
const sent = [];
let code = 201;
const ctx = vm.createContext({
  console, JSON, Math, Date, Promise, Set, Array, Object, String, Number, Map, parseInt, Number,
  _sendPush: async (_env, sub, payload) => { sent.push({ ep: sub.endpoint, payload }); return code; },
});
vm.runInContext(block + '\nthis._clean=_oceneClean; this._notify=_oceneNotify; this._dates=_oceneDates; this.C={OCENE_PUSH_KEY, OCENE_MAX_RULES, OCENE_MAX_AGE_H};', ctx);
const { _clean, _notify, _dates, C } = ctx;
const env = { PHOTOS_R2: r2, VAPID_PRIVATE: 'x' };

const NOW = Date.UTC(2026, 5, 10, 10);        // 10. 6. 2026 12.00 po naši uri
const D = _dates(NOW);
assert.deepEqual({ ...D }, { danes: '2026-06-10', jutri: '2026-06-11' });
// čez polnoč po naši uri: 23.30 po naši uri (UTC 21.30) je še 10. 6.; 00.30 (UTC 22.30) je že 11. 6.
assert.equal(_dates(Date.UTC(2026, 5, 10, 21, 30)).danes, '2026-06-10');
assert.equal(_dates(Date.UTC(2026, 5, 10, 22, 30)).danes, '2026-06-11');
assert.equal(_dates(Date.UTC(2026, 5, 10, 22, 30)).jutri, '2026-06-12');
// konec meseca
assert.equal(_dates(Date.UTC(2026, 5, 30, 10)).jutri, '2026-07-01');

const data = {
  generated: new Date(NOW - 5 * 3600e3).toISOString(),
  pages: {
    'susenje-perila': { naslov: 'Sušenje perila', url: '/susenje-perila/', levels: ['odlično', 'dobro', 'slabo', 'neprimerno'],
      days: [{ date: '2026-06-10', lvl: 2, reasons: ['vlaga povprečno 84 %', 'veter povprečno 5 km/h'] }, { date: '2026-06-11', lvl: 0, reasons: [] }] },
    astma: { naslov: 'Vreme in astma', url: '/astma/', levels: ['nizko', 'zmerno', 'povišano', 'visoko'],
      days: [{ date: '2026-06-10', lvl: 1, reasons: [] }, { date: '2026-06-11', lvl: 3, reasons: ['breza 120 zrn/m³'] }] },
  },
};

// 1. čiščenje pravil
const ok = { page: 'astma', op: 'ge', lvl: 2, when: 'jutri' };
assert.equal(JSON.stringify(_clean(data, [ok])), JSON.stringify([ok]));
assert.equal(_clean(data, [{ ...ok, page: 'neznana' }]), null, 'neznana stran');
assert.equal(_clean(data, [{ ...ok, op: 'eq' }]), null, 'neznana operacija');
assert.equal(_clean(data, [{ ...ok, lvl: 4 }]), null, 'raven nad 3');
assert.equal(_clean(data, [{ ...ok, lvl: -1 }]), null, 'raven pod 0');
assert.equal(_clean(data, [{ ...ok, lvl: 1.5 }]), null, 'necela raven');
assert.equal(_clean(data, [{ ...ok, when: 'pojutrišnjem' }]), null, 'neznan dan');
assert.equal(_clean(data, 'x'), null);
assert.equal(_clean(data, [null]), null);
assert.equal(_clean(data, [ok, ok]).length, 1, 'podvojeno pravilo');
assert.equal(JSON.stringify(_clean(data, [])), '[]', 'prazen seznam = odjava');
const many = ['danes', 'jutri'].flatMap(w => [0, 1, 2, 3].map(l => ({ page: 'astma', op: 'ge', lvl: l, when: w })));
assert.equal(_clean(data, many).length, C.OCENE_MAX_RULES, 'največ pravil');

// 2. obvestila
const sub = (ep, rules) => ({ endpoint: ep, keys: { p256dh: 'a', auth: 'b' }, rules, st: {} });
store[C.OCENE_PUSH_KEY] = JSON.stringify([
  sub('https://push/perilo-slabo-danes', [{ page: 'susenje-perila', op: 'ge', lvl: 2, when: 'danes' }]),
  sub('https://push/perilo-odlicno-jutri', [{ page: 'susenje-perila', op: 'le', lvl: 0, when: 'jutri' }]),
  sub('https://push/astma-visoko-jutri', [{ page: 'astma', op: 'ge', lvl: 3, when: 'jutri' }]),
  sub('https://push/astma-visoko-danes', [{ page: 'astma', op: 'ge', lvl: 3, when: 'danes' }]),
  sub('https://push/dve', [{ page: 'susenje-perila', op: 'ge', lvl: 2, when: 'danes' }, { page: 'astma', op: 'ge', lvl: 3, when: 'jutri' }]),
]);
let r = await _notify(env, data, NOW);
const got = Object.fromEntries(sent.map(x => [x.ep.replace('https://push/', ''), x.payload]));
assert.deepEqual(Object.keys(got).sort(), ['astma-visoko-jutri', 'dve', 'perilo-odlicno-jutri', 'perilo-slabo-danes'], 'prave naprave dobijo obvestilo');
assert.match(got['perilo-slabo-danes'].body, /^Sušenje perila: danes \(sreda\) raven »slabo«: vlaga povprečno 84 %; veter povprečno 5 km\/h\./);
assert.match(got['perilo-slabo-danes'].body, /Modelska napoved, ne meritev\.$/);
assert.equal(got['perilo-slabo-danes'].url, 'https://meteorec.si/susenje-perila/');
assert.match(got['perilo-odlicno-jutri'].body, /jutri \(četrtek\) raven »odlično«/);
assert.match(got['astma-visoko-jutri'].body, /raven »visoko«: breza 120 zrn\/m³/);
assert.match(got['dve'].body, /In še 1 tvoje opozorilo/, 'več pravil: eno obvestilo');
assert.equal(sent.filter(x => x.ep.endsWith('/dve')).length, 1);
assert.equal(r.sent, 4);
// ista ciljna dneva ne sprožita znova
sent.length = 0;
r = await _notify(env, data, NOW + 3600e3);
assert.equal(sent.length, 0, 'enkrat na pravilo in ciljni dan');
// naslednji dan je nov ciljni dan: pravilo »danes« se lahko sproži znova (stanje je po datumu)
const next = JSON.parse(JSON.stringify(data)); next.generated = new Date(NOW + 20 * 3600e3).toISOString();
next.pages.astma.days = [{ date: '2026-06-11', lvl: 3, reasons: [] }, { date: '2026-06-12', lvl: 0, reasons: [] }];
r = await _notify(env, next, NOW + 24 * 3600e3);
assert.deepEqual(sent.map(x => x.ep.replace('https://push/', '')), ['astma-visoko-danes'], 'novi dan, novo obvestilo');
// stare ocene ne sprožijo ničesar
sent.length = 0;
const stale = { ...data, generated: new Date(NOW - 40 * 3600e3).toISOString() };
store[C.OCENE_PUSH_KEY] = JSON.stringify([sub('https://push/x', [{ page: 'astma', op: 'ge', lvl: 1, when: 'danes' }])]);
r = await _notify(env, stale, NOW);
assert.equal(r.skipped, 'ocene so stare'); assert.equal(sent.length, 0);
// ni ocene za ciljni dan (stran je prazna za jutri): nič
const noTomorrow = JSON.parse(JSON.stringify(data)); noTomorrow.pages.astma.days = [{ date: '2026-06-10', lvl: 3, reasons: [] }];
store[C.OCENE_PUSH_KEY] = JSON.stringify([sub('https://push/y', [{ page: 'astma', op: 'ge', lvl: 1, when: 'jutri' }])]);
await _notify(env, noTomorrow, NOW); assert.equal(sent.length, 0, 'brez ocene za ciljni dan ne pošlje');
// napaka pošiljanja (ne 404/410): stanje se ne zapiše in se poskusi znova
store[C.OCENE_PUSH_KEY] = JSON.stringify([sub('https://push/z', [{ page: 'astma', op: 'ge', lvl: 3, when: 'jutri' }])]);
const _send = ctx._sendPush; ctx._sendPush = async () => { throw new Error('omrežje'); };
await _notify(env, data, NOW);
assert.deepEqual(JSON.parse(store[C.OCENE_PUSH_KEY])[0].st, {}, 'neuspeh ne porabi opozorila');
ctx._sendPush = _send; sent.length = 0;
await _notify(env, data, NOW + 3600e3); assert.equal(sent.length, 1, 'naslednji poskus uspe');
// potekla naročnina se odstrani
sent.length = 0; code = 410;
store[C.OCENE_PUSH_KEY] = JSON.stringify([sub('https://push/dead', [{ page: 'astma', op: 'ge', lvl: 3, when: 'jutri' }])]);
r = await _notify(env, data, NOW);
assert.equal(r.pruned, 1); assert.equal(JSON.parse(store[C.OCENE_PUSH_KEY]).length, 0);
code = 201;
assert.equal((await _notify({ PHOTOS_R2: r2 }, data, NOW)).skipped, 'ni shrambe ali VAPID');

// 3. endpoint in cron obstajata
assert(src.includes('body.site === "ocene"'), 'endpoint za site:"ocene"');
assert(src.includes('_cronBeat(env, "ocene"'), 'cron opravilo');
assert(/ocene: 20,/.test(src), 'CRON_JOBS');
console.log('test_ocene: vse v redu');
