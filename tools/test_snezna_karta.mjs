/*
 * tools/test_snezna_karta.mjs — snežna karta (zima/snezna-karta/karta.js) v pravem brskalniku na SINTETIČNEM odgovoru
 * /sneg-karta.json. Poleti je ni mogel preizkusiti noben pravi sneg, zato se tu preveri:
 *   - karta se nariše (barvni piksli) v vseh treh prikazih in ob vseh kontrolah, brez napak v konzoli,
 *   - dan brez sneženja pove, da sneženja ni; manjkajoči podatek (ICON-D2 sega 48 h od svojega teka) NE sme reči »ni sneženja«,
 *   - nedosegljiv vir pove, da karta ni dosegljiva.
 * Zahteva Playwright (PW=$(npm root -g)/playwright). Zaženi: PW=... node tools/test_snezna_karta.mjs
 */
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW || 'playwright');
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' };
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(ROOT, p);
  if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); res.end(fs.readFileSync(f));
}).listen(0);
const port = server.address().port;

const NX = 35, NY = 16, HOURS = 48;
function data({ snow, nullFrom = HOURS }) {
  const t0 = Math.floor(Date.now() / 3600000) * 3600000;
  const n = NX * NY;
  const sn = [], ln = [];
  for (let k = 0; k < HOURS; k++) {
    const a = new Array(n), b = new Array(n);
    for (let i = 0; i < n; i++) {
      const y = Math.floor(i / NX), x = i % NX;
      if (k >= nullFrom) { a[i] = null; b[i] = null; continue; }
      // sneg v ur 6-30 po hribovitem severu in zahodu; meja sneženja pade s 2000 na 400 m
      a[i] = snow && k >= 6 && k <= 30 ? Math.round(Math.max(0, (y / NY) * 14 - 3 + (x < 12 ? 5 : 0))) : 0;
      b[i] = Math.round((2000 - Math.min(k, 24) * 66) / 10);
    }
    sn.push(a); ln.push(b);
  }
  const z = Array.from({ length: n }, (_, i) => 300 + (i % NX) * 25);
  return { generated: Date.now(), t0, hours: HOURS, lat0: 45.4, lon0: 13.3, d: 0.1, nx: NX, ny: NY, model: 'ICON-D2', units: { sn: 0.1, ln: 10 }, z, sn, ln };
}

let fails = 0;
const check = (c, m) => { if (!c) { fails++; console.error('✗ ' + m); } else console.log('✓ ' + m); };
const b = await chromium.launch();

async function open(payload, mode = 'ok') {
  const ctx = await b.newContext({ viewport: { width: 390, height: 900 }, isMobile: true, hasTouch: true });
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', e => errors.push(String(e)));
  p.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });
  await p.route('**/*', r => {
    const u = r.request().url();
    if (u.includes('/sneg-karta.json')) {
      return mode === 'down' ? r.fulfill({ status: 503, body: 'x' }) : r.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify(payload) });
    }
    return u.startsWith('http://localhost') ? r.continue() : r.abort();
  });
  await p.goto(`http://localhost:${port}/zima/snezna-karta/`, { waitUntil: 'load' });
  await p.waitForTimeout(700);
  return { p, ctx, errors };
}
const painted = p => p.evaluate(() => { const cv = document.getElementById('sk-cv'); if (!cv) return -1; const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 100) n++; return n; });
const empty = p => p.evaluate(() => { const e = document.getElementById('sk-empty'); return e && !e.hidden ? e.textContent : null; });

// 1) navaden snežni scenarij
{
  const { p, ctx, errors } = await open(data({ snow: true }));
  check(await p.$('#sk-cv') !== null, 'karta se zgradi');
  await p.click('button[data-v="h"]'); await p.click('#sk-slider'); await p.fill('#sk-slider', '12'); await p.dispatchEvent('#sk-slider', 'input');
  check(await painted(p) > 2000, 'sneženje po urah ob uri 13: karta je pobarvana');
  await p.click('button[data-v="s"]'); await p.click('button[data-h="24"]');
  check(await painted(p) > 2000, 'skupno do +24 h: karta je pobarvana');
  check(await empty(p) === null, 'sneg je napovedan: opozorilo o praznem polju je skrito');
  await p.click('button[data-v="l"]'); await p.click('button[data-h="6"]');
  check(await painted(p) > 2000, 'meja sneženja: karta je pobarvana');
  await p.click('#sk-cv', { position: { x: 100, y: 60 } });
  const read = await p.textContent('#sk-read');
  check(/meja sneženja/.test(read) && !/NaN|undefined/.test(read), 'dotik karte izpiše vrednosti brez NaN (' + read.slice(0, 60) + '…)');
  await p.click('#sk-days button:nth-child(2)'); await p.click('#sk-next'); await p.click('#sk-prev'); await p.click('#sk-now');
  check(errors.length === 0, 'brez napak v konzoli ' + JSON.stringify(errors));
  await ctx.close();
}
// 2) dan brez sneženja
{
  const { p, ctx } = await open(data({ snow: false }));
  await p.click('button[data-v="s"]'); await p.click('button[data-h="24"]');
  const msg = await empty(p);
  check(msg && /ne napoveduje sneženja/.test(msg) && /sneženja ni/.test(msg), 'brez snega: karta to pove (' + msg + ')');
  await ctx.close();
}
// 3) ICON-D2 zadnjih ur nima podatkov: to NI »ni sneženja«
{
  const { p, ctx } = await open(data({ snow: true, nullFrom: 44 }));
  await p.click('button[data-v="h"]'); await p.click('button[data-h="48"]');
  const msg = await empty(p);
  check(msg && !/ne napoveduje sneženja/.test(msg) && /podatk/i.test(msg), 'ura brez podatkov ne trdi »ni sneženja« (' + msg + ')');
  await ctx.close();
}
// 4) vir ne odgovarja
{
  const { p, ctx } = await open(null, 'down');
  const t = await p.textContent('#sk-app');
  check(/ni dosegljiva/.test(t), 'nedosegljiv vir: pove, da karta ni dosegljiva');
  await ctx.close();
}
await b.close(); server.close();
process.exit(fails ? 1 : 0);
