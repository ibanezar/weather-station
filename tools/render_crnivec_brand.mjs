// Izriše rastrske datoteke znamke crnivec.si iz SVG v crnivec-brand/
// (te naredi tools/build_crnivec_brand.py) in jih skopira v crnivec-site/.
//
//   NODE_PATH=$(npm root -g) node tools/render_crnivec_brand.mjs
//
// Chromium namesto Pillowa/cairosvg: SVG-je riše brskalnik, torej enako kot
// na strani (paint-order, clipPath, vzorci). ICO je zapisan ročno — vsebuje
// PNG-je 16/32/48 (to podpirajo vsi brskalniki od Viste naprej).
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SRC = path.join(ROOT, "crnivec-brand");
const SITE = path.join(ROOT, "crnivec-site");

// [izvorni SVG, izhodni PNG, širina, višina]
const PNGS = [
  ["favicon.svg", "favicon-16.png", 16, 16],
  ["favicon.svg", "favicon-32.png", 32, 32],
  ["favicon.svg", "favicon-48.png", 48, 48],
  ["mark.svg", "apple-touch-icon.png", 180, 180],
  ["mark.svg", "icon-192.png", 192, 192],
  ["mark.svg", "icon-512.png", 512, 512],
  ["mark-maskable.svg", "icon-maskable-512.png", 512, 512],
  ["logo-crnivec.svg", "logo-crnivec.png", 0, 400],          // širina po razmerju
  ["fb-profile.svg", "fb-profile.png", 1080, 1080],
  ["fb-cover.svg", "fb-cover.png", 1640, 624],
];

// Na crnivec.si gredo samo ikone in logotip; FB slike ostanejo v crnivec-brand/.
// Logotip NI /logo.svg — glava strani je Meteorecova in kaže na njegov /logo.svg.
const TO_SITE = ["favicon.ico", "favicon.svg", "apple-touch-icon.png", "icon-192.png",
                 "icon-512.png", "icon-maskable-512.png", "logo-crnivec.svg", "logo-crnivec.png"];

function ico(pngs) {
  const head = Buffer.alloc(6 + 16 * pngs.length);
  head.writeUInt16LE(0, 0);
  head.writeUInt16LE(1, 2);
  head.writeUInt16LE(pngs.length, 4);
  let off = head.length;
  pngs.forEach(([size, buf], i) => {
    const e = 6 + 16 * i;
    head.writeUInt8(size >= 256 ? 0 : size, e);
    head.writeUInt8(size >= 256 ? 0 : size, e + 1);
    head.writeUInt8(0, e + 2);
    head.writeUInt8(0, e + 3);
    head.writeUInt16LE(1, e + 4);
    head.writeUInt16LE(32, e + 6);
    head.writeUInt32LE(buf.length, e + 8);
    head.writeUInt32LE(off, e + 12);
    off += buf.length;
  });
  return Buffer.concat([head, ...pngs.map(([, b]) => b)]);
}

const browser = await chromium.launch();
const page = await browser.newPage();
for (const [src, out, w0, h] of PNGS) {
  const svg = fs.readFileSync(path.join(SRC, src), "utf8");
  const [, vw, vh] = svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/).map(Number);
  const w = w0 || Math.round((h * vw) / vh);
  await page.setViewportSize({ width: w, height: h });
  const sized = svg.replace(/width="[\d.]+" height="[\d.]+"/, `width="${w}" height="${h}"`);
  await page.setContent(
    `<!doctype html><html><body style="margin:0;background:transparent">${sized}</body></html>`);
  const buf = await page.screenshot({ omitBackground: true, clip: { x: 0, y: 0, width: w, height: h } });
  fs.writeFileSync(path.join(SRC, out), buf);
  console.log(`  → crnivec-brand/${out} (${w}×${h})`);
}
await browser.close();

fs.writeFileSync(path.join(SRC, "favicon.ico"),
  ico([16, 32, 48].map((s) => [s, fs.readFileSync(path.join(SRC, `favicon-${s}.png`))])));
console.log("  → crnivec-brand/favicon.ico");

for (const f of TO_SITE) {
  fs.copyFileSync(path.join(SRC, f), path.join(SITE, f));
}
console.log(`  → crnivec-site/ (${TO_SITE.length} datotek)`);
