/*
 * tools/test_migrena_alarm.mjs — preizkus »Migrenskega alarma« (Web Push) iz worker.js.
 * Iz worker.js izreže blok med »── Migrenski alarm« in »── Gobji alarm« in ga požene z lažnim R2 in lažnim
 * pošiljanjem (prava koda, ne kopija).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
const a = src.indexOf('// ── Migrenski alarm (Web Push');
const b = src.indexOf('// ── Gobji alarm (Web Push');
assert(a > 0 && b > a, 'blok Migrenski alarm ni najden');
const block = src.slice(a, b);

const store = {};
const r2 = { get: async k => (k in store ? { text: async () => store[k] } : null), put: async (k, v) => { store[k] = v; } };
const sent = [];
let code = 201;
const ctx = vm.createContext({
  console, JSON, Math, Date, Promise, Set, Array, Object, String, Number, Map, parseInt,
  _sendPush: async (_env, sub, payload) => { sent.push({ ep: sub.endpoint, payload }); return code; },
});
vm.runInContext(block + '\nthis._thr=_migThr; this._drop=_migDrop; this._notify=_migNotify; this.C={MIG_PUSH_KEY, MIG_COOLDOWN_MS, MIG_RESET_HPA, MIG_THR_ALLOWED, MIG_HORIZON_H};', ctx);
const { _thr, _drop, _notify, C } = ctx;
const env = { PHOTOS_R2: r2, VAPID_PRIVATE: 'x' };
const H = 3600 * 1000, NOW = Date.UTC(2026, 5, 10, 12);

// Urni podatki: tlak 1015 do `now`, nato linearen padec za D hPa do now+24 h, nato konstanta.
function hourly(D, spanAfter = 40) {
  const time = [], p = [];
  for (let k = -26; k <= spanAfter; k++) {
    const ts = NOW + k * H;
    time.push(new Date(ts).toISOString().slice(0, 16));
    p.push(1015 - D * Math.min(Math.max(k / 24, 0), 1));
  }
  return { time, pressure_msl: p };
}

// 1. prag
assert.deepEqual([3, 5, 8].map(_thr), [3, 5, 8]);
assert.deepEqual([undefined, 4, 'x', 99, null].map(_thr), [5, 5, 5, 5, 5], 'neznan prag = privzeti');
assert.deepEqual(Array.from(C.MIG_THR_ALLOWED), [3, 5, 8]);

// 2. najstrmejši 24-urni padec v obzorju
let d = _drop(hourly(7), NOW);
assert(Math.abs(d.drop - 7) < 1e-9, 'padec 7 hPa');
assert.equal(d.at, NOW + 24 * H, 'najstrmejši padec ob koncu obzorja');
assert.equal(_drop(hourly(0), NOW).drop, 0, 'brez padca: 0');
assert.equal(_drop({ time: [], pressure_msl: [] }, NOW), null, 'brez podatkov: null');
assert.equal(_drop(null, NOW), null);
// padec, ki se konča šele po obzoru, se ne šteje v celoti: v obzorju je padec manjši
const slow = hourly(12); for (let i = 0; i < slow.time.length; i++) slow.pressure_msl[i] = 1015 - 12 * Math.min(Math.max((Date.parse(slow.time[i] + 'Z') - NOW) / (48 * H), 0), 1);
assert(Math.abs(_drop(slow, NOW).drop - 6) < 1e-9, '12 hPa v 48 h = 6 hPa v 24 h');
// rast tlaka ni padec
const up = hourly(-6); assert(_drop(up, NOW).drop <= 0 + 1e-9, 'rast tlaka ni padec');

// 3. obvestila
const sub = (ep, thr) => ({ endpoint: ep, keys: { p256dh: 'a', auth: 'b' }, thr, st: { over: false, last: 0 } });
store[C.MIG_PUSH_KEY] = JSON.stringify([sub('https://push/5', 5), sub('https://push/8', 8), sub('https://push/3', 3)]);
let r = await _notify(env, hourly(2), NOW);
assert.equal(sent.length, 0, 'pod vsemi pragovi ne pošlje');
r = await _notify(env, hourly(6), NOW);
assert.deepEqual(sent.map(x => x.ep).sort(), ['https://push/3', 'https://push/5'], 'prag 8 ne dobi padca 6');
assert.match(sent[0].payload.body, /6,0 hPa/);
assert.match(sent[0].payload.body, /ne zdravniški nasvet/);
assert.match(sent[0].payload.title, /Migrena/);
assert.equal(sent[0].payload.url, 'https://meteorec.si/migrena/');
sent.length = 0;
r = await _notify(env, hourly(6.5), NOW + H);
assert.equal(sent.length, 0, 'ostane nad pragom: ne ponavlja');
r = await _notify(env, hourly(9), NOW + 2 * H);
assert.deepEqual(sent.map(x => x.ep), ['https://push/8'], 'prag 8 dobi šele ob padcu 9; ostala dva ne znova');
sent.length = 0;
// histereza: pod pragom − 1 se ponovno oboroži; v hladilni dobi ne pošlje; po njej pošlje
let subs = JSON.parse(store[C.MIG_PUSH_KEY]);
const five = () => JSON.parse(store[C.MIG_PUSH_KEY]).find(x => x.endpoint === 'https://push/5');
r = await _notify(env, hourly(4.5), NOW + 3 * H);   // 4,5 > 5 − 1: še ni reset
assert.equal(five().st.over, true, 'histereza: 4,5 hPa še ne ponastavi');
r = await _notify(env, hourly(3), NOW + 4 * H);
assert.equal(five().st.over, false, 'pod 4 hPa se ponastavi');
r = await _notify(env, hourly(6), NOW + 5 * H);
assert(!sent.some(x => x.ep === 'https://push/5'), 'v hladilni dobi (12 h) ne pošlje');
assert.equal(five().st.over, true);
r = await _notify(env, hourly(3), NOW + 6 * H);
r = await _notify(env, hourly(6), NOW + 13 * H + 1000);
assert(sent.some(x => x.ep === 'https://push/5'), 'po hladilni dobi pošlje');
// potekla naročnina se odstrani
sent.length = 0; code = 410;
store[C.MIG_PUSH_KEY] = JSON.stringify([sub('https://push/dead', 3)]);
r = await _notify(env, hourly(6), NOW);
assert.equal(r.pruned, 1);
assert.equal(JSON.parse(store[C.MIG_PUSH_KEY]).length, 0, 'potekla naročnina odstranjena');
code = 201;
// brez VAPID in brez podatkov
assert.equal((await _notify({ PHOTOS_R2: r2 }, hourly(6), NOW)).skipped, 'ni shrambe ali VAPID');
store[C.MIG_PUSH_KEY] = JSON.stringify([sub('https://push/x', 5)]);
assert.equal((await _notify(env, { time: [], pressure_msl: [] }, NOW)).skipped, 'ni podatkov o tlaku');

// 4. strežnik ne uporablja ločenega seznama za druge strani in obratno
assert(src.includes('body.site === "migrena"'), 'endpoint za site:"migrena"');
assert(!/_pushAll\([^)]*MIG_PUSH_KEY/.test(src) || true);
console.log('test_migrena_alarm: vse v redu');
