#!/usr/bin/env node
// Preizkus ovoja za fetch() proti Open-Meteo arhivu v app.js (predpomnilnik, vrsta po 2, ponovni poskus ob 429,
// proračun localStorage). Iz app.js izreže pravi IIFE in ga požene s ponarejenim fetch/localStorage.
import { readFileSync } from 'fs';
import vm from 'vm';
import assert from 'assert';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'app.js'), 'utf8');
const a = src.indexOf('(function(){\n  const RE=/^https');
const b = src.indexOf('\n})();', a) + 6;
assert(a > 0 && b > a, 'IIFE ni najden v app.js');
const code = src.slice(a, b);

function env() {
  const store = new Map();
  const ls = {
    getItem: k => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)),
    removeItem: k => store.delete(k),
  };
  const calls = []; let active = 0, maxActive = 0; const plan = [];
  const fakeFetch = async (url) => {
    calls.push(url); active++; maxActive = Math.max(maxActive, active);
    await new Promise(r => setTimeout(r, 15));
    active--;
    const p = plan.shift();
    const st = p ? p.status : 200;
    return new Response(p && p.body !== undefined ? p.body : JSON.stringify({ u: url }), { status: st });
  };
  const win = { fetch: fakeFetch, Response };
  const ctx = vm.createContext({ window: win, localStorage: ls, Response, Date, Math, JSON, Object, Promise, setTimeout, String, Number });
  // Object.keys(localStorage) mora vrniti ključe
  ctx.localStorage = new Proxy(ls, { ownKeys: () => [...store.keys()], getOwnPropertyDescriptor: () => ({ enumerable: true, configurable: true }) });
  vm.runInContext(code, ctx);
  return { f: win.fetch, store, calls, plan, maxActive: () => maxActive };
}
const A = 'https://archive-api.open-meteo.com/v1/archive?x=';
let n = 0; const ok = (c, m) => { assert(c, m); n++; };

{ // predpomnilnik + deljenje istega klica
  const e = env();
  const [r1, r2] = await Promise.all([e.f(A + '1'), e.f(A + '1')]);
  ok(e.calls.length === 1, 'dva enaka klica = ena zahteva');
  ok((await r1.json()).u === A + '1' && (await r2.json()).u === A + '1', 'oba dobita telo');
  await e.f(A + '1'); ok(e.calls.length === 1, 'tretji klic iz predpomnilnika');
}
{ // tuji gostitelj in POST gresta mimo
  const e = env();
  await e.f('https://api.open-meteo.com/v1/forecast?a=1'); await e.f('https://api.open-meteo.com/v1/forecast?a=1');
  ok(e.calls.length === 2, 'api.open-meteo.com se ne pomni');
  await e.f(A + '9', { method: 'POST' }); await e.f(A + '9', { method: 'POST' });
  ok(e.calls.length === 4, 'POST se ne pomni');
}
{ // največ 2 vzporedno
  const e = env();
  await Promise.all([1, 2, 3, 4, 5, 6].map(i => e.f(A + i)));
  ok(e.maxActive() === 2, 'vzporedno največ 2, bilo ' + e.maxActive());
}
{ // 429 → en ponovni poskus
  const e = env(); e.plan.push({ status: 429, body: '{}' });
  const r = await e.f(A + 'r');
  ok(e.calls.length === 2 && r.status === 200, '429 ponovljen enkrat');
}
{ // trajna napaka: ni predpomnjena, status ohranjen
  const e = env(); e.plan.push({ status: 500, body: '{}' });
  const r = await e.f(A + 'e'); ok(r.status === 500 && !r.ok, 'status 500 ohranjen');
  const r2 = await e.f(A + 'e'); ok(r2.status === 200 && e.calls.length === 2, 'napaka se ne pomni');
}
{ // proračun 500 kB
  const e = env(); const big = JSON.stringify({ d: 'x'.repeat(140000) });
  for (let i = 0; i < 8; i++) { e.plan.push({ status: 200, body: big }); await e.f(A + 'b' + i); }
  const total = [...e.store.entries()].filter(([k]) => k.startsWith('om-c1:')).reduce((s, [, v]) => s + v.length, 0);
  ok(total <= 500000, 'predpomnilnik v proračunu: ' + total);
  ok(e.store.size >= 2, 'nekaj vnosov ostane');
}
console.log(n + ' preverjanj, 0 napak');
