// Kartice za FB objavo kalkulatorja »Gobji valovi« (1080 x 1350, 4:5) v štirih slogih -> og/valovi-fb-*.jpg
//   1 foto      okrogla fotografija jurčka z loki skupin, velik naslov
//   2 casovnica prave številke iz kalkulatorja: dež in tri okna rasti na osi dni
//   3 poster    svetla, jesenska, velike številke »2–8 dni« (brez datumov, zato je kartica trajna)
//   4 telefon   pravi posnetek strani v telefonu
// Ročno: node tools/render_valovi_fb_cards.mjs [foto|casovnica|poster|telefon]   (potrebuje Playwright/Chromium)
// Številke (okna, zamiki) se preberejo iz PRAVE strani gobarska-napoved/valovi/ s primerom dežja pred 4 dnevi, 35 mm;
// datumi na slikah so zato izračunani na dan izdelave. Slika je primer izračuna, ne napoved.
// Foto: Wikimedia Commons, licence in avtorji so v gobarska-napoved/img/vrste/CREDITS.json in v vrstici na sliki.
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const only = process.argv[2] || null;
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

const DAY = 864e5;
const today = new Date(); today.setUTCHours(0, 0, 0, 0);
const iso = n => new Date(Date.now() - n * DAY).toISOString().slice(0, 10);
const MON = ['januarja','februarja','marca','aprila','maja','junija','julija','avgusta','septembra','oktobra','novembra','decembra'];
const RAIN_DAYS_AGO = 4, RAIN_MM = 35;
const rainDate = new Date(Date.now() - RAIN_DAYS_AGO * DAY);
const primer = `Primer: dež ${rainDate.getUTCDate()}. ${MON[rainDate.getUTCMonth()]}, ${RAIN_MM} mm`;

// ── 1. podatki iz prave strani ─────────────────────────────────────────────
const PHOTO = { 'Razkrojevalke stelje': 'macrolepiota_procera', 'Lesne vrste': 'laetiporus_sulphureus', 'Mikorizne vrste': 'boletus_edulis' };
const credits = JSON.parse(fs.readFileSync(path.join(root, 'gobarska-napoved/img/vrste/CREDITS.json'), 'utf8'));
const b64 = f => fs.readFileSync(f).toString('base64');
const photoUri = id => 'data:image/jpeg;base64,' + b64(path.join(root, 'gobarska-napoved/img/vrste', id + '.jpg'));
const credit = id => { const c = credits[id + '.jpg'] || {}; return `${c.artist} (${c.license})`; };

const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3 });
const pg = await ctx.newPage();
// brez omrežja: temperatura/vlaga se na karticah ne uporabljata, napoved dežja je izklopljena (f=0)
await pg.route('https://api.open-meteo.com/**', r => r.abort());
await pg.goto(`${base}/gobarska-napoved/valovi/index.html#d=${iso(RAIN_DAYS_AGO)}~${RAIN_MM}&s=0&f=0`);
await pg.waitForSelector('#gvalStatePanel .gp-val-item');
await pg.waitForTimeout(600);
const groups = await pg.evaluate(() => [...document.querySelectorAll('#gvalStatePanel .gp-val-item')].map(it => {
  const lab = [...it.querySelectorAll('.gp-pv-prl span')].map(s => s.textContent.trim());
  const lag = (it.textContent.match(/Modelski zamik:\s*(\d+)\D+(\d+)\s*dni/) || []);
  return { name: it.querySelector('.gp-val-title').textContent.trim(), color: it.querySelector('.gp-val-big').style.color,
    range: it.querySelector('.gp-val-big').textContent.trim(), status: it.querySelector('.gp-val-status').textContent.trim(),
    start: lab[0] || '', end: lab[1] || '', lagMin: +lag[1], lagMax: +lag[2] };
}));
if (groups.length !== 3 || groups.some(g => !g.lagMin || !PHOTO[g.name])) throw new Error('Kalkulator ne vrne treh skupin: ' + JSON.stringify(groups));
// »začetek 12. 10.« -> odmik v dneh od dne dežja
const off = s => { const m = s.match(/(\d+)\.\s*(\d+)\./); const d = new Date(Date.UTC(today.getUTCFullYear(), +m[2] - 1, +m[1]));
  return Math.round((d - Date.UTC(rainDate.getUTCFullYear(), rainDate.getUTCMonth(), rainDate.getUTCDate())) / DAY); };
for (const g of groups) { g.s0 = off(g.start); g.e0 = off(g.end); g.id = PHOTO[g.name]; g.short = { 'Razkrojevalke stelje': 'Stelja', 'Lesne vrste': 'Les', 'Mikorizne vrste': 'Mikorizne' }[g.name]; }

// posnetek strani za telefon (zaslon 442 x 989 px = 390 x 872 enot strani): zgornji del (logotip) + rezultat z kartico skupine, zloženo v en zaslon
// (fullPage + clip: pri premiku okna se v headless sticky vrstice pokvarijo)
// logotip na zaslonu telefona je manjši od logotipa na kartici (samo v posnetku, prava stran se ne spremeni)
await pg.addStyleTag({ content: '.gp-pv-hero{padding:.7rem .8rem!important;gap:.7rem!important}.gp-pv-hero img{width:2.5rem!important;height:2.5rem!important;border-radius:.7rem!important}.gp-pv-n{font-size:1.3rem!important}.gp-pv-s{font-size:.78rem!important}.gp-pv-k{font-size:.58rem!important}' });
await pg.waitForTimeout(200);
const HERO_Y = 58, HERO_H = 255, NOTCH = 38;  // zgornja vrstica strani (HERO_Y) ostane zunaj, pod »otokom« telefona je prostor (NOTCH)
const topY = await pg.evaluate(() => document.querySelector('#gvalResult').getBoundingClientRect().top + scrollY - 70);
const heroShot = await pg.screenshot({ type: 'png', fullPage: true, clip: { x: 0, y: HERO_Y, width: 390, height: HERO_H } });
const resShot = await pg.screenshot({ type: 'png', fullPage: true, clip: { x: 0, y: topY, width: 390, height: 872 - NOTCH - HERO_H } });
await ctx.close();

const logo = fs.readFileSync(path.join(root, 'gobarska-napoved/valovi/logo-valovi.svg'), 'utf8');
const FONT = `Inter,"Inter Display","Helvetica Neue",Arial,sans-serif`;
const BASE = `*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1350px;overflow:hidden;font-family:${FONT}}`;
const FINE_TXT = 'Primer izračuna na dan izdelave kartice. Ujemanje pravil ni verjetnost najdbe, okna so modelski razpon.';
const ids = groups.map(g => g.id);
const credAll = 'Foto: ' + [...new Set(ids)].map(credit).join(', ') + ', Wikimedia Commons.';

const cards = {};

// ── 1. FOTO ────────────────────────────────────────────────────────────────
cards.foto = `<style>${BASE}
html,body{background:#08130d;color:#eef6f0}
.bg{position:absolute;inset:0;background:radial-gradient(900px 700px at 50% 30%,rgba(63,207,142,.28),transparent 70%),radial-gradient(500px 400px at 0% 100%,rgba(167,139,250,.16),transparent 70%)}
.arcs{position:absolute;left:50%;top:20px;width:1000px;height:1000px;margin-left:-500px}
.ph{position:absolute;left:50%;top:140px;width:580px;height:580px;margin-left:-290px;border-radius:50%;object-fit:cover;
 border:10px solid #08130d;box-shadow:0 30px 80px rgba(0,0,0,.6)}
.brand{position:absolute;left:64px;top:60px;display:flex;align-items:center;gap:20px}
.brand svg{width:78px;height:78px;border-radius:18px}
.brand b{font-size:34px;font-weight:800;letter-spacing:-.01em}.brand b em{font-style:normal;color:#3fcf8e}
.brand i{display:block;font-style:normal;font-size:20px;letter-spacing:.16em;text-transform:uppercase;color:#3fcf8e;font-weight:800;margin-bottom:2px}
.t{position:absolute;left:0;right:0;top:740px;text-align:center;padding:0 60px}
h1{margin:0;font-size:104px;line-height:1;font-weight:800;letter-spacing:-.03em}h1 span{color:#3fcf8e}
p{margin:20px auto 0;font-size:32px;line-height:1.35;color:#b9ccbf;max-width:880px}
.chips{position:absolute;left:0;right:0;top:1100px;display:flex;justify-content:center;gap:16px}
.chip{display:flex;align-items:center;gap:12px;padding:16px 26px;border-radius:999px;font-size:28px;font-weight:800;border:2px solid}
.chip i{width:16px;height:16px;border-radius:50%;display:block}
.btn{position:absolute;left:64px;right:64px;top:1210px;display:flex;justify-content:space-between;align-items:center}
.btn b{background:#27834d;color:#fff;font-size:34px;padding:22px 38px;border-radius:20px}
.btn span{font-size:26px;color:#9fb3a6;text-align:right;line-height:1.3}.btn span u{text-decoration:none;color:#eef6f0;font-weight:800}
.fine{position:absolute;left:64px;right:64px;bottom:20px;font-size:17px;color:#7f9486;line-height:1.35}
</style><div class="bg"></div>
<svg class="arcs" viewBox="0 0 100 100" fill="none" stroke-linecap="round"><path d="M6 78A44 44 0 0 1 94 78" stroke="${groups[2].color}" stroke-width="1.8" opacity=".85"/>
<path d="M11 78A39 39 0 0 1 89 78" stroke="${groups[1].color}" stroke-width="1.8" opacity=".85"/><path d="M16 78A34 34 0 0 1 84 78" stroke="${groups[0].color}" stroke-width="1.8" opacity=".85"/></svg>
<div class="brand">${logo}<div><i>MeteoGobar</i><b>Gobji <em>valovi</em></b></div></div>
<img class="ph" src="${photoUri('boletus_edulis')}" style="object-position:50% 40%">
<div class="t"><h1>Dež je padel.<br><span>Kdaj v gozd?</span></h1><p>Vsaka skupina gob raste po svojem urniku.<br>Kalkulator pokaže okno rasti.</p></div>
<div class="chips">${groups.map(g => `<div class="chip" style="color:${g.color};border-color:${g.color}55;background:${g.color}14"><i style="background:${g.color}"></i>${g.short} · ${g.lagMin}–${g.lagMax} dni</div>`).join('')}</div>
<div class="btn"><b>Preračunajte dež →</b><span>Kalkulator rasti gob<br><u>meteorec.si</u></span></div>
<div class="fine">Zamiki so modelski razpon, ne napoved najdbe. Foto: ${credit('boletus_edulis')}, Wikimedia Commons.</div>`;

// ── 2. ČASOVNICA ───────────────────────────────────────────────────────────
{
  const L = 72, W = 936, maxD = Math.max(...groups.map(g => g.e0)) + 2;
  const x = d => L + (d + 0.5) / (maxD + 1) * W;
  const ticks = []; for (let d = 0; d <= maxD; d += 2) { const dt = new Date(rainDate.getTime() + d * DAY); ticks.push([d, `${dt.getUTCDate()}. ${dt.getUTCMonth() + 1}.`]); }
  const todayOff = RAIN_DAYS_AGO;
  const rowH = 170, y0 = 560;
  const rows = groups.map((g, i) => {
    const y = y0 + i * rowH, xs = x(g.s0 - 0.5), xe = x(g.e0 + 0.5);
    return `<div class="row" style="top:${y}px"><div class="nm"><b style="color:${g.color}">${g.name}</b> <span>${g.range}</span></div>
<div class="bar" style="left:${xs}px;width:${xe - xs}px;background:${g.color}"></div></div>`;
  }).join('');
  cards.casovnica = `<style>${BASE}
html,body{background:#0a1610;color:#eef6f0}
.bg{position:absolute;inset:0;background:radial-gradient(800px 500px at 100% 0%,rgba(63,207,142,.2),transparent 70%),radial-gradient(700px 500px at 0% 100%,rgba(96,165,250,.14),transparent 70%)}
.brand{position:absolute;left:72px;top:60px;display:flex;align-items:center;gap:18px;font-size:28px;font-weight:800}
.brand svg{width:64px;height:64px;border-radius:15px}.brand em{font-style:normal;color:#3fcf8e}
h1{position:absolute;left:72px;right:72px;top:160px;margin:0;font-size:92px;line-height:1.02;font-weight:800;letter-spacing:-.03em}h1 span{color:#3fcf8e}
p.s{position:absolute;left:72px;right:72px;top:372px;margin:0;font-size:31px;line-height:1.35;color:#b9ccbf;white-space:nowrap}
.drop{position:absolute;left:${x(0) - 30}px;top:${y0 - 70}px;width:60px;height:60px}
.dropl{position:absolute;left:${x(0) + 34}px;top:${y0 - 56}px;font-size:26px;font-weight:800;color:#60a5fa;white-space:nowrap}
.grid{position:absolute;top:${y0 - 6}px;height:${rowH * 3 + 6}px;width:2px;background:rgba(255,255,255,.07)}
.today{position:absolute;left:${x(todayOff)}px;top:${y0 - 30}px;height:${rowH * 3 + 30}px;border-left:3px dashed #fbbf24}
.todayl{position:absolute;left:${x(todayOff) - 56}px;top:${y0 - 70}px;width:115px;text-align:center;background:#fbbf24;color:#1a1204;font-weight:800;font-size:23px;padding:6px 0;border-radius:10px}
.row{position:absolute;left:0;right:0;height:${rowH}px}
.nm{position:absolute;left:72px;top:0;font-size:32px;font-weight:800;z-index:2;background:#0a1610;padding:2px 14px 2px 0;white-space:nowrap}.nm span{font-size:26px;font-weight:600;color:#b9ccbf;margin-left:10px}
.bar{position:absolute;top:62px;height:56px;border-radius:28px;z-index:1;box-shadow:0 8px 30px rgba(0,0,0,.4)}
.axis{position:absolute;left:0;right:0;top:${y0 + rowH * 3 + 20}px}
.tk{position:absolute;top:0;transform:translateX(-50%);font-size:23px;color:#8aa093;font-weight:700}
.cta{position:absolute;left:72px;right:72px;bottom:96px;display:flex;justify-content:space-between;align-items:center}
.cta b{background:#27834d;color:#fff;font-size:34px;padding:22px 38px;border-radius:20px}
.cta span{font-size:26px;color:#9fb3a6;text-align:right;line-height:1.3}.cta span u{text-decoration:none;color:#eef6f0;font-weight:800}
.fine{position:absolute;left:72px;right:72px;bottom:22px;font-size:17px;color:#7f9486;line-height:1.35}
.tag{position:absolute;left:72px;top:${y0 - 130}px;font-size:25px;font-weight:800;color:#60a5fa;letter-spacing:.04em}
</style><div class="bg"></div>
<div class="brand">${logo}<span>Gobji <em>valovi</em></span></div>
<h1>Po enem dežju<br><span>trije valovi.</span></h1>
<p class="s">Stelja, les in mikorizne vrste ne rastejo hkrati.</p>
<div class="tag">${primer.toUpperCase()}</div>
${ticks.map(([d]) => `<div class="grid" style="left:${x(d)}px"></div>`).join('')}
<div class="today"></div><div class="todayl" style="left:${x(todayOff) - 58}px">danes</div>
<div class="dropl">${RAIN_MM} mm</div><svg class="drop" viewBox="0 0 24 24"><path d="M12 2.5C12 2.5 5 10.2 5 15a7 7 0 0 0 14 0c0-4.800-7-12.500-7-12.500z" fill="#60a5fa"/></svg>
${rows}
<div class="axis">${ticks.map(([d, l]) => `<div class="tk" style="left:${x(d)}px">${l}</div>`).join('')}</div>
<div class="cta"><b>Preračunajte svoj dež →</b><span>Kalkulator rasti gob<br><u>meteorec.si</u></span></div>
<div class="fine">${FINE_TXT}</div>`;
}

// ── 3. POSTER (svetla, trajna) ─────────────────────────────────────────────
{
  const dark = { 'Razkrojevalke stelje': '#0f766e', 'Lesne vrste': '#b45309', 'Mikorizne vrste': '#6d28d9' };
  const rows = groups.map((g, i) => `<div class="r" style="top:${440 + i * 232}px">
<img src="${photoUri(g.id)}"><div class="m"><div class="k" style="color:${dark[g.name]}">${g.name}</div>
<div class="n" style="color:${dark[g.name]}">${g.lagMin}–${g.lagMax}<small> dni</small></div></div></div>`).join('');
  cards.poster = `<style>${BASE}
html,body{background:#f4ecda;color:#1d2a20}
.bg{position:absolute;inset:0;background:radial-gradient(700px 500px at 100% 0%,rgba(193,127,62,.22),transparent 70%),radial-gradient(600px 500px at 0% 100%,rgba(15,118,110,.12),transparent 70%)}
.brand{position:absolute;left:72px;top:60px;display:flex;align-items:center;gap:18px;font-size:28px;font-weight:800}
.brand svg{width:64px;height:64px;border-radius:15px}.brand em{font-style:normal;color:#1f7a49}
.lab{position:absolute;right:72px;top:74px;font-size:22px;letter-spacing:.16em;text-transform:uppercase;font-weight:800;color:#8a6a3a}
h1{position:absolute;left:72px;right:72px;top:150px;margin:0;font-size:100px;line-height:1;font-weight:800;letter-spacing:-.035em}h1 span{color:#1f7a49}
p.s{position:absolute;left:72px;right:72px;top:372px;margin:0;font-size:30px;line-height:1.35;color:#4b5a4e}
.r{position:absolute;left:72px;right:72px;height:214px;display:flex;align-items:center;gap:36px;background:#fffaf0;border-radius:36px;padding:18px;
 box-shadow:0 10px 30px rgba(80,60,20,.12);border:2px solid rgba(80,60,20,.1)}
.r img{width:178px;height:178px;border-radius:24px;object-fit:cover;flex:none}
.k{font-size:30px;font-weight:800;letter-spacing:.01em}
.n{font-size:112px;line-height:1;font-weight:800;letter-spacing:-.04em;margin-top:4px}.n small{font-size:42px;letter-spacing:0;font-weight:800}
.after{position:absolute;right:72px;top:1172px;font-size:27px;color:#4b5a4e;text-align:right;line-height:1.3}
.btn{position:absolute;left:72px;top:1164px;background:#1f7a49;color:#fff;font-size:34px;font-weight:800;padding:22px 38px;border-radius:20px}
.after u{text-decoration:none;color:#1d2a20;font-weight:800}
.fine{position:absolute;left:72px;right:72px;bottom:20px;font-size:17px;color:#7b8576;line-height:1.35}
</style><div class="bg"></div>
<div class="brand">${logo}<span>Gobji <em>valovi</em></span></div><div class="lab">MeteoGobar</div>
<h1>Koliko dni<br><span>po dežju?</span></h1>
<p class="s">Zamik rasti po skupinah gob, kot ga računa naš model.</p>
${rows}
<div class="btn">Preračunajte dež →</div><div class="after">Kalkulator rasti gob<br><u>meteorec.si</u></div>
<div class="fine">Modelski razpon od dežja do rasti, ne napoved najdbe. ${credAll}</div>`;
}

// ── 4. TELEFON (več besedilnih različic; postavitev ista) ───────────────────
const lag = g => `${g.lagMin}–${g.lagMax} dni`;
const TICK = c => `<i style="background:${c}22"><svg viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.500 4.500L19 7.500"/></svg></i>`;
const GREEN = '#3fcf8e';
const TEXTS = {
  a: { h: 'Je deževalo?<br><span>Preverite, kdaj rastejo gobe.</span>', size: 66,
       bullets: ['Vnesite datum in količino dežja', 'Izberite skupino gob', 'Poglejte okno rasti'] },
};
const telefon = t => `<style>${BASE}
html,body{background:#0b1510;color:#eef6f0}
.bg{position:absolute;inset:0;background:radial-gradient(800px 700px at 85% 55%,rgba(63,207,142,.35),transparent 70%),radial-gradient(500px 400px at 0% 0%,rgba(167,139,250,.18),transparent 70%)}
.brand{position:absolute;left:64px;top:50px;display:flex;align-items:center;gap:24px;font-size:48px;font-weight:800;letter-spacing:-.01em}
.brand svg{width:116px;height:116px;border-radius:26px}.brand em{font-style:normal;color:#3fcf8e}
.col{position:absolute;left:64px;width:490px;top:226px;bottom:300px;display:flex;flex-direction:column;gap:34px}
h1{margin:0;font-size:${t.size}px;line-height:1.05;font-weight:800;letter-spacing:-.03em}h1 span{color:#3fcf8e}
p.sub{margin:0;font-size:32px;line-height:1.35;color:#c4d5c9}
ul{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:22px}
li{display:flex;align-items:center;gap:18px;font-size:29px;line-height:1.25;color:#d4e3d8;font-weight:600}
li i{flex:none;width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center}
li svg{width:24px;height:24px}
.btn{position:absolute;left:64px;top:1090px;background:#27834d;color:#fff;font-size:32px;font-weight:800;padding:22px 36px;border-radius:20px}
.url{position:absolute;left:64px;top:1190px;font-size:26px;color:#9fb3a6}.url u{text-decoration:none;color:#eef6f0;font-weight:800}
.phone{position:absolute;left:575px;top:150px;width:470px;height:1017px;transform:rotate(5deg);border-radius:66px;background:#111;padding:14px;
 box-shadow:0 0 0 3px #2a3a30,0 40px 90px rgba(0,0,0,.7),0 0 120px rgba(63,207,142,.25)}
.scr{width:100%;height:100%;border-radius:54px;overflow:hidden;background:#0b1510;padding-top:${Math.round(NOTCH * 442 / 390)}px}.scr img{width:100%;display:block}
.phone:before{content:"";position:absolute;left:50%;top:26px;width:120px;height:30px;margin-left:-60px;border-radius:20px;background:#000;z-index:2}
.fine{position:absolute;left:64px;width:480px;bottom:20px;font-size:16px;color:#7f9486;line-height:1.35}
</style><div class="bg"></div>
<div class="brand">${logo}<span>Gobji <em>valovi</em></span></div>
<div class="col"><h1>${t.h}</h1>${t.sub ? `<p class="sub">${t.sub}</p>` : ''}
${t.bullets ? `<ul>${t.bullets.map(x => { const [txt, c] = Array.isArray(x) ? x : [x, GREEN]; return `<li>${TICK(c)}${txt}</li>`; }).join('')}</ul>` : ''}</div>
<div class="btn">Preračunajte dež →</div><div class="url">Kalkulator rasti gob · <u>meteorec.si</u></div>
<div class="phone"><div class="scr"><img src="data:image/png;base64,${heroShot.toString('base64')}"><img src="data:image/png;base64,${resShot.toString('base64')}"></div></div>
<div class="fine">${FINE_TXT} ${credAll}</div>`;
for (const [k, t] of Object.entries(TEXTS)) cards['telefon-' + k] = telefon(t);

// ── izris ──────────────────────────────────────────────────────────────────
const FILES = { foto: 'valovi-fb-1-foto.jpg', casovnica: 'valovi-fb-2-casovnica.jpg', poster: 'valovi-fb-3-poster.jpg', };
FILES['telefon-a'] = 'valovi-fb-4-telefon.jpg';
const ctx2 = await b.newContext({ viewport: { width: 1080, height: 1350 } });
for (const [k, html] of Object.entries(cards)) {
  if (only && only !== k && only !== k.split('-')[0]) continue;
  const p = await ctx2.newPage();
  await p.setContent(`<!doctype html><meta charset="utf-8">${html}`, { waitUntil: 'load' });
  await p.evaluate(() => document.fonts.ready);
  await p.screenshot({ path: path.join(root, 'og', FILES[k]), type: 'jpeg', quality: 92 });
  await p.close();
  console.log('ok', FILES[k]);
}
await b.close(); srv.close();
console.log(groups.map(g => `${g.short}: ${g.range} (zamik ${g.lagMin}-${g.lagMax}, ${g.s0}..${g.e0})`).join(' | '));
