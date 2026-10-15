/*
 * tools/test_gobe_alarm.mjs — preizkus »Gobjega alarma« (Web Push) iz worker.js.
 * Iz worker.js izreže blok med »── Gobji alarm« in »── Opozorila s prelaza Črnivec«
 * in ga požene z lažnim R2 in lažnim pošiljanjem (prava koda, ne kopija).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
const a = src.indexOf('// ── Gobji alarm (Web Push');
const b = src.indexOf('// ── Opozorila s prelaza Črnivec');
assert(a > 0 && b > a, 'blok Gobji alarm ni najden');
const block = src.slice(a, b);

const store = {};
const r2 = {
  get: async k => (k in store ? { text: async () => store[k] } : null),
  put: async (k, v) => { store[k] = v; },
};
const sent = [];
let sendCode = 201;
const ctx = vm.createContext({
  console, JSON, Math, Date, Promise, Set, Array, Object, String, parseInt,
  _sendPush: async (_env, sub, payload) => { sent.push({ ep: sub.endpoint, payload }); return sendCode; },
});
vm.runInContext(block + '\nthis._clean=_gobeAlarmClean; this._notify=_gobeAlarmNotify; this.C={GOBE_PUSH_KEY, GOBE_ALARM_RESET_PTS, GOBE_ALARM_COOLDOWN_DAYS};', ctx);
const { _clean, _notify, C } = ctx;
const env = { PHOTOS_R2: r2, VAPID_PRIVATE: 'x' };

const picker = { species: new Set(['boletus_edulis', 'cantharellus_cibarius']), locations: new Set(['Rečica ob Savinji', 'Gozdovi nad Ljubnim']) };
const digest = v => ({ species_meta: { boletus_edulis: { name_sl: 'Jurček' } }, locations: [
  { name: 'Gozdovi nad Ljubnim', days: [{ species: [{ id: 'boletus_edulis', index: v }] }] }] });
const rule = { species_id: 'boletus_edulis', location: 'Gozdovi nad Ljubnim', threshold: 75 };

// 1. čiščenje pravil
assert.equal(JSON.stringify(_clean(picker, [rule])), JSON.stringify([rule]));
assert.equal(_clean(picker, [{ ...rule, species_id: 'amanita_phalloides' }]), null, 'neznana vrsta');
assert.equal(_clean(picker, [{ ...rule, location: 'Drugje' }]), null, 'neznano območje');
assert.equal(_clean(picker, 'x'), null);
assert.equal(_clean(picker, [{ ...rule, threshold: 5 }])[0].threshold, 40, 'spodnja meja praga');
assert.equal(_clean(picker, [{ ...rule, threshold: 500 }])[0].threshold, 95, 'zgornja meja praga');
assert.equal(_clean(picker, [rule, rule]).length, 1, 'podvojeno pravilo');
const four = ['boletus_edulis', 'cantharellus_cibarius'].flatMap(s => ['Rečica ob Savinji', 'Gozdovi nad Ljubnim'].map(l => ({ ...rule, species_id: s, location: l })));
assert.equal(_clean(picker, four).length, 3, 'največ 3 pravila');

// 2. prehod čez prag, histereza, hladilna doba
const sub = { endpoint: 'https://push/1', keys: { p256dh: 'a', auth: 'b' }, rules: [rule], st: {} };
store[C.GOBE_PUSH_KEY] = JSON.stringify([sub]);
let r = await _notify(env, digest(60));
assert.equal(sent.length, 0, 'pod pragom ne pošlje');
r = await _notify(env, digest(80));
assert.equal(sent.length, 1, 'čez prag pošlje');
assert.match(sent[0].payload.body, /Jurček · Gozdovi nad Ljubnim: 80\/100/);
assert.match(sent[0].payload.body, /ne obljuba najdbe/);
r = await _notify(env, digest(85));
assert.equal(sent.length, 1, 'ostane nad pragom: ne ponavlja');
r = await _notify(env, digest(72));
assert.equal(sent.length, 1, '72 je znotraj histereze (prag − 8 = 67): še vedno »nad«');
r = await _notify(env, digest(60));
assert.equal(sent.length, 1, 'pade pod prag − 8: ponastavi, ne pošlje');
r = await _notify(env, digest(90));
assert.equal(sent.length, 1, 'ponoven prehod isti dan: hladilna doba');
// hladilna doba mine
const st = JSON.parse(store[C.GOBE_PUSH_KEY]);
st[0].st['boletus_edulis|Gozdovi nad Ljubnim'].last = '2000-01-01';
store[C.GOBE_PUSH_KEY] = JSON.stringify(st);
await _notify(env, digest(60)); await _notify(env, digest(90));
assert.equal(sent.length, 2, 'po hladilni dobi znova');

// 3. potekla naročnina (410) se pobriše
sendCode = 410;
const st2 = JSON.parse(store[C.GOBE_PUSH_KEY]);
st2[0].st = {};
store[C.GOBE_PUSH_KEY] = JSON.stringify(st2);
r = await _notify(env, digest(95));
assert.equal(r.pruned, 1);
assert.equal(JSON.parse(store[C.GOBE_PUSH_KEY]).length, 0, 'mrtva naročnina odstranjena');

// 4. manjkajoča vrsta v izvlečku ne zruši
sendCode = 201;
store[C.GOBE_PUSH_KEY] = JSON.stringify([sub]);
r = await _notify(env, { species_meta: {}, locations: [] });
assert.equal(r.sent, 0);

console.log('gobji alarm: vsa preverjanja v redu');
