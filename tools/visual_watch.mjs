// tools/visual_watch.mjs — čuvaj VIDEZA žive strani (visual-watch.yml).
//
// Zakaj: smoke_test.py preveri, da stran obstaja in ima pravo vsebino, varuh svežine pa, da so podatki sveži.
// Nobeden ne vidi, ali se stran VIDI prav: CLS na namizju je bil 0,16–0,21 teden dni (vrstica zavihkov
// se je ob prihodu pisav skrčila z 84 na 49 px), ne da bi kdo opazil. Ta skript to meri vsak dan na ŽIVI strani.
//
// Preveri (vse na https://meteorec.si, brez avtorizacije):
//   1. CLS naslovne strani na telefonu (390 px) in namizju (1280 px): mediana treh tekov pod omejitvijo omrežja
//      (CDP 200 kB/s, 150 ms, CPU 4×, kot ročne meritve v CLAUDE.md), meja CLS_MAX.
//   2. Vodoravni razliv (scrollWidth > širina) na ključnih straneh pri 360 px.
//   3. axe-core (wcag2a/aa, 2.1 aa, 2.2 aa) na hero kartici v obeh temah: resne in kritične kršitve.
//   4. Odzivnost (INP): najdaljši odziv med štirimi dotiki (»Pokaži podrobnosti«, zavihka MTR in Zdaj, spet »podrobnosti«)
//      pod isto omejitvijo kot CLS; mediana treh tekov, meja INP_MAX (varovalka pred poslabšanjem, ne cilj CWV).
//
// Napake gredo v poročilo (--report) in izhod `fail` v GITHUB_OUTPUT; workflow odpre/zapre issue `visual-fail`.
// Namerno samo ŽIVA stran: lokalni strežnik brez stiskanja ne reproducira premikov (glej CLAUDE.md, CLS na namizju).
//
// Usage: node tools/visual_watch.mjs [--base https://meteorec.si] [--report visual.md] [--runs 3]
import { createRequire } from 'module';
import fs from 'fs';
const require = createRequire(import.meta.url);

const args = process.argv.slice(2);
const arg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const BASE = arg('--base', 'https://meteorec.si').replace(/\/$/, '');
const REPORT = arg('--report', '');
const RUNS = +arg('--runs', 3);

export const CLS_MAX = 0.10;          // "dobro" je pod 0,1 (Core Web Vitals); po popravku zavihkov je namizje ~0,005, telefon ~0,05
export const OVERFLOW_PAGES = ['/', '/vreme-recica-ob-savinji/', '/zima/', '/blog/', '/nevihte/', '/tocnost-napovedi/'];
export const AXE_BAD = ['serious', 'critical'];
// INP pod CPU 4× (kot srednji telefon): izmerjeno 5. 11. 2026 na živi strani 360–528 ms (telefon), 568–640 ms (namizje; zavihek MTR ~560 ms).
// CWV: dobro ≤ 200 ms, slabo > 500 ms. Meja 800 ms je VAROVALKA pred poslabšanjem od današnjega stanja, ne trditev, da je 600 ms dobro:
// vse nad INP_POOR se izpiše v poročilu kot opozorilo, issue pa odpre šele INP_MAX.
export const INP_MAX = 800;
export const INP_POOR = 500;
export const INP_STEPS = ['#more-toggle', '#tab-btn-mtr', '#tab-btn-current', '#more-toggle'];

export function median(a) { const s = [...a].sort((x, y) => x - y); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : NaN; }

// Najdaljša interakcija: dogodki z istim interactionId (pointerdown, pointerup, click) so en dotik, štejejo kot največji od njih.
export function worstInteraction(events) {
  const by = new Map();
  for (const e of events || []) if (e && e.id) by.set(e.id, Math.max(by.get(e.id) || 0, e.d));
  return by.size ? Math.max(...by.values()) : NaN;
}

export function evaluate({ cls, overflow, axe, inp }) {
  // cls: {mobile:[...], desktop:[...]}, overflow: [{path, sw, W, over}], axe: [{theme, id, impact, nodes}], inp: {mobile:[ms], desktop:[ms]} (neobvezno)
  const fails = [];
  for (const [k, v] of Object.entries(inp || {})) {
    const m = median(v);
    if (!(m <= INP_MAX)) fails.push(`INP ${k}: mediana ${Number.isNaN(m) ? 'brez meritve' : Math.round(m) + ' ms'} > ${INP_MAX} ms (teki: ${v.map(x => Math.round(x)).join(', ')})`);
  }
  for (const [k, v] of Object.entries(cls)) {
    const m = median(v);
    if (!(m <= CLS_MAX)) fails.push(`CLS ${k}: mediana ${Number.isNaN(m) ? 'brez meritve' : m.toFixed(3)} > ${CLS_MAX} (teki: ${v.map(x => x.toFixed(3)).join(', ')})`);
  }
  for (const o of overflow) if (o.sw > o.W) fails.push(`razliv ${o.path} pri 360 px: scrollWidth ${o.sw} > ${o.W} ${o.over.length ? '(' + o.over.join('; ') + ')' : ''}`);
  for (const a of axe) if (AXE_BAD.includes(a.impact)) fails.push(`axe (${a.theme}) ${a.id} [${a.impact}] na ${a.nodes} elementih hero kartice`);
  return fails;
}

async function main() {
  const { chromium } = require(process.env.PW || 'playwright');
  const b = await chromium.launch();
  const cls = { mobile: [], desktop: [] };
  const overflow = [];
  const axeRes = [];

  async function throttled(ctx, page) {
    const c = await ctx.newCDPSession(page);
    await c.send('Network.enable');
    await c.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: 200 * 1024, uploadThroughput: 200 * 1024 });
    await c.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  }

  // 1) CLS
  for (const [name, vp, mobile] of [['mobile', { width: 390, height: 844 }, true], ['desktop', { width: 1280, height: 800 }, false]]) {
    for (let i = 0; i < RUNS; i++) {
      const ctx = await b.newContext({ viewport: vp, colorScheme: 'dark', deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile });
      const p = await ctx.newPage();
      await throttled(ctx, p);
      await p.addInitScript(() => {
        window.__cls = 0;
        new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
      });
      try {
        await p.goto(BASE + '/', { waitUntil: 'load', timeout: 60000 });
        await p.waitForTimeout(6000);
        cls[name].push(await p.evaluate(() => window.__cls));
      } catch (e) { console.log('CLS', name, 'napaka', e.message.slice(0, 80)); }
      await ctx.close();
    }
  }

  // 2) razliv pri 360 px
  {
    const ctx = await b.newContext({ viewport: { width: 360, height: 800 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
    const p = await ctx.newPage();
    for (const path of OVERFLOW_PAGES) {
      try {
        await p.goto(BASE + path, { waitUntil: 'load', timeout: 45000 });
        await p.waitForTimeout(1500);
        overflow.push({ path, ...(await p.evaluate(() => {
          const W = document.documentElement.clientWidth, over = [];
          for (const el of document.querySelectorAll('body *')) {
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') continue;
            const r = el.getBoundingClientRect();
            if (!r.width || !r.height || (r.right <= W + 1 && r.left >= -1)) continue;
            let a = el.parentElement, clipped = false;
            while (a && a !== document.body) { if (/(auto|scroll|hidden|clip)/.test(getComputedStyle(a).overflowX)) { clipped = true; break; } a = a.parentElement; }
            if (!clipped) over.push(el.tagName + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.split(' ')[0] : ''));
          }
          return { sw: document.documentElement.scrollWidth, W, over: [...new Set(over)].slice(0, 4) };
        })) });
      } catch (e) { console.log('razliv', path, 'napaka', e.message.slice(0, 80)); }
    }
    await ctx.close();
  }

  // 3) axe na hero kartici
  let axePath = null;
  try { axePath = require.resolve('axe-core'); } catch { console.log('axe-core ni nameščen: preskočeno'); }
  if (axePath) {
    for (const theme of ['dark', 'light']) {
      const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, colorScheme: theme, isMobile: true, hasTouch: true });
      const p = await ctx.newPage();
      try {
        await p.goto(BASE + '/', { waitUntil: 'load', timeout: 60000 });
        await p.waitForSelector('.hero-b', { timeout: 20000 });
        await p.waitForTimeout(5000);
        await p.addScriptTag({ path: axePath });
        const res = await p.evaluate(async () => {
          const r = await axe.run('.hero-b', { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } });
          return r.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }));
        });
        for (const v of res) axeRes.push({ theme, ...v });
      } catch (e) { console.log('axe', theme, 'napaka', e.message.slice(0, 80)); }
      await ctx.close();
    }
  }

  // 4) odzivnost: dotiki na živi strani pod omejitvijo CPU
  const inp = { mobile: [], desktop: [] };
  for (const [name, vp, mobile] of [['mobile', { width: 390, height: 844 }, true], ['desktop', { width: 1280, height: 800 }, false]]) {
    for (let i = 0; i < RUNS; i++) {
      const ctx = await b.newContext({ viewport: vp, colorScheme: 'dark', deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile });
      const p = await ctx.newPage();
      await throttled(ctx, p);
      await p.addInitScript(() => {
        window.__ev = [];
        new PerformanceObserver(l => { for (const e of l.getEntries()) window.__ev.push({ id: e.interactionId, d: e.duration }); }).observe({ type: 'event', durationThreshold: 16, buffered: true });
      });
      try {
        await p.goto(BASE + '/', { waitUntil: 'load', timeout: 60000 });
        await p.waitForTimeout(6000);
        for (const sel of INP_STEPS) {
          try { await p.locator(sel).scrollIntoViewIfNeeded({ timeout: 3000 }); await p.locator(sel).click({ timeout: 5000 }); } catch (e) { console.log('INP klik', name, sel, 'napaka', e.message.slice(0, 60)); }
          await p.waitForTimeout(1200);
        }
        const w = worstInteraction(await p.evaluate(() => window.__ev));
        if (!Number.isNaN(w)) inp[name].push(w);
      } catch (e) { console.log('INP', name, 'napaka', e.message.slice(0, 80)); }
      await ctx.close();
    }
  }
  await b.close();

  const fails = evaluate({ cls, overflow, axe: axeRes, inp });
  const lines = [`# Čuvaj videza žive strani (${BASE})`, '',
    `CLS (mediana ${RUNS} tekov, meja ${CLS_MAX}): telefon ${median(cls.mobile).toFixed(3)} [${cls.mobile.map(x => x.toFixed(3))}], namizje ${median(cls.desktop).toFixed(3)} [${cls.desktop.map(x => x.toFixed(3))}]`,
    `Razliv pri 360 px: ${overflow.filter(o => o.sw > o.W).length} od ${overflow.length} strani`,
    `axe na hero kartici: ${axeRes.length ? axeRes.map(a => `${a.theme}:${a.id}(${a.impact})`).join(', ') : 'brez kršitev'}`,
    `Odzivnost (INP pod CPU 4×, mediana, meja ${INP_MAX} ms, CWV »slabo« nad ${INP_POOR} ms): telefon ${Math.round(median(inp.mobile))} ms [${inp.mobile.map(Math.round)}], namizje ${Math.round(median(inp.desktop))} ms [${inp.desktop.map(Math.round)}]` +
      (median(inp.mobile) > INP_POOR || median(inp.desktop) > INP_POOR ? ' (nad mejo »slabo« po CWV: opozorilo, ne napaka)' : ''), '',
    fails.length ? '## Napake\n' + fails.map(f => '- ' + f).join('\n') : 'Vse v redu.'];
  console.log(lines.join('\n'));
  if (REPORT) fs.writeFileSync(REPORT, lines.join('\n') + '\n');
  if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `fail=${fails.length}\n`);
  // čuvaj sam ne pade (issue je signal); pade samo, če ni bilo nobene meritve
  if (!cls.mobile.length && !cls.desktop.length) process.exit(2);
}

if (import.meta.url === `file://${process.argv[1]}`) main().catch(e => { console.error(e); process.exit(2); });
