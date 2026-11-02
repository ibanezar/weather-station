/*
 * tools/test_hourly_fallback.mjs — /hourly v PRAVEM worker.js (lažen WU in Ecowitt):
 *   - WU vrne 401 (2. 11. 2026) → odgovor je zgrajen iz Ecowitt device/history v WU obliki,
 *     da grafi »Urni temperaturni profil«, »Temperatura« in »Padavine« ne obstanejo v »Nalaganje…«;
 *   - svež WU odgovor gre naprej nespremenjen (brez klica Ecowitta);
 *   - zastarel WU (zadnji zapis > 3 h) → Ecowitt;
 *   - oba odpovesta → status WU (odjemalec pokaže »ni mogoče naložiti«), ne izmišljeni podatki;
 *   - Ecowitt ne dobi notranjih kanalov (pravilo z vrha CLAUDE.md).
 * Poganjanje: node tools/test_hourly_fallback.mjs
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hourly-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);

const LJ = d => d.toLocaleString('sv-SE', { timeZone: 'Europe/Ljubljana' });
const now = Date.now();
const step = 30 * 60 * 1000;
const t0 = Math.floor(now / step) * step;

function ecowittBody() {
  const T = {}, H = {}, W = {}, G = {}, R = {}, WD = {};
  for (let i = 60; i >= 0; i--) {                       // 30 h nazaj
    const ms = t0 - i * step, ts = String(ms / 1000), loc = LJ(new Date(ms));
    const hh = parseInt(loc.slice(11, 13), 10);
    T[ts] = String(5 + hh / 4); H[ts] = '80'; W[ts] = '3.2'; G[ts] = '7.5'; WD[ts] = '350';
    // kumulativa od polnoči: 0,1 mm na vsako polovico ure od 00:00
    R[ts] = String((hh * 2 + (loc.slice(14, 16) === '30' ? 1 : 0)) * 0.1);
  }
  const list = o => ({ unit: 'x', list: o });
  return {
    code: 0, msg: 'success',
    data: {
      outdoor: { temperature: list(T), humidity: list(H), dew_point: list(T) },
      wind: { wind_speed: list(W), wind_gust: list(G), wind_direction: list(WD) },
      rainfall: { daily: list(R), rain_rate: list(R) },
      pressure: { relative: list(Object.fromEntries(Object.keys(T).map(k => [k, '1015']))) },
      solar_and_uvi: { solar: list(Object.fromEntries(Object.keys(T).map(k => [k, '120']))), uvi: list(Object.fromEntries(Object.keys(T).map(k => [k, '0.4']))) },
    },
  };
}

let wuMode = '401', ecCalls = 0, wuCalls = 0, ecUrl = '', ecFails = false;
globalThis.fetch = async (url) => {
  const u = String(url);
  if (u.includes('api.weather.com')) {
    wuCalls++;
    if (wuMode === '401') return new Response('{"errors":[{"error":{"code":"CDN-0001"}}]}', { status: 401 });
    const iso = wuMode === 'stale' ? new Date(now - 5 * 3600e3).toISOString() : new Date(now - 10 * 60e3).toISOString();
    return new Response(JSON.stringify({ observations: [{ obsTimeUtc: iso, obsTimeLocal: '2026-01-01 00:59:00', metric: { tempAvg: 1 } }] }), { status: 200 });
  }
  if (u.includes('api.ecowitt.net')) {
    ecCalls++; ecUrl = u;
    if (ecFails) return new Response('{"code":-1,"msg":"boom"}', { status: 200 });
    return new Response(JSON.stringify(ecowittBody()), { status: 200 });
  }
  return new Response('{}', { status: 200 });
};
const mod = await import(pathToFileURL(file).href);
const env = { EW_APP: 'a', EW_API: 'b' };
const call = () => mod.default.fetch(new Request('https://x.test/hourly', { headers: { Origin: 'https://meteorec.si' } }), env, { waitUntil() {} });
const reset = () => { ecCalls = 0; wuCalls = 0; ecUrl = ''; };

// 1) WU 401 → Ecowitt
reset(); wuMode = '401';
let res = await call(); let j = await res.json();
assert.equal(res.status, 200, 'rezerva mora vrniti 200');
assert.ok(ecCalls === 1, 'Ecowitt mora biti poklican enkrat');
const obs = j.observations;
assert.ok(obs.length >= 28 && obs.length <= 32, 'približno 30 urnih zapisov, dobil ' + obs.length);
const keys = obs.map(o => o.obsTimeLocal);
assert.deepEqual(keys, [...keys].sort(), 'zapisi morajo biti urejeni po času');
assert.ok(keys.every(k => /^\d{4}-\d\d-\d\d \d\d:59:00$/.test(k)), 'oblika obsTimeLocal kot pri WU (HH:59:00)');
assert.equal(new Set(keys).size, keys.length, 'brez podvojenih ur');
assert.ok(obs.every(o => typeof o.metric.tempAvg === 'number' && o.metric.tempHigh >= o.metric.tempLow), 'temperature');
assert.ok(obs.every(o => o.winddirAvg === 350), 'smer vetra (krožno povprečje)');
assert.ok(obs.every(o => o.metric.windspeedAvg === 3.2 && o.metric.windgustHigh === 7.5), 'veter');
assert.ok(obs.every(o => o.metric.pressureMax === 1015), 'tlak');
// kumulativa od polnoči: ob 0:59 je 0,2 mm (0:00 + 0:30), nato raste; prvi zapis naslednjega dne spet pade
const h0 = obs.find(o => o.obsTimeLocal.slice(11, 13) === '00');
if (h0) assert.ok(Math.abs(h0.metric.precipTotal - 0.1) < 1e-9, 'precipTotal ob 00:59 = kumulativa na koncu ure, dobil ' + h0.metric.precipTotal);
for (let i = 1; i < obs.length; i++) {
  const same = obs[i].obsTimeLocal.slice(0, 10) === obs[i - 1].obsTimeLocal.slice(0, 10);
  if (same) assert.ok(obs[i].metric.precipTotal >= obs[i - 1].metric.precipTotal, 'kumulativa ne sme pasti znotraj dneva');
}
// app.js: priraštek dežja po urah ne sme biti negativen ali velik (Math.max(0, …) ga varuje, a tu preverimo vhod)
// 2) zasebnost: nobenih notranjih kanalov v zahtevi in odgovoru
assert.ok(!/indoor/i.test(ecUrl), 'Ecowitt zahteva ne sme omenjati indoor');
assert.ok(!/indoor|tempinf/i.test(JSON.stringify(j)), 'odgovor ne sme vsebovati notranjih meritev');
assert.ok(/cycle_type=30min/.test(ecUrl), 'zgodovina 7 dni gre v 30-min koraku');

// 3) svež WU → nespremenjen, brez Ecowitta
reset(); wuMode = 'ok';
res = await call(); j = await res.json();
assert.equal(res.status, 200); assert.equal(ecCalls, 0, 'svež WU ne sme klicati Ecowitta');
assert.equal(j.observations[0].obsTimeLocal, '2026-01-01 00:59:00');

// 4) zastarel WU → Ecowitt
reset(); wuMode = 'stale';
res = await call(); j = await res.json();
assert.equal(ecCalls, 1); assert.ok(j.observations.length > 20, 'zastarel WU mora preklopiti na Ecowitt');

// 5) WU 401 in Ecowitt odpove → WU status (ne izmišljen odgovor)
reset(); wuMode = '401'; ecFails = true;
res = await call();
assert.equal(res.status, 401, 'ob odpovedi obeh virov odjemalec dobi napako, ne praznega uspeha');

console.log('OK  test_hourly_fallback: 5 scenarijev');
