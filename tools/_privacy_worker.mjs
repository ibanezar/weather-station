/*
 * tools/_privacy_worker.mjs — pomočnik za tools/test_privacy.py.
 *
 * Naloži PRAVI worker.js (z nadomeščenim uvozom cloudflare:workers), nastavi
 * lažen fetch, ki na Ecowitt in Varpolje odgovarja z blokom `indoor` (tudi
 * vgnezdenim), pokliče javne končne točke in izpiše, kaj bi dobil brskalnik.
 * stdout: {"<pot>": {"status": n, "body": "<besedilo>"}, ...}
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'privacy-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);

const INDOOR = { temperature: { value: '23.47', unit: '℃' }, humidity: { value: '47.3', unit: '%' },
  feels_like: { value: '24.11' }, dew_point: { value: '11.23' } };
const real = {
  code: 0, msg: 'success',
  data: {
    outdoor: { temperature: { value: '12.3' }, humidity: { value: '80' }, dew_point: { value: '9.0' }, feels_like: { value: '11' } },
    indoor: INDOOR,
    wind: { wind_speed: { value: '2' }, wind_gust: { value: '4' }, wind_direction: { value: '180' } },
    rainfall: { daily: { value: '0.0' }, rain_rate: { value: '0' } },
    pressure: { relative: { value: '1015' }, absolute: { value: '980' } },
    solar_and_uvi: { solar: { value: '120' }, uvi: { value: '1' } },
  },
};
const varpolje = { ok: true, updated_utc: new Date().toISOString(), indoor: INDOOR,
  current: { temp_c: 11.9, humidity: 82, indoor: INDOOR } };

globalThis.fetch = async (url) => {
  const u = String(url);
  const j = (o) => new Response(JSON.stringify(o), { status: 200, headers: { 'Content-Type': 'application/json' } });
  if (u.includes('api.ecowitt.net')) return j(real);
  if (u.includes('varpolje')) return j(varpolje);
  return new Response('{}', { status: 404 });
};

const mod = await import(pathToFileURL(file).href);
const env = { EW_APP: 'x', EW_API: 'y' };
const ctx = { waitUntil() {}, passThroughOnException() {} };
const out = {};
for (const p of ['/ecowitt-current', '/varpolje-current', '/current']) {
  try {
    const r = await mod.default.fetch(new Request('https://worker.test' + p, { headers: { Origin: 'https://meteorec.si' } }), env, ctx);
    out[p] = { status: r.status, body: await r.text() };
  } catch (e) { out[p] = { status: -1, body: 'IZJEMA ' + e }; }
}
fs.rmSync(dir, { recursive: true, force: true });
process.stdout.write(JSON.stringify(out));
process.exit(0);
