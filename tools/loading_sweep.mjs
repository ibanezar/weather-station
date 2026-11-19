// Ročni pregled »večnega nalaganja« (19. 11. 2026): strani iz CORE naloži brez omrežja do workerja/zunanjih virov
// (vse zunaj BASE je prekinjeno), počaka WAIT ms in izpiše vidne elemente, ki še kažejo »Preverjam/Nalagam …«.
// Napaka vira mora biti vidna (sporočilo ali skrit gradnik), ne večni placeholder.
//   PW=$(npm root -g)/playwright node tools/loading_sweep.mjs [/pot/ ...]     (strežnik: python3 -m http.server 8765)
import { createRequire } from 'module';
import { execFileSync } from 'child_process';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW);
const BASE = process.env.BASE || 'http://localhost:8765';
const WAIT = +(process.env.WAIT || 9000);
const paths = process.argv.length > 2 ? process.argv.slice(2) : JSON.parse(execFileSync('python3', ['-c',
  "import sys,json;sys.path.insert(0,'tools');import seo_audit as s;print(json.dumps(['/'+k if k else '/' for k in s.CORE]))"], { encoding: 'utf8' }));
const RE = /^\s*(preverjam|nalagam|nalaganje|iščem|pridobivam|računam|loading)\b[^.]{0,40}(…|\.\.\.)?\s*$/i;
const b = await chromium.launch();
let bad = 0;
for (const path of paths) {
  const ctx = await b.newContext({ viewport: { width: 390, height: 800 } });
  const p = await ctx.newPage();
  await p.route('**/*', r => (r.request().url().startsWith(BASE) ? r.continue() : r.abort()));
  try {
    await p.goto(BASE + path, { waitUntil: 'load', timeout: 25000 });
    await p.waitForTimeout(WAIT);
    const hits = await p.evaluate(src => {
      const re = new RegExp(src, 'i'), out = [];
      for (const el of document.querySelectorAll('body *')) {
        if (el.children.length > 1) continue;
        const t = el.textContent || '';
        if (!re.test(t)) continue;
        const cs = getComputedStyle(el), r = el.getBoundingClientRect();
        if (cs.display === 'none' || cs.visibility === 'hidden' || !r.width || !r.height || el.closest('[hidden],noscript,template')) continue;
        out.push(`${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : ''} "${t.trim().slice(0, 40)}"`);
      }
      return out;
    }, RE.source);
    if (hits.length) { bad++; console.log(path); for (const h of [...new Set(hits)].slice(0, 6)) console.log('   ', h); }
  } catch (e) { console.log(path, 'napaka', e.message.slice(0, 60)); }
  await ctx.close();
}
await b.close();
console.log(bad ? `\n${bad} od ${paths.length} strani kaže placeholder` : `\n${paths.length} strani brez večnega nalaganja`);
