/*
 * tools/test_nebo_alarm.mjs — preizkus »Nebo alarma« (Web Push, /nebo-nocoj/) iz worker.js.
 * Iz worker.js izreže blok med »── Nebo alarm« in »── Migrenski alarm« in ga požene z lažnim R2 in lažnim pošiljanjem
 * (prava koda, ne kopija). Preveri tudi, da so pravila in konstante enaka kot v nebo-nocoj/nebo.js (namerna podvojitev).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const M = require('../nebo-nocoj/nebo.js');
const src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
const a = src.indexOf('// ── Nebo alarm (Web Push');
const b = src.indexOf('// ── Migrenski alarm (Web Push');
assert(a > 0 && b > a, 'blok Nebo alarm ni najden');
const block = src.slice(a, b);

const store = {};
const r2 = { get: async k => (k in store ? { text: async () => store[k] } : null), put: async (k, v) => { store[k] = v; } };
const sent = [];
let code = 201;
const ctx = vm.createContext({
  console, JSON, Math, Date, Promise, Set, Array, Object, String, Number, Map, parseInt, parseFloat, isNaN, RegExp,
  _sendPush: async (_env, sub, payload) => { sent.push({ ep: sub.endpoint, payload }); return code; },
});
vm.runInContext(block + '\nthis._kpMax=_nebKpMax; this._cloud=_nebCloud; this._local=_nebLocalDate; this._tonight=_nebShowerTonight; this._moon=_nebMoon; this._notify=_nebNotify; this.C={NEBO_PUSH_KEY, NEBO_KP_LIMIT, NEBO_CLOUD_NO, NEBO_SHOWERS, NEBO_OD, NEBO_DO};', ctx);
const { _kpMax, _cloud, _local, _tonight, _moon, _notify, C } = ctx;
const env = { PHOTOS_R2: r2, VAPID_PRIVATE: 'x' };
const H = 3600 * 1000;
const NOW = Date.UTC(2026, 11, 14, 17, 30);        // 14. 12. 2026 18.30 po naši uri: večer vrha Geminidov

// 1. Kp: seznami z glavo in objekti, okno od −3 h do +24 h
const iso = ms => new Date(ms).toISOString().slice(0, 19).replace('T', ' ');
const rowsA = [['time_tag', 'kp', 'observed', 'noaa_scale'], [iso(NOW - 6 * H), '8.0', 'observed', 'G4'], [iso(NOW - 2 * H), '4.33', 'observed', null], [iso(NOW + 5 * H), '6.67', 'predicted', null], [iso(NOW + 30 * H), '9.0', 'predicted', 'G5']];
assert.equal(_kpMax(rowsA, NOW), 6.67, 'seznam z glavo: izven okna se ne šteje (−6 h in +30 h)');
const rowsO = rowsA.slice(1).map(r => ({ time_tag: r[0], kp: Number(r[1]), observed: r[2] }));
assert.equal(_kpMax(rowsO, NOW), 6.67, 'objekti');
assert.equal(_kpMax([{ time_tag: new Date(NOW + H).toISOString(), kp: '7.33' }], NOW), 7.33, 'ISO čas z Z');
assert.equal(_kpMax([], NOW), null); assert.equal(_kpMax(null, NOW), null); assert.equal(_kpMax([{ time_tag: 'x', kp: 'y' }], NOW), null);

// 2. lokalni datum in oblačnost nočnih ur
assert.equal(_local(Date.UTC(2026, 11, 14, 20, 0)), '2026-12-14', 'zima: 21.00 lokalno');
assert.equal(_local(Date.UTC(2026, 11, 14, 23, 30)), '2026-12-15', 'zima: 0.30 je že naslednji dan');
assert.equal(_local(Date.UTC(2026, 6, 1, 22, 30)), '2026-07-02', 'poletje (UTC+2)');
const hr = (day, h, c) => ({ t: `${day}T${String(h).padStart(2, '0')}:00`, c });
const rows = [hr('2026-12-14', 12, 100), hr('2026-12-14', 20, 10), hr('2026-12-14', 23, 30), hr('2026-12-15', 3, 20), hr('2026-12-15', 6, 100), hr('2026-12-16', 2, 100)];
const hourly = { time: rows.map(x => x.t), cloud_cover: rows.map(x => x.c) };
assert.equal(_cloud(hourly, '2026-12-14'), 20, 'ure 20–23 tistega dne in 0–5 naslednjega');
assert.equal(_cloud({ time: [], cloud_cover: [] }, '2026-12-14'), null);
assert.equal(_cloud(null, '2026-12-14'), null);
assert.equal(_cloud({ time: ['2026-12-14T21:00'], cloud_cover: [null] }, '2026-12-14'), null, 'null oblačnost se ne šteje');
assert.equal(_cloud({ time: ['2026-12-31T22:00', '2027-01-01T02:00'], cloud_cover: [40, 60] }, '2026-12-31'), 50, 'prehod čez novo leto');

// 3. roj nocoj
assert.equal(_tonight('2026-12-14').id, 'geminidi'); assert.equal(_tonight('2027-01-03').id, 'kvadrantidi');
assert.equal(_tonight('2026-12-15'), null); assert.equal(_tonight('2026-11-17').id, 'leonidi');
assert.equal(_tonight('2026-11-14'), null, 'isti dan v mesecu, drug mesec: ni vrha');
assert.equal(_tonight('2026-12-03'), null, '3. 12. ni vrh Kvadrantidov (3. 1.)');
assert.equal(_tonight('2026-12-17'), null, '17. 12. ni vrh Leonidov (17. 11.)');

// 4. pravila so enaka kot v nebo-nocoj/nebo.js
assert.equal(C.NEBO_KP_LIMIT, M.KP_LIMIT, 'prag Kp');
assert.equal(M.cloudVerdict(C.NEBO_CLOUD_NO - 0.1).lvl !== 'no', true); assert.equal(M.cloudVerdict(C.NEBO_CLOUD_NO).lvl, 'no', 'prag oblačnosti 70 = stran pravi »ne«');
assert.deepEqual(JSON.parse(JSON.stringify(Array.from(C.NEBO_SHOWERS))), M.SHOWERS.map(s => ({ id: s.id, name: s.name, peak: s.peak, zhr: s.zhr })), 'roji');
for (const t of [Date.UTC(2000, 0, 6, 18, 14), Date.UTC(2000, 0, 21, 4, 40), Date.UTC(2026, 11, 14, 22), Date.UTC(2027, 0, 3, 22), Date.UTC(2026, 10, 24)]) assert(Math.abs(_moon(t) - M.moonIllum(t)) < 1e-12, 'luna ' + t);
const nc = M.nightCloud(rows.filter(x => x.t.startsWith('2026-12-14') && +x.t.slice(11, 13) >= 20 || x.t.startsWith('2026-12-15') && +x.t.slice(11, 13) <= 5).map(x => ({ h: +x.t.slice(11, 13), c: x.c })));
assert.equal(nc, _cloud(hourly, '2026-12-14'), 'nočna oblačnost: isto kot na strani');

// 5. obvestila
const sub = (ep, sij, roji) => ({ endpoint: ep, keys: { p256dh: 'a', auth: 'b' }, sij, roji, st: {} });
const reset = subs => { store[C.NEBO_PUSH_KEY] = JSON.stringify(subs); sent.length = 0; };
const stored = () => JSON.parse(store[C.NEBO_PUSH_KEY]);
reset([sub('https://p/roji', false, true), sub('https://p/sij', true, false), sub('https://p/oboje', true, true)]);
// vrh roja + jasno, Kp nizek: samo roji
let r = await _notify(env, { kp: 3, cloud: 20 }, NOW);
assert.deepEqual(sent.map(x => x.ep).sort(), ['https://p/oboje', 'https://p/roji'], 'roji: kdor jih je vklopil');
assert.match(sent[0].payload.title, /Geminidi/); assert.match(sent[0].payload.body, /150 utrinkov/); assert.match(sent[0].payload.body, /oblačnost 20 %/);
assert.match(sent[0].payload.body, /ne moti/, 'Geminidi 2026: luna ne moti'); assert.equal(sent[0].payload.tag, 'nebo-roj'); assert.equal(sent[0].payload.url, 'https://meteorec.si/nebo-nocoj/');
// isti večer ne ponovi (ni ob 2. tiku)
sent.length = 0; r = await _notify(env, { kp: 3, cloud: 20 }, NOW + H);
assert.equal(sent.length, 0, 'enkrat na večer');
// Kp 7,3 in jasno: sij samo tistim, ki so ga vklopili (roji so že poslani)
r = await _notify(env, { kp: 7.3, cloud: 20 }, NOW + 2 * H);
assert.deepEqual(sent.map(x => x.ep).sort(), ['https://p/oboje', 'https://p/sij'], 'sij: kdor ga je vklopil');
assert.equal(sent[0].payload.tag, 'wx-aurora', 'isti tag kot splošni alarm: obvestili se ne podvojita');
assert.match(sent[0].payload.body, /Kp 7,3/); assert.match(sent[0].payload.body, /ne obljuba/);
// naslednji večer (ni vrh roja): sij znova
sent.length = 0; r = await _notify(env, { kp: 8, cloud: 10 }, NOW + 24 * H);
assert.deepEqual(sent.map(x => x.ep).sort(), ['https://p/oboje', 'https://p/sij'], 'drug večer drugo obvestilo');
assert.equal(sent.every(x => x.payload.tag === 'wx-aurora'), true, 'roja ta večer ni');
// pogoji: oblačno, Kp 6,9, Kp brez podatka
reset([sub('https://p/x', true, true)]);
await _notify(env, { kp: 9, cloud: 70 }, NOW); assert.equal(sent.length, 0, 'oblačnost 70 %: nič');
await _notify(env, { kp: 6.9, cloud: 10 }, NOW + 24 * H); assert.equal(sent.length, 0, 'Kp 6,9 pod pragom, roja ta večer ni: nič');
await _notify(env, { kp: null, cloud: 10 }, NOW); assert.deepEqual(sent.map(x => x.payload.tag), ['nebo-roj'], 'brez Kp: roji vseeno, sij ne');
reset([sub('https://p/x', true, true)]);
r = await _notify(env, { kp: 9, cloud: null }, NOW); assert.equal(r.skipped, 'ni napovedi oblačnosti'); assert.equal(sent.length, 0, 'brez oblačnosti ne trdi nič');
// naročnina brez kljukic ne dobi nič; potekla naročnina se odstrani; napaka pošiljanja ne zapiše stanja
reset([sub('https://p/none', false, false)]); await _notify(env, { kp: 9, cloud: 10 }, NOW); assert.equal(sent.length, 0);
code = 410; reset([sub('https://p/dead', true, true), sub('https://p/live', false, false)]);
r = await _notify(env, { kp: 9, cloud: 10 }, NOW);
assert.equal(r.pruned, 1); assert.deepEqual(stored().map(x => x.endpoint), ['https://p/live'], 'potekla naročnina odstranjena');
assert.equal(sent.filter(x => x.ep === 'https://p/dead').length, 1, 'po 410 se za isto naročnino ne pošilja drugega obvestila');
code = 201;
code = 500; reset([sub('https://p/err', true, true)]); await _notify(env, { kp: 9, cloud: 10 }, NOW);
assert.deepEqual(stored()[0].st, { sij: _local(NOW), roji: _local(NOW) }, 'koda 500 (ne 404/410) se šteje kot poslano: brez neskončnega ponavljanja');
code = 201;
// brez VAPID
assert.equal((await _notify({ PHOTOS_R2: r2 }, { kp: 9, cloud: 10 }, NOW)).skipped, 'ni shrambe ali VAPID');
// večerno okno
assert.deepEqual([C.NEBO_OD, C.NEBO_DO], [17, 23]);
// 6. strežnik: lasten seznam, kljukici, cron
assert(src.includes('body.site === "nebo"'), 'endpoint za site:"nebo"');
assert(/nebo: 20/.test(src), 'cron nebo v CRON_JOBS (zdravje)');
assert(src.includes('_cronBeat(env, "nebo"'), 'cron nebo v scheduled()');
console.log('test_nebo_alarm: vse v redu');
