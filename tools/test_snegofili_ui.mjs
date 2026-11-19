// tools/test_snegofili_ui.mjs — /snegofili/ v brskalniku (ročno, ni v CI): pas »Kjer zdaj sneži«, kamerni zid in lightbox,
// podrobnost točke (grafi, primerjava, drsnik, povezava #t-<id>), Kam peljem, toplotna karta, priljubljene točke.
// Uporablja pravi snegofili/ure.json in lažne odgovore workerja (kamera ARSO = SVG). Zunanji klici so blokirani.
//   python3 -m http.server 8765 (v korenu repozitorija)
//   PW=$(npm root -g)/playwright node tools/test_snegofili_ui.mjs
import { createRequire } from 'module';
import assert from 'assert';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW || 'playwright');
const BASE = process.env.BASE || 'http://localhost:8765';
const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1023" height="520"><rect width="1023" height="520" fill="#889"/></svg>';
const b = await chromium.launch();
let n = 0; const ok = (c, m) => { assert(c, m); n++; };
for (const vp of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
  const ctx = await b.newContext({ viewport: vp }); const page = await ctx.newPage();
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/weatherireica1.filip-eremita.workers.dev/**', r => {
    const u = r.request().url();
    if (u.includes('/arso-cam?format=json')) return r.fulfill({ json: { kamera: 'Test', slika: '/arso-cam?slika=1', posnet: new Date().toISOString() }, headers: { 'access-control-allow-origin': '*' } });
    if (u.includes('slika=1')) return r.fulfill({ body: svg, contentType: 'image/svg+xml' });
    return r.fulfill({ status: 404, body: '{}' });
  });
  await page.route(/googletagmanager|google-analytics|fonts\.g|drsc\.si|embed\.windy\.com/, r => r.abort());
  await page.goto(BASE + '/snegofili/index.html'); await page.waitForSelector('.sg-nowc', { timeout: 8000 });
  const tag = vp.width + ' px: ';
  ok(await page.locator('.sg-spark svg').count() === await page.locator('.sg-card').count(), tag + 'sparkline na vsaki kartici');
  ok(await page.locator('.sg-hm-l').count() >= 30, tag + 'toplotna karta ima vrstico za vsako točko');
  ok(await page.locator('.sg-pl-i').count() === 3, tag + 'Kam peljem: tri točke');
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), tag + 'brez vodoravnega razliva');
  const nowCount = +(await page.locator('#sg-st-now').textContent());
  ok(nowCount > 0 || (await page.locator('#sg-now-row .sg-nowc').count()) === 0, tag + 'števec »sneži zdaj« se ujema s pasom');
  /* drsnik premakne pas in števec */
  await page.locator('#sg-range').fill('119'); await page.waitForTimeout(200);
  ok(await page.locator('#zs-h').textContent() === 'Kjer sneži ob izbrani uri', tag + 'naslov pasu ob drugi uri');
  await page.locator("#sg-now").click();
  /* kamera: lightbox, naslednja, Esc vrne fokus */
  await page.locator('.sg-cam-b').first().scrollIntoViewIfNeeded();
  const opener = page.locator('.sg-cam-b').first(); await opener.click(); await page.waitForSelector('.sg-lb-img');
  ok(await page.locator('.sg-lb-model').textContent().then(t => /Model ob izbrani uri/.test(t)), tag + 'lightbox pove, kaj pravi model');
  const t1 = await page.locator('#sg-lb-t, .sg-lb-hd h2').first().textContent();
  await page.getByRole('button', { name: /Naslednja/ }).click(); await page.waitForTimeout(150);
  ok(await page.locator('.sg-lb-hd h2').textContent() !== t1, tag + 'naslednja kamera');
  await page.keyboard.press('Escape');
  ok(await page.locator('.sg-modal').evaluate(e => e.hidden), tag + 'Esc zapre okno');
  ok(await page.evaluate(() => document.activeElement && document.activeElement.classList.contains('sg-cam-b')), tag + 'fokus se vrne na sprožilec');
  /* podrobnost: grafi, primerjava, povezava */
  await page.locator('.sg-hm-l').first().click(); await page.waitForSelector('.sg-ch');
  ok(/^#t-/.test(await page.evaluate(() => location.hash)), tag + 'povezava #t-id');
  ok(await page.locator('.sg-ch .bp, .sg-ch .bf').count() > 5, tag + 'graf snega ima stolpce');
  await page.locator('.sg-dt-row select').selectOption({ index: 2 });
  ok(await page.locator('.sg-ch .cmp').count() === 1, tag + 'primerjava doda črto');
  await page.locator('.sg-dt-rg').fill('100');
  ok(/čez 29 h/.test(await page.locator('.sg-dt-rd').textContent()), tag + 'drsnik v grafih bere uro');
  /* Tab ostane v oknu */
  for (let i = 0; i < 25; i++) await page.keyboard.press('Tab');
  ok(await page.evaluate(() => !!document.activeElement.closest('.sg-mp')), tag + 'fokus ostane v modalnem oknu');
  await page.keyboard.press('Escape');
  ok(await page.evaluate(() => location.hash === ''), tag + 'zaprtje počisti hash');
  /* priljubljene */
  await page.locator('.sg-card .sg-star').first().click();
  ok(await page.evaluate(() => JSON.parse(localStorage.getItem('wx-sg-fav')).length === 1), tag + 'zvezdica shrani priljubljeno');
  await page.locator('#sg-filter [data-f="fav"]').click();
  ok(await page.locator('.sg-card:not([hidden])').count() === 1, tag + 'filter »Moje točke«');
  /* Windy karta: iframe šele po kliku, plast se menja */
  ok(await page.locator('#sg-wy iframe').count() === 0, tag + 'Windy: brez iframe pred klikom');
  await page.locator('#windy .sg-heatbar button[data-ov="wind"]').click();
  await page.locator('#sg-wy .sg-live').click();
  ok((await page.locator('#sg-wy iframe').getAttribute('src')).startsWith('https://embed.windy.com/embed2.html') && (await page.locator('#sg-wy iframe').getAttribute('src')).includes('overlay=wind&'), tag + 'Windy: iframe na embed.windy.com z izbrano plastjo');
  /* globoka povezava */
  await page.goto(BASE + '/snegofili/index.html#t-kredarica'); await page.waitForSelector('.sg-dt');
  ok(await page.locator('#sg-dt-t').textContent() === 'Kredarica', tag + 'globoka povezava odpre podrobnost');
  ok(errs.length === 0, tag + 'brez napak v konzoli: ' + errs.join('; '));
  await ctx.close();
}
await b.close();
console.log('test_snegofili_ui: ' + n + ' preverjanj v redu');
