/*
 * tools/_cron_beat_test.mjs — pomočnik za tools/test_freshness.py.
 * Požene PRAVA _cronBeat() in _cronHealth() iz worker.js nad lažnim KV in izpiše rezultate (JSON).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
const start = src.indexOf('const CRON_JOBS = {');
const end = src.indexOf('// ── ARSO 24-urne padavine: posnetek zjutraj');
if (start < 0 || end < start) throw new Error('blok _cronBeat v worker.js ni najden');

const ctx = vm.createContext({ Date, JSON, Math, Object, Promise, String, Number });
vm.runInContext(`
var _store = {}, _puts = 0;
var env = { COUNTER_KV: {
  get: async function (k) { return _store[k] === undefined ? null : _store[k]; },
  put: async function (k, v) { _puts++; _store[k] = v; } } };
${src.slice(start, end)}
globalThis.__run = (async function () {
  var out = {};
  out.r1 = await _cronBeat(env, 'thresholds', async () => 1);
  out.r2 = await _cronBeat(env, 'dispatch', async () => ({ ok: false, reason: 'manjka GH_DISPATCH_TOKEN' }));
  out.r3 = await _cronBeat(env, 'aurora', async () => { throw new Error('boom'); });
  out.r4 = await _cronBeat(env, 'lightning', async () => false);
  var p0 = _puts;
  await _cronBeat(env, 'thresholds', async () => 1);   // enako stanje, < 15 min: brez novega zapisa
  out.rewrite = _puts - p0;
  out.health = await _cronHealth(env);
  // opravilo brez zapisa, a znotraj roka od prvega zapisa: čaka, ni zastarelo
  out.waiting = out.health.jobs.score_napovej;
  out.since_set = _store['cron:health:_since'] !== undefined;
  _store['cron:health:_since'] = String(Date.now() - 31 * 3600000);   // prvi zapis je star > 30 h
  out.long_missing = (await _cronHealth(env)).jobs.score_napovej;
  return out;
})();`, ctx);
process.stdout.write(JSON.stringify(await ctx.__run));
