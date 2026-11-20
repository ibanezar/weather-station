/*
 * tools/test_windy_thumb.mjs — preizkus GET /windy-thumb na PRAVEM worker.js (lažen fetch proti Windy API in seznamu točk).
 * Poganjanje: node tools/test_windy_thumb.mjs
 * Preveri: id je število, brez ključa ni klica, samo kamere s seznama točk, ključ gre samo v glavo Windy klica, rezultat se
 * 8 min drži v pomnilniku (en klic Windyju na kamero), napake se ne izmislijo kot slika, slike samo z Windyjevih domen.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let src = fs.readFileSync(path.join(ROOT, 'worker.js'), 'utf8');
src = src.replace('import { DurableObject } from "cloudflare:workers";',
  'class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'windy-'));
const file = path.join(dir, 'worker.mjs');
fs.writeFileSync(file, src);
const mod = await import(pathToFileURL(file).href);

const ctx = { waitUntil() {}, passThroughOnException() {} };
let fails = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };

const KEY = 'TEST-KEY-123';
const tocke = { tocke: [
  { id: 'a', kamere: [{ embed: 'https://webcams.windy.com/webcams/public/embed/player/1111/day' }] },
  { id: 'b', kamere: [{ embed: 'https://webcams.windy.com/webcams/public/embed/player/2222/day' },
                      { embed: 'https://webcams.windy.com/webcams/public/embed/player/3333/day' }] },
  { id: 'c', kamere: [{ embed: 'https://evil.example/webcams/public/embed/player/4444/day' }] },
  { id: 'd', kamere: [] },
] };
const svet = { tocke: [{ id: 'niseko', kamere: [{ embed: 'https://webcams.windy.com/webcams/public/embed/player/7777/day' }] }] };
const apiCalls = []; let listOk = true, svetOk = true;
const answers = {
  '1111': { images: { current: { icon: 'https://images-webcams.windy.com/1/i.jpg', thumbnail: 'https://images-webcams.windy.com/1/t.jpg?token=x', preview: 'https://images-webcams.windy.com/1/p.jpg?token=x' } } },
  '2222': { images: { current: { preview: 'https://evil.example/p.jpg', thumbnail: 'http://images-webcams.windy.com/t.jpg' } } },
  '7777': { images: { current: { preview: 'https://images-webcams.windy.com/7/p.jpg?token=z' } } },
  '3333': { images: { current: { thumbnail: 'https://images-webcams.windy.com/3/t.jpg?token=y' } } },
};
globalThis.fetch = async (u, init = {}) => {
  const s = String(u);
  if (s.startsWith('https://meteorec.si/data/snegofili-tocke.json')) return listOk ? new Response(JSON.stringify(tocke), { status: 200 }) : new Response('x', { status: 500 });
  if (s.startsWith('https://meteorec.si/data/snegofili-svet-tocke.json')) return svetOk ? new Response(JSON.stringify(svet), { status: 200 }) : new Response('x', { status: 500 });
  const m = /^https:\/\/api\.windy\.com\/webcams\/api\/v3\/webcams\/(\d+)\?/.exec(s);
  if (m) {
    apiCalls.push({ id: m[1], key: (init.headers || {})['x-windy-api-key'], url: s });
    if (m[1] === '3333' && apiCalls.filter(c => c.id === '3333').length === 1 && globalThis.__fail3333) return new Response('no', { status: 401 });
    return new Response(JSON.stringify(answers[m[1]] || {}), { status: answers[m[1]] ? 200 : 404 });
  }
  throw new Error('nepričakovan klic: ' + s);
};

const call = (p, env) => mod.default.fetch(new Request('https://w.test' + p, { headers: { Origin: 'https://meteorec.si', 'CF-Connecting-IP': '1.2.3.4' } }), env, ctx);
const withKey = { WINDY_API_KEY: KEY };

let r = await call('/windy-thumb?id=abc', withKey);
check(r.status === 400, 'id, ki ni število, je zavrnjen (400)');
r = await call('/windy-thumb?id=1111', {});
let b = await r.json();
check(b.error === 'no_key' && apiCalls.length === 0, 'brez ključa: error no_key in nobenega klica');
r = await call('/windy-thumb?id=9999', withKey);
check(r.status === 404 && apiCalls.length === 0, 'kamera, ki ni na seznamu točk, je zavrnjena brez klica Windyju');
r = await call('/windy-thumb?id=4444', withKey);
check(r.status === 404, 'vdelava z napačne domene ne šteje za dovoljeno kamero');

r = await call('/windy-thumb?id=1111', withKey); b = await r.json();
check(r.status === 200 && b.preview === 'https://images-webcams.windy.com/1/p.jpg?token=x' && b.thumbnail.endsWith('t.jpg?token=x'), 'veljavna kamera vrne preview in thumbnail');
check(apiCalls.length === 1 && apiCalls[0].key === KEY && !apiCalls[0].url.includes(KEY), 'ključ gre samo v glavo, ne v naslov');
check(!JSON.stringify(b).includes(KEY), 'ključ ni v odgovoru odjemalcu');
r = await call('/windy-thumb?id=1111', withKey); await r.json();
check(apiCalls.length === 1, 'drugi klic znotraj 8 min ne gre na Windy (pomnilnik izolata)');

r = await call('/windy-thumb?id=7777', withKey); b = await r.json();
check(r.status === 200 && b.preview === 'https://images-webcams.windy.com/7/p.jpg?token=z', 'kamera iz seznama »Po svetu« je dovoljena');

r = await call('/windy-thumb?id=2222', withKey); b = await r.json();
check(b.error === 'no_image' && !b.preview, 'slika z druge domene in ne-https se zavrneta (no_image)');

globalThis.__fail3333 = true;
r = await call('/windy-thumb?id=3333', withKey); b = await r.json();
check(b.error === 'windy_401' && !b.preview, 'napaka Windyja: error, nikoli izmišljena slika');
r = await call('/windy-thumb?id=3333', withKey); await r.json();
check(apiCalls.filter(c => c.id === '3333').length === 1, 'napaka se kratek čas pomni (brez klica ob vsakem zahtevku)');

check(r.headers.get('Access-Control-Allow-Origin') !== null, 'CORS glava je prisotna');

if (fails) { console.error(fails + ' napak'); process.exit(1); }
console.log('test_windy_thumb: vse v redu');
