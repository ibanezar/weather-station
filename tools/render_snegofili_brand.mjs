// Izriše PNG znamke /snegofili/ iz SVG v snegofili/brand/ (te naredi tools/build_snegofili_brand.py).
//   NODE_PATH=$(npm root -g) node tools/render_snegofili_brand.mjs
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const DIR = path.join(ROOT, "snegofili", "brand");

// [izvor, izhod, širina, višina (0 = po razmerju)]
const PNGS = [
  ["favicon.svg", "favicon-32.png", 32, 32],
  ["favicon.svg", "favicon-48.png", 48, 48],
  ["mark.svg", "apple-touch-icon.png", 180, 180],
  ["mark.svg", "icon-192.png", 192, 192],
  ["mark.svg", "icon-512.png", 512, 512],
  ["mark-maskable.svg", "icon-maskable-512.png", 512, 512],
  ["logo-snegofili.svg", "logo-snegofili.png", 0, 240],
  ["og.svg", "og.png", 1200, 630],
];

const browser = await chromium.launch();
for (const [src, out, w, h] of PNGS) {
  const svg = fs.readFileSync(path.join(DIR, src), "utf8");
  const m = /viewBox="0 0 ([\d.]+) ([\d.]+)"/.exec(svg);
  const vw = +m[1], vh = +m[2];
  const W = w || Math.round(h * vw / vh), H = h || Math.round(w * vh / vw);
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.setContent(`<body style="margin:0;background:transparent">` +
    svg.replace(/width="\d+" height="\d+"/, `width="${W}" height="${H}"`) + `</body>`);
  await page.screenshot({ path: path.join(DIR, out), omitBackground: true });
  await page.close();
  console.log("  →", path.relative(ROOT, path.join(DIR, out)));
}
await browser.close();
