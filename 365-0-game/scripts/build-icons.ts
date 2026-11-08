// `node scripts/build-icons.ts`: renders the app icons and the link-preview image from the logo mark
// (src/brand/mark.ts). Run by hand when the mark changes; the outputs are committed. Uses the Playwright
// Chromium (set PW_CHROMIUM_PATH to a system Chromium when the Playwright download is not installed).
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from '@playwright/test';
import { BRAND, markSvg } from '../src/brand/mark.ts';

const root = join(import.meta.dirname, '..');
const pub = join(root, 'public');
const out = join(pub, 'icons');
mkdirSync(out, { recursive: true });

// Vector files: "any" is the rounded plate; the favicon is the same mark.
const rounded = markSvg({ plate: 'rounded' });
const bleed = markSvg({ plate: 'bleed' });
writeFileSync(join(out, 'icon.svg'), rounded);
writeFileSync(join(pub, 'favicon.svg'), rounded);

const font = (pkg: string, file: string): string =>
  readFileSync(join(root, 'node_modules/@fontsource-variable', pkg, 'files', file)).toString(
    'base64',
  );
const displayFont = font('big-shoulders-display', 'big-shoulders-display-latin-wght-normal.woff2');
const uiFont = font('instrument-sans', 'instrument-sans-latin-wght-normal.woff2');

/** The 1200 by 630 picture that link previews (chat apps, social posts) show. */
const preview = `<!doctype html><html><head><style>
@font-face{font-family:D;src:url(data:font/woff2;base64,${displayFont}) format('woff2');font-weight:100 900}
@font-face{font-family:U;src:url(data:font/woff2;base64,${uiFont}) format('woff2');font-weight:400 700}
html,body{margin:0}
body{width:1200px;height:630px;background:#0E1624;color:#F1F4F8;font-family:U,sans-serif;display:flex;align-items:center;gap:64px;padding:0 88px;box-sizing:border-box}
.mark{flex:none;width:380px;height:380px}
.mark svg{width:380px;height:380px;display:block}
h1{margin:0;font-family:D,sans-serif;font-weight:900;font-size:188px;line-height:.9;letter-spacing:-1px;white-space:nowrap}
p{margin:0}
.tag{font-size:44px;font-weight:650;margin-top:22px}
.sub{font-size:28px;color:#A9B6C6;margin-top:14px;line-height:1.3}
.legend{display:flex;gap:22px;margin-top:28px;font-size:26px;color:#D6DEE8}
.legend span{display:flex;align-items:center;gap:12px}
.legend i{display:block;width:34px;height:24px;border-radius:6px}
</style></head><body>
<div class="mark">${markSvg({ plate: 'rounded' })}</div>
<div>
<h1>365-0</h1>
<p class="tag">Plan a year of the weather you want.</p>
<p class="sub">Chase sun, snow, rain, storms or heat. Pick a city for every month, then watch the real weather play out.</p>
<div class="legend"><span><i style="background:${BRAND.gold}"></i>Sun</span><span><i style="background:#A2EDF6"></i>Snow</span><span><i style="background:#316EDC"></i>Rain</span><span><i style="background:#C082EB"></i>Storms</span><span><i style="background:#EF512C"></i>Heat</span></div>
</div>
</body></html>`;

const browser = await chromium.launch({
  args: ['--no-sandbox'],
  ...(process.env['PW_CHROMIUM_PATH'] ? { executablePath: process.env['PW_CHROMIUM_PATH'] } : {}),
});
const page = await browser.newPage();
const render = async (source: string, size: number, file: string): Promise<void> => {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(
    `<style>html,body{margin:0;background:transparent}svg{display:block;width:${String(size)}px;height:${String(size)}px}</style>${source}`,
  );
  await page.screenshot({ path: join(out, file), omitBackground: true });
};
await render(rounded, 192, 'icon-192.png');
await render(rounded, 512, 'icon-512.png');
await render(bleed, 512, 'icon-maskable-512.png');
await render(bleed, 180, 'apple-touch-icon.png');
await render(rounded, 32, 'favicon-32.png');

await page.setViewportSize({ width: 1200, height: 630 });
await page.setContent(preview);
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: join(pub, 'og.png') });
await browser.close();
console.log('icons written to public/icons, preview to public/og.png');
