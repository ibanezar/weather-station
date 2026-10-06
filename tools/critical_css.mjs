#!/usr/bin/env node
// Kritični CSS za index.html: v <head> vstavi samo pravila, ki jih rabi vsebina v
// prvih ~1,5 zaslonih, ostalo (style.min.css) se naloži brez blokiranja izrisa.
//
// Zakaj: style.min.css (45 KiB prenosa) je bil render-blocking — PageSpeed (mobile, 6. 10. 2026)
// je ocenil 1,9 s zadržanega prvega izrisa. Celoten CSS se še vedno naloži in je enak, zato
// zastarel kritični del (style.css se je spremenil, tega skripta še ni osvežila) povzroči
// kvečjemu kratek drugačen izris, ne zlomljene strani. Osvežuje ga minify-assets.yml.
//
// Kako: Chromium (Playwright) naloži stran v 12 stanjih (telefon/namizje × temna/svetla tema ×
// nov obiskovalec/napredni/preprosti pogled), za vsako pravilo pogleda, ali se kak njegov
// selektor ujema z elementom, ki ima postavitev in leži v prvih 1,5 zaslonih. Unija stanj gre
// v index.html med markerja CRITICAL-CSS. @font-face iz fonts/fonts.css gre v isti blok
// (en prenos manj v verigi: HTML → fonts.css → woff2).
//
// Uporaba: node tools/critical_css.mjs   (potrebuje `playwright` in Chromium; izhod 0 tudi,
// če ju ni — stran takrat ostane pri trenutnem kritičnem bloku.)
import { createRequire } from 'module';
import { readFileSync, writeFileSync } from 'fs';
import { createServer } from 'http';
import { fileURLToPath } from 'url';
import { dirname, join, extname } from 'path';
import CleanCSS from 'clean-css';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);

let chromium;
for (const p of ['playwright', '/opt/node-tools/node_modules/playwright']) {
  try { ({ chromium } = require(p)); break; } catch (_) { /* naslednji */ }
}
if (!chromium) { console.log('critical_css: playwright ni nameščen — preskočeno.'); process.exit(0); }

const MIME = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json',
  '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.webmanifest': 'application/json' };
const server = createServer((req, res) => {
  let path = decodeURIComponent(req.url.split('?')[0]);
  if (path.endsWith('/')) path += 'index.html';
  try {
    const body = readFileSync(join(ROOT, path));
    res.writeHead(200, { 'content-type': MIME[extname(path)] || 'application/octet-stream' });
    res.end(body);
  } catch (_) { res.writeHead(404); res.end(); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const origin = `http://127.0.0.1:${server.address().port}`;

const VIEWPORTS = [{ name: 'telefon', width: 390, height: 844 }, { name: 'namizje', width: 1280, height: 800 }];
const THEMES = ['dark', 'light'];
const MODES = ['nov', 'napredni', 'preprosti'];
const REACH = 1.5; // koliko zaslonov visoko štejemo za »nad pregibom«

// Teče v strani. Vrne ključe pravil (pot v drevesu pravil + indeks selektorja), ki so potrebna.
function collect(reach) {
  const limit = innerHeight * reach;
  const sheet = [...document.styleSheets].find(s => (s.href || '').includes('style.min.css'));
  if (!sheet) return null;
  // Pseudo-razredi stanja in pseudo-elementi se za preizkus ujemanja odstranijo.
  const strip = sel => sel
    .replace(/::?(before|after|first-line|first-letter|placeholder|selection|marker|backdrop|-webkit-[\w-]+|-moz-[\w-]+)/g, '')
    .replace(/:(hover|focus|focus-visible|focus-within|active|visited|target|checked|disabled|enabled)\b/g, '')
    .trim();
  const splitSel = text => { // loči po vejicah zunaj oklepajev
    const out = []; let d = 0, cur = '';
    for (const ch of text) {
      if (ch === '(' || ch === '[') d++; else if (ch === ')' || ch === ']') d--;
      if (ch === ',' && d === 0) { out.push(cur.trim()); cur = ''; } else cur += ch;
    }
    if (cur.trim()) out.push(cur.trim());
    return out;
  };
  const visible = sel => {
    const t = strip(sel);
    if (!t) return true;
    let nodes;
    try { nodes = document.querySelectorAll(t); } catch (_) { return true; } // neznan selektor: raje vključi
    for (const el of nodes) {
      if (el.getClientRects().length) {
        if (el.getBoundingClientRect().top < limit) return true;
        continue;
      }
      // Element brez postavitve: vključimo ga samo, če ga skriva LASTNO pravilo (display:none,
      // [hidden]) in je starš viden nad pregibom. Brez tega pravilo, ki skriva pasico/gumb,
      // manjka v kritičnem delu in se pasica pred prihodom celotnega CSS pokaže neoblikovana.
      // Potomci skritih elementov (neaktivni zavihki) tako ostanejo zunaj.
      const par = el.parentElement;
      if (par && par.getClientRects().length && par.getBoundingClientRect().top < limit
          && getComputedStyle(el).display === 'none') return true;
    }
    return false;
  };
  const keys = [];
  const walk = (rules, path) => {
    [...rules].forEach((r, i) => {
      const key = path + '/' + i;
      if (r.type === CSSRule.STYLE_RULE) {
        const sels = splitSel(r.selectorText);
        sels.forEach((s, j) => { if (visible(s)) keys.push(key + '#' + j); });
      } else if (r.type === CSSRule.MEDIA_RULE || r.type === CSSRule.SUPPORTS_RULE) {
        walk(r.cssRules, key);
      }
    });
  };
  walk(sheet.cssRules, '');
  return keys;
}

const needed = new Set();
const browser = await chromium.launch();
for (const vp of VIEWPORTS) for (const theme of THEMES) for (const mode of MODES) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 });
  await ctx.addInitScript(([t, m]) => {
    try {
      localStorage.setItem('wx-theme', t);
      if (m === 'nov') { localStorage.removeItem('wx-mode'); localStorage.removeItem('wx-mode-intro'); }
      else localStorage.setItem('wx-mode', m === 'preprosti' ? 'simple' : 'advanced');
    } catch (_) { /* brez */ }
  }, [theme, mode]);
  // Zunanjih klicev ne rabimo (in naj ne vplivajo na stanje strani).
  await ctx.route(u => !u.href.startsWith(origin), r => r.abort());
  const page = await ctx.newPage();
  await page.goto(origin + '/', { waitUntil: 'load' });
  await page.waitForTimeout(1500);
  const keys = await page.evaluate(collect, REACH);
  if (!keys) { console.error('critical_css: style.min.css ni naložen — prekinjeno.'); await browser.close(); server.close(); process.exit(1); }
  keys.forEach(k => needed.add(k));
  console.log(`  ${vp.name} / ${theme} / ${mode}: ${keys.length} selektorjev`);
  await ctx.close();
}
await browser.close();
server.close();

// Izris izbranih pravil iz iste datoteke (razčlenimo z brskalnikom-neodvisnim pristopom:
// uporabimo CleanCSS-ov izhod kot besedilo in ga ponovno preberemo prek Chromiuma ni potrebno —
// ključi so indeksi pravil v style.min.css, zato jih beremo še enkrat v brskalniku).
const browser2 = await chromium.launch();
const page2 = await (await browser2.newContext()).newPage();
const server2 = createServer((req, res) => { res.writeHead(200, { 'content-type': 'text/html' }); res.end('<!doctype html><html></html>'); });
await new Promise(r => server2.listen(0, '127.0.0.1', r));
await page2.goto(`http://127.0.0.1:${server2.address().port}/`);
const css = readFileSync(join(ROOT, 'style.min.css'), 'utf8');
const critical = await page2.evaluate(([cssText, keyList]) => {
  const st = document.createElement('style'); st.textContent = cssText; document.head.appendChild(st);
  const rules = st.sheet.cssRules;
  const want = new Set(keyList);
  const splitSel = text => {
    const out = []; let d = 0, cur = '';
    for (const ch of text) {
      if (ch === '(' || ch === '[') d++; else if (ch === ')' || ch === ']') d--;
      if (ch === ',' && d === 0) { out.push(cur.trim()); cur = ''; } else cur += ch;
    }
    if (cur.trim()) out.push(cur.trim());
    return out;
  };
  const build = (rs, path) => {
    let out = '';
    [...rs].forEach((r, i) => {
      const key = path + '/' + i;
      if (r.type === CSSRule.STYLE_RULE) {
        const sels = splitSel(r.selectorText).filter((_, j) => want.has(key + '#' + j));
        if (sels.length) out += sels.join(',') + '{' + r.style.cssText + '}';
      } else if (r.type === CSSRule.MEDIA_RULE || r.type === CSSRule.SUPPORTS_RULE) {
        const inner = build(r.cssRules, key);
        if (inner) out += (r.type === CSSRule.MEDIA_RULE ? '@media ' : '@supports ') + r.conditionText + '{' + inner + '}';
      }
    });
    return out;
  };
  let body = build(rules, '');
  // @keyframes / @property: samo tisti, katerih ime se pojavi v izbranih pravilih.
  let extra = '';
  [...rules].forEach(r => {
    if (r.type === CSSRule.KEYFRAMES_RULE && body.includes(r.name)) extra += r.cssText;
  });
  return { body, extra };
}, [css, [...needed]]);
await browser2.close();
server2.close();

const fonts = readFileSync(join(ROOT, 'fonts', 'fonts.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
const minified = new CleanCSS({}).minify(fonts + critical.extra + critical.body);
if (minified.errors.length) throw new Error(minified.errors.join('\n'));
const out = minified.styles;

const file = join(ROOT, 'index.html');
let html = readFileSync(file, 'utf8');
const re = /<!-- CRITICAL-CSS:START[^>]*-->[\s\S]*?<!-- CRITICAL-CSS:END -->/;
if (!re.test(html)) { console.error('critical_css: v index.html ni markerjev CRITICAL-CSS.'); process.exit(1); }
const block = `<!-- CRITICAL-CSS:START (izpeljano: node tools/critical_css.mjs — ne urejaj ročno) -->\n<style id="critical-css">${out}</style>\n<!-- CRITICAL-CSS:END -->`;
html = html.replace(re, () => block);
writeFileSync(file, html);
console.log(`critical_css: ${out.length} B kritičnega CSS (celoten style.min.css ${css.length} B).`);
