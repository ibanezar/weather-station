/*
 * tools/check_snow_card.mjs — kartica »Sneg v dolini — MTR« (app.js renderSnowCard, toggleSnowDetail) v pravem brskalniku na
 * SINTETIČNEM napoved-snega.json (poleti so vsi dnevi < 5 %, zato se višje stopnje ne vidijo). Preveri:
 *   - klik, Enter in presledek odprejo ploščo #snow-detail, drugi dan jo preklopi, ponovni klik, ✕ in Esc jo zaprejo (fokus se vrne),
 *   - plošča ima vse štiri postaje v dolini in višino samo, kjer jo JSON ima (station_meta),
 *   - strani ne razširi vodoravno (na 320, 390 in 1280 px),
 *   - zaprta kartica pri vseh izmerjenih širinah ni nižja od naravne višine (rezervacija min-height v style.css, brez CLS).
 * Zahteva Playwright (PW=$(npm root -g)/playwright). Zaženi: PW=... node tools/check_snow_card.mjs   (PRINT=1 izpiše naravne višine, WIDTHS=320,390,... preglasi seznam širin)
 * Ob spremembi besedila kartice ali njenih ploščic se višine spremenijo: znova izmeri (izpis »MANJ«) in popravi stopnje `.snow-card{min-height}`.
 */
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW || 'playwright');
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.png': 'image/png', '.webp': 'image/webp' };
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(ROOT, p);
  if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); res.end(fs.readFileSync(f));
}).listen(0);
const port = server.address().port;

const mk = (i, p, t, mm, ps) => ({
  date: new Date(Date.now() + i * 864e5).toISOString().slice(0, 10), lead: i, p_snow: p, p_proxy: Math.min(.95, p * 1.8), basis: 'observed',
  stations: { 'Gornji Grad': p, 'Luče': ps[0], 'Radegunda': ps[1], 'Solčava': ps[2] }, tavg: t, prec_mm: mm, n_models: 4,
});
const sample = () => ({
  generated_at: new Date().toISOString(), model_version: '0.4', in_season: true, main_station: 'Gornji Grad',
  station_meta: { 'Gornji Grad': { alt_m: 428 }, 'Luče': { alt_m: null }, 'Radegunda': { alt_m: 794 }, 'Solčava': { alt_m: null } },
  days: [mk(1, .02, 9.5, .4, [.04, .08, .05]), mk(2, .12, 2.8, 3.1, [.2, .38, .22]), mk(3, .433, -0.6, 6.2, [.5, .7, .52]),
         mk(4, .28, 0.4, 4.5, [.34, .52, .36]), mk(5, .007, 7.0, 0, [.01, .03, .02])],
});

let fails = 0;
const ok = (name, cond, extra = '') => { console.log((cond ? '  ✓ ' : '  ✗ ') + name + (cond ? '' : ' ' + extra)); if (!cond) fails++; };
const browser = await chromium.launch();
async function open(w, h) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  await page.route(/open-meteo|arso|workers\.dev|meteorec\.si\/(?!napoved-snega)/, r => r.abort());
  await page.route(/napoved-snega\.json/, r => r.fulfill({ contentType: 'application/json', body: JSON.stringify(sample()) }));
  await page.addInitScript(() => { try { localStorage.setItem('wx-mode', 'advanced'); localStorage.setItem('wx-more-open', '1'); } catch (e) {} });
  await page.goto(`http://localhost:${port}/index.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#snow-days .snow-day', { timeout: 20000 });
  await page.waitForTimeout(500);
  return { ctx, page };
}
const isOpen = page => page.evaluate(() => document.getElementById('snow-detail').classList.contains('open'));

console.log('plošča s podrobnostmi');
for (const w of [1280, 390, 320]) {
  const { ctx, page } = await open(w, 900);
  await page.click('#snow-days .snow-day:nth-child(3)');
  const o = await page.evaluate(() => {
    const d = document.getElementById('snow-detail'), t = document.querySelector('#snow-days .snow-day.active');
    return { rows: [...d.querySelectorAll('.snow-st-row')].map(r => r.textContent.replace(/\s+/g, ' ').trim()), expanded: t && t.getAttribute('aria-expanded'),
      pct: d.querySelector('.snow-d-pct').textContent.trim(), title: d.querySelector('.snow-detail-title').textContent, overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth };
  });
  ok(`${w}px: klik odpre ploščo za izbrani dan`, await isOpen(page) && o.expanded === 'true' && /3 dni vnaprej/.test(o.title), JSON.stringify(o));
  ok(`${w}px: štiri postaje, višina samo pri Gornjem Gradu in Radegundi`, o.rows.length === 4 && /428/.test(o.rows[0]) && /794/.test(o.rows[2]) && !/ m/.test(o.rows[1] + o.rows[3]), JSON.stringify(o.rows));
  ok(`${w}px: stran se ne razširi vodoravno`, !o.overflow);
  if (w === 1280) {
    await page.click('#snow-days .snow-day:nth-child(2)');
    ok('preklop na drug dan', await isOpen(page) && /2 dneva vnaprej/.test(await page.textContent('.snow-detail-title')));
    await page.click('#snow-days .snow-day:nth-child(2)');
    ok('ponovni klik zapre', !(await isOpen(page)));
    await page.focus('#snow-days .snow-day:nth-child(4)'); await page.keyboard.press('Enter');
    ok('Enter odpre', await isOpen(page));
    await page.keyboard.press('Escape');
    ok('Esc zapre in vrne fokus na ploščico', !(await isOpen(page)) && await page.evaluate(() => document.activeElement && document.activeElement.classList.contains('snow-day')));
    await page.focus('#snow-days .snow-day:nth-child(1)'); await page.keyboard.press(' ');
    ok('presledek odpre', await isOpen(page));
    await page.click('[data-snow-close]');
    ok('✕ zapre', !(await isOpen(page)) && await page.evaluate(() => document.querySelectorAll('#snow-days .snow-day.active').length === 0));
  }
  await ctx.close();
}

console.log('rezervirana višina zaprte kartice');
const widths = process.env.WIDTHS ? process.env.WIDTHS.split(',').map(Number) : [1600, 1280, 1100, 1030, 1010, 1000, 900, 760, 720, 714, 712, 700, 640, 605, 600, 598, 590, 570, 560, 545, 540, 530, 520, 500, 460, 445, 440, 435, 430, 400, 392, 390, 381, 380, 375, 360, 350, 349, 345, 340, 330, 327, 325, 320];
const short = [];
for (const w of widths) {
  const { ctx, page } = await open(w, 900);
  const r = await page.evaluate(() => { const c = document.getElementById('snow-card'), m = c.style.minHeight; c.style.minHeight = '0'; const nat = c.getBoundingClientRect().height; c.style.minHeight = m; return { nat, min: parseFloat(getComputedStyle(c).minHeight) }; });
  if (process.env.PRINT) console.log(w, (r.nat / 16).toFixed(2) + 'rem'); if (r.min + 0.5 < r.nat) short.push(`${w}px: naravno ${Math.round(r.nat)} > rezervirano ${Math.round(r.min)}`);
  await ctx.close();
}
ok(`min-height pokriva naravno višino pri vseh ${widths.length} širinah`, short.length === 0, 'MANJ: ' + short.join('; '));

await browser.close(); server.close();
console.log(fails ? `\n${fails} NAPAK` : '\nVSE V REDU');
process.exit(fails ? 1 : 0);
