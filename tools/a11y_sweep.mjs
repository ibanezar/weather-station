// Ročni pregled dostopnosti in vodoravnega razliva za strani iz CORE (seo_audit.py).
// Strežnik: python3 -m http.server 8765 v korenu repozitorija; zunanji klici so blokirani (meri se statična stran).
//   PW=$(npm root -g)/playwright AXE=/pot/do/axe-core/axe.min.js node tools/a11y_sweep.mjs            # vse strani iz CORE
//   ... node tools/a11y_sweep.mjs /astma/ /snegofili/                                                  # samo izbrane
// Meri: scrollWidth proti širini pri 360 px (z elementom, ki ga povzroča) in axe-core (wcag2a/aa, 2.1 aa, 2.2 aa),
// samo »serious« in »critical«, v svetli in temni shemi. Prvi tek (19. 11. 2026): 128 strani, 0 razlivov, 9 skupin napak axe
// (kontrast povezav in gumbov, aria-label na <b>, drsne regije brez fokusa, tablist brez tab, ločilo z gumbom).
// Namenoma ni v CI (Chromium in axe sta draga); poženi ob novi vrsti strani ali večji spremembi CSS.
// axe-core: `npm i axe-core` v poljubni mapi; AXE kaže na axe.min.js. Brez AXE se preveri samo razliv.
import { createRequire } from 'module';
import { execFileSync } from 'child_process';
import fs from 'fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW);
const AXE = process.env.AXE ? fs.readFileSync(process.env.AXE, 'utf8') : null;
const BASE = process.env.BASE || 'http://localhost:8765';

function corePaths() {
  const out = execFileSync('python3', ['-c',
    "import sys,json;sys.path.insert(0,'tools');import seo_audit as s;print(json.dumps(['/'+k if k else '/' for k in s.CORE]))"],
    { encoding: 'utf8' });
  return JSON.parse(out);
}

const paths = process.argv.length > 2 ? process.argv.slice(2) : corePaths();
const b = await chromium.launch();
let bad = 0;
for (const path of paths) {
  const issues = [];
  for (const scheme of ['light', 'dark']) {
    const ctx = await b.newContext({ viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true, colorScheme: scheme });
    const p = await ctx.newPage();
    await p.route('**/*', r => (r.request().url().startsWith(BASE) ? r.continue() : r.abort()));
    try {
      await p.goto(BASE + path, { waitUntil: 'load', timeout: 25000 });
      await p.waitForTimeout(700);
      if (scheme === 'light') {
        const over = await p.evaluate(() => {
          const W = document.documentElement.clientWidth, sw = document.documentElement.scrollWidth;
          if (sw <= W + 1) return null;
          const els = [];
          for (const el of document.querySelectorAll('body *')) {
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') continue;
            const r = el.getBoundingClientRect();
            if (!r.width || !r.height || r.right <= W + 1) continue;
            let a = el.parentElement, clip = false;
            while (a && a !== document.body) { if (/(auto|scroll|hidden|clip)/.test(getComputedStyle(a).overflowX)) { clip = true; break; } a = a.parentElement; }
            if (!clip) els.push(`${el.tagName}.${String(el.className).slice(0, 30)}#${el.id} r=${Math.round(r.right)}`);
          }
          return { sw, W, els: els.slice(0, 4) };
        });
        if (over) issues.push(`razliv ${over.sw}>${over.W}: ${over.els.join('; ')}`);
      }
      if (AXE) {
        await p.evaluate(AXE);
        const res = await p.evaluate(() => axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] }, resultTypes: ['violations'] }));
        for (const v of res.violations.filter(x => ['serious', 'critical'].includes(x.impact)))
          issues.push(`axe ${scheme} ${v.id} [${v.impact}] ×${v.nodes.length}: ${v.nodes[0].target.join(' ').slice(0, 70)}`);
      }
    } catch (e) { issues.push(`${scheme}: napaka ${e.message.slice(0, 60)}`); }
    await ctx.close();
  }
  const uniq = [...new Set(issues)];
  if (uniq.length) { bad++; console.log(path); for (const i of uniq) console.log('   ', i); }
}
await b.close();
console.log(bad ? `\n${bad} od ${paths.length} strani ima težave` : `\n${paths.length} strani brez težav`);
process.exit(bad ? 1 : 0);
