// Kartica za FB objavo kalkulatorja »Gobji valovi« (1080 x 1350) -> og/valovi-fb.jpg.
// Ročno: node tools/render_valovi_fb_card.mjs   (potrebuje Playwright/Chromium)
// Izsek je PRAVA stran (gobarska-napoved/valovi/) s primerom dežja pred 4 dnevi, 35 mm; datumi na sliki so zato
// izračunani na dan izdelave. Slika je primer izračuna, ne napoved.
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.json': 'application/json',
  '.jpg': 'image/jpeg', '.png': 'image/png', '.woff2': 'font/woff2', '.webp': 'image/webp' };
const srv = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(root, p);
  if (!f.startsWith(root) || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
});
await new Promise(r => srv.listen(0, r));
const base = 'http://localhost:' + srv.address().port;

const b = await chromium.launch();
const iso = n => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);
const ctx = await b.newContext({ viewport: { width: 560, height: 900 }, deviceScaleFactor: 3 });
const pg = await ctx.newPage();
await pg.goto(`${base}/gobarska-napoved/valovi/index.html#d=${iso(4)}~35&s=0`);
await pg.waitForSelector('#gvalStatePanel .gp-val-item');
await pg.waitForTimeout(500);
// samo kartice skupin (brez zloženih podrobnosti): skrij mapo vrst
await pg.addStyleTag({ content: '.gp-val-more,.gp-val-sub{display:none!important}.gp-val-item{margin-bottom:.4rem;padding:.5rem .85rem}.gp-val-big{font-size:1.4rem;margin:.15rem 0 0}.gp-val-state{margin:0}' });
const shot = await (await pg.$('#gvalStatePanel')).screenshot({ type: 'png' });
const resultTxt = await pg.textContent('#gvalResult');
await ctx.close();

const logo = fs.readFileSync(path.join(root, 'gobarska-napoved/valovi/logo-valovi.svg'), 'utf8');
const d = new Date(Date.now() - 4 * 864e5);
const MON = ['januarja','februarja','marca','aprila','maja','junija','julija','avgusta','septembra','oktobra','novembra','decembra'];
const primer = `Primer: dež ${d.getUTCDate()}. ${MON[d.getUTCMonth()]}, 35 mm`;
const html = `<!doctype html><meta charset="utf-8"><style>
*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1350px;overflow:hidden;background:#0b1510;color:#eaf3ec;
font-family:Inter,"Helvetica Neue",Arial,sans-serif}
.bg{position:absolute;inset:0;background:radial-gradient(700px 500px at 100% 0%,rgba(76,174,120,.22),transparent 70%),
radial-gradient(600px 500px at 0% 100%,rgba(167,139,250,.12),transparent 70%)}
.w{position:relative;padding:64px 72px;height:100%;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:22px}
.top svg{width:96px;height:96px;border-radius:22px}
.k{font-size:24px;letter-spacing:.16em;text-transform:uppercase;color:#4cae78;font-weight:800}
.n{font-size:46px;font-weight:800;line-height:1.1}.n em{font-style:normal;color:#4cae78}
h1{font-size:88px;line-height:1.02;margin:34px 0 14px;font-weight:800;letter-spacing:-.02em}
h1 span{color:#4cae78}
p.s{font-size:32px;line-height:1.35;margin:0;color:#b8cbbd;max-width:900px}
.frame{margin-top:30px;position:relative;border:2px solid rgba(76,174,120,.4);border-radius:30px;background:#101e16;padding:62px 26px 0;
height:600px;overflow:hidden}
.frame img{width:100%;display:block;border-radius:14px}
.frame:after{content:"";position:absolute;left:0;right:0;bottom:0;height:120px;background:linear-gradient(transparent,#101e16)}
.tag{position:absolute;top:-1px;left:26px;background:#27834d;color:#fff;font-weight:800;font-size:24px;padding:10px 22px;border-radius:0 0 14px 14px;z-index:2}
.cta{margin-top:40px;display:flex;align-items:center;justify-content:space-between;gap:24px}
.btn{background:#27834d;color:#fff;font-weight:800;font-size:36px;padding:26px 40px;border-radius:22px;white-space:nowrap}
.url{font-size:26px;color:#9fb3a6;text-align:right;line-height:1.3}
.url b{color:#eaf3ec}
.fine{margin-top:auto;padding-top:18px;font-size:21px;color:#7f9486;line-height:1.4}
</style><div class="bg"></div><div class="w">
<div class="top">${logo}<div><div class="k">MeteoGobar · Rečica ob Savinji</div><div class="n">Gobji <em>valovi</em></div></div></div>
<h1>Dež je padel.<br><span>Kdaj v gozd?</span></h1>
<p class="s">Vsaka skupina gob se po dežju odzove po svoje. Kalkulator pokaže, kdaj se začne in konča okno rasti.</p>
<div class="frame"><div class="tag">${primer}</div><img src="data:image/png;base64,${shot.toString('base64')}"></div>
<div class="cta"><div class="btn">Preračunajte dež →</div><div class="url">Kalkulator rasti gob<br><b>meteorec.si</b></div></div>
<div class="fine">Primer izračuna na dan izdelave kartice. Ujemanje pravil ni verjetnost najdbe, okna so modelski razpon.</div>
</div>`;
const pg2 = await (await b.newContext({ viewport: { width: 1080, height: 1350 } })).newPage();
await pg2.setContent(html, { waitUntil: 'load' });
await pg2.screenshot({ path: path.join(root, 'og/valovi-fb.jpg'), type: 'jpeg', quality: 92 });
await b.close(); srv.close();
console.log('ok', resultTxt.slice(0, 80));
