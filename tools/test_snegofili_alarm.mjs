/*
 * tools/test_snegofili_alarm.mjs — preizkus »Snegofili alarma« (Web Push, /snegofili/) iz worker.js.
 * Iz worker.js izreže blok med »── Snegofili alarm« in »── Nebo alarm« in ga požene z lažnim R2 in lažnim pošiljanjem
 * (prava koda, ne kopija). Prage 5/15/30 cm veže na step() v snegofili/snegofili.js (namerna podvojitev).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const SG = require('../snegofili/snegofili.js');
const src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
const a = src.indexOf('// ── Snegofili alarm (Web Push');
const b = src.indexOf('// ── Nebo alarm (Web Push');
assert(a > 0 && b > a, 'blok Snegofili alarm ni najden');
const block = src.slice(a, b);

const store = {};
const r2 = { get: async k => (k in store ? { text: async () => store[k] } : null), put: async (k, v) => { store[k] = v; } };
const sent = [];
let code = 201;
const ctx = vm.createContext({
  console, JSON, Math, Date, Promise, Set, Array, Object, String, Number, Map, parseInt, isNaN,
  _sendPush: async (_env, sub, payload) => { sent.push({ ep: sub.endpoint, payload }); return code; },
});
vm.runInContext(block + '\nthis._clean=_sgClean; this._notify=_sgNotify; this._text=_sgText; this.C={SG_PUSH_KEY, SG_CM_ALLOWED, SG_MAX_RULES, SG_MAX_AGE_H, SG_COOLDOWN_MS, SG_RESET_FRAC, SG_TIHO_OD, SG_TIHO_DO};', ctx);
const { _clean, _notify, _text, C } = ctx;
const env = { PHOTOS_R2: r2, VAPID_PRIVATE: 'x' };
const H = 3600 * 1000, NOW = Date.UTC(2026, 11, 3, 8, 0);

const pt = (id, cm, ime = id, elev = 1400) => ({ id, ime, elevation_m: elev, next24_cm: cm, next24_mm: cm / 10 });
const data = (pts, gen = NOW - H) => ({ generated_at: new Date(gen).toISOString(), tocke: pts });

// 1. čiščenje pravil
const D = data([pt('golte', 0), pt('krvavec', 0), pt('tignes', 0), pt('zugspitze', 0)]);
assert.deepEqual(Array.from(C.SG_CM_ALLOWED), [5, 15, 30]);
assert.deepEqual(JSON.parse(JSON.stringify(_clean(D, [{ id: 'golte', cm: 15 }, { id: 'krvavec', cm: 5 }]))), [{ id: 'golte', cm: 15 }, { id: 'krvavec', cm: 5 }]);
assert.equal(_clean(D, [{ id: 'neznana', cm: 15 }]), null, 'neznana točka');
assert.equal(_clean(D, [{ id: 'golte', cm: 10 }]), null, 'prag izven 5/15/30');
assert.equal(_clean(D, [{ id: 'golte', cm: '15' }]).length, 1, 'prag kot niz je veljaven');
assert.equal(_clean(D, 'x'), null); assert.equal(_clean(D, [null]), null); assert.equal(_clean(D, [{ id: 'golte', cm: 'x' }]), null);
assert.equal(_clean(D, [{ id: 'golte', cm: 15 }, { id: 'golte', cm: 15 }]).length, 1, 'dvojnik');
assert.equal(_clean(D, [{ id: 'golte', cm: 5 }, { id: 'golte', cm: 15 }, { id: 'golte', cm: 30 }, { id: 'krvavec', cm: 5 }]).length, 3, 'največ SG_MAX_RULES pravil');
assert.deepEqual(Array.from(_clean(D, [])), [], 'prazen seznam = odjava');

// 2. prage veže na model strani: vsak prag je meja stopnje v step()
for (const cm of C.SG_CM_ALLOWED) assert(SG.step(cm) > SG.step(cm - 0.1), 'prag ' + cm + ' cm je meja stopnje snega na strani');

// 3. besedilo
const tx = _text(pt('golte', 17.4, 'Golte', 1400), 15);
assert.match(tx, /Golte \(1400 m\)/); assert.match(tx, /okoli 17 cm/); assert.match(tx, /prag 15 cm/); assert.match(tx, /ne meritev/); assert.match(tx, /ni plazovni bilten/);

// 4. obvestila
const sub = (ep, rules) => ({ endpoint: ep, keys: { p256dh: 'a', auth: 'b' }, rules, st: {} });
const reset = subs => { store[C.SG_PUSH_KEY] = JSON.stringify(subs); sent.length = 0; };
const stored = () => JSON.parse(store[C.SG_PUSH_KEY]);
reset([sub('https://p/a', [{ id: 'golte', cm: 15 }]), sub('https://p/b', [{ id: 'golte', cm: 30 }]), sub('https://p/c', [{ id: 'krvavec', cm: 5 }])]);
await _notify(env, data([pt('golte', 12), pt('krvavec', 2)]), NOW);
assert.equal(sent.length, 0, 'pod pragi ne pošlje');
await _notify(env, data([pt('golte', 17), pt('krvavec', 2)]), NOW + H);
assert.deepEqual(sent.map(x => x.ep), ['https://p/a'], 'golte 17 cm: prag 15 da, prag 30 ne');
assert.equal(sent[0].payload.tag, 'snegofili-golte'); assert.equal(sent[0].payload.url, 'https://meteorec.si/snegofili/');
sent.length = 0;
await _notify(env, data([pt('golte', 20), pt('krvavec', 2)]), NOW + 2 * H);
assert.equal(sent.length, 0, 'ostane nad pragom: ne ponavlja');
await _notify(env, data([pt('golte', 32), pt('krvavec', 2)]), NOW + 3 * H);
assert.deepEqual(sent.map(x => x.ep), ['https://p/b'], 'prag 30 dobi šele ob 32 cm; prag 15 ne znova');
// histereza: pod 50 % praga se ponovno oboroži; v hladilni dobi ne pošlje; po njej pošlje
sent.length = 0;
const a1 = () => stored().find(x => x.endpoint === 'https://p/a').st['golte|15'];
await _notify(env, data([pt('golte', 9), pt('krvavec', 2)]), NOW + 4 * H);
assert.equal(a1().over, true, '9 cm je nad 7,5 (50 % od 15): še ni reset');
await _notify(env, data([pt('golte', 5), pt('krvavec', 2)]), NOW + 5 * H);
assert.equal(a1().over, false, 'pod 7,5 cm se ponastavi');
await _notify(env, data([pt('golte', 18), pt('krvavec', 2)]), NOW + 6 * H);
assert(!sent.some(x => x.ep === 'https://p/a'), 'v hladilni dobi (12 h) ne pošlje');
assert.equal(a1().over, true);
await _notify(env, data([pt('golte', 3), pt('krvavec', 2)]), NOW + 7 * H);
await _notify(env, data([pt('golte', 18), pt('krvavec', 2)]), NOW + 13 * H + 1000);
assert(sent.some(x => x.ep === 'https://p/a'), 'po hladilni dobi pošlje');
// ostane nad pragom tudi po hladilni dobi: brez novega prehoda ne pošlje drugič (pošiljanje je ob PREHODU, ne vsakih 12 h)
reset([sub('https://p/h', [{ id: 'golte', cm: 15 }])]);
await _notify(env, data([pt('golte', 20)]), NOW); assert.equal(sent.length, 1);
sent.length = 0;
await _notify(env, data([pt('golte', 22)]), NOW + 14 * H); assert.equal(sent.length, 0, 'še vedno nad pragom po 14 h: ne ponovi');
// več pravil na napravi: eno obvestilo, ostala omenjena
reset([sub('https://p/m', [{ id: 'golte', cm: 5 }, { id: 'krvavec', cm: 5 }, { id: 'tignes', cm: 15 }])]);
await _notify(env, data([pt('golte', 6), pt('krvavec', 7), pt('tignes', 20)]), NOW);
assert.equal(sent.length, 1, 'eno obvestilo na napravo'); assert.match(sent[0].payload.body, /In še 2 tvoji opozorili\./, 'dvojina pri 2 dodatnih opozorilih');
reset([sub('https://p/m2', [{ id: 'golte', cm: 5 }, { id: 'krvavec', cm: 5 }])]);
await _notify(env, data([pt('golte', 6), pt('krvavec', 7)]), NOW);
assert.match(sent[0].payload.body, /In še 1 tvoje opozorilo\./, 'ednina pri 1 dodatnem opozorilu');
reset([sub('https://p/m', [{ id: 'golte', cm: 5 }, { id: 'krvavec', cm: 5 }, { id: 'tignes', cm: 15 }])]);
await _notify(env, data([pt('golte', 6), pt('krvavec', 7), pt('tignes', 20)]), NOW);
assert.deepEqual(Object.values(stored()[0].st).map(s => s.last > 0), [true, true, true], 'vsa pravila dobijo čas obvestila');
// manjkajoča točka in nepravilna vrednost se preskočita
reset([sub('https://p/x', [{ id: 'izginila', cm: 5 }, { id: 'golte', cm: 5 }])]);
await _notify(env, data([{ id: 'golte', ime: 'Golte', elevation_m: 1400, next24_cm: null }]), NOW);
assert.equal(sent.length, 0, 'next24_cm brez vrednosti ne sproži');
await _notify(env, data([{ id: 'golte', ime: 'Golte', elevation_m: 1400, next24_cm: '20' }]), NOW);
assert.equal(sent.length, 0, 'neštevilska vrednost (niz) ne sproži: model piše števila');
// stari podatki
reset([sub('https://p/s', [{ id: 'golte', cm: 5 }])]);
let r = await _notify(env, data([pt('golte', 50)], NOW - (C.SG_MAX_AGE_H + 1) * H), NOW);
assert.equal(r.skipped, 'snegofili so stari'); assert.equal(sent.length, 0, 'stari podatki ne sprožijo nič');
r = await _notify(env, data([pt('golte', 50)], NOW - (C.SG_MAX_AGE_H - 1) * H), NOW); assert.equal(sent.length, 1, 'še sveži podatki');
// potekla naročnina se odstrani; koda 500 ne blokira
code = 410; reset([sub('https://p/dead', [{ id: 'golte', cm: 5 }])]);
r = await _notify(env, data([pt('golte', 50)]), NOW); assert.equal(r.pruned, 1); assert.equal(stored().length, 0, 'potekla naročnina odstranjena');
code = 201;
// brez VAPID
assert.equal((await _notify({ PHOTOS_R2: r2 }, data([pt('golte', 50)]), NOW)).skipped, 'ni shrambe ali VAPID');
// 5. strežnik: ločen seznam, cron, tiho
assert(src.includes('body.site === "snegofili"'), 'endpoint za site:"snegofili"');
assert(/snegofili: 20/.test(src), 'cron snegofili v CRON_JOBS');
assert(src.includes('_cronBeat(env, "snegofili"'), 'cron snegofili v scheduled()');
assert.deepEqual([C.SG_TIHO_OD, C.SG_TIHO_DO], [22, 7]);
console.log('test_snegofili_alarm: vse v redu');
