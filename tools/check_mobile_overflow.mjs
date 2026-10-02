// Ročni mobilni pregled: na 360/390/430 px poišče strani, ki se premikajo vstran
// (scrollWidth > širina) in element, ki je kriv. Strežnik: python3 -m http.server 8765
// v korenu repozitorija; zunanji klici so blokirani (meri se statična postavitev).
//   PW=$(npm root -g)/playwright OUT=/tmp node tools/check_mobile_overflow.mjs / /vreme/2026/09/ …
// Namenoma ni v CI (Chromium v workflowu je drag); poženi ob novi vrsti strani.
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW);
const pages = process.argv.slice(2);
const widths = [360, 390, 430];
const b = await chromium.launch();
for (const w of widths) {
  const ctx = await b.newContext({ viewport: { width: w, height: 800 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const p = await ctx.newPage();
  // brez zunanjih klicev (API, GA) — merimo postavitev statične strani
  await p.route('**/*', r => { const u = r.request().url(); return u.startsWith('http://localhost') ? r.continue() : r.abort(); });
  for (const path of pages) {
    try { await p.goto('http://localhost:8765' + path, { waitUntil: 'load', timeout: 20000 }); } catch (e) { console.log(w, path, 'NAPAKA', e.message.slice(0, 80)); continue; }
    await p.waitForTimeout(600);
    const r = await p.evaluate(() => {
      const W = document.documentElement.clientWidth;
      const over = [];
      for (const el of document.querySelectorAll('body *')) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') continue;
        const rc = el.getBoundingClientRect();
        if (rc.width === 0 || rc.height === 0) continue;
        if (rc.right > W + 1 || rc.left < -1) {
          // prijavi samo, če noben prednik nima overflow (scroll/hidden)
          let a = el.parentElement, clipped = false;
          while (a && a !== document.body) { const o = getComputedStyle(a); if (/(auto|scroll|hidden|clip)/.test(o.overflowX)) { clipped = true; break; } a = a.parentElement; }
          if (!clipped) over.push((el.tagName + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').slice(0,2).join('.') : '')) + ' r=' + Math.round(rc.right));
        }
      }
      return { sw: document.documentElement.scrollWidth, W, over: [...new Set(over)].slice(0, 8) };
    });
    console.log(w, path, r.sw > r.W ? `PRELIV scrollWidth=${r.sw}` : 'ok', r.over.length ? JSON.stringify(r.over) : '');
    if (w === 360) await p.screenshot({ path: `${process.env.OUT}/m360${path.replace(/\W+/g, '_')}.png` });
  }
  await ctx.close();
}
await b.close();
