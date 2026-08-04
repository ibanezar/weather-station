#!/usr/bin/env node
// Minificira app.js -> app.min.js in style.css -> style.min.css.
// app.js ostaja edini vir za urejanje; app.min.js/style.min.css sta izpeljana
// datoteki, ki ju dejansko servira index.html (statični site brez build koraka,
// zato morata biti commitana v repo — glej .github/workflows/minify-assets.yml).
//
// Pomembno: mangle NE sme uporabljati `toplevel`, ker index.html kliče
// vrsto funkcij prek inline onclick="funkcija()" — top-level imena funkcij
// morajo ostati nespremenjena.
//
// Cache-busting: index.html referencira obe izhodni datoteki z `?v=<hash8>`
// (hash vsebine, ne verzija paketa), ki ga ta skripta po vsakem minificiranju
// vpiše nazaj v index.html. Tako lahko Cloudflare Cache Rule cachira
// style.min.css/app.min.js z zelo dolgim TTL-jem brez tveganja, da obiskovalec
// po objavi spremembe še dolgo dobiva staro verzijo — nova vsebina dobi nov
// query string in torej nov cache key.
import { minify } from 'terser';
import CleanCSS from 'clean-css';
import { createHash } from 'crypto';
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

function hash8(content) {
  return createHash('sha256').update(content).digest('hex').slice(0, 8);
}

async function minifyJs() {
  const src = readFileSync(join(ROOT, 'app.js'), 'utf8');
  const result = await minify(src, {
    compress: true,
    mangle: { toplevel: false },
    format: { comments: false },
  });
  if (result.error) throw result.error;
  writeFileSync(join(ROOT, 'app.min.js'), result.code);
  console.log(`app.js ${src.length} B → app.min.js ${result.code.length} B`);
  return hash8(result.code);
}

function minifyCss() {
  const src = readFileSync(join(ROOT, 'style.css'), 'utf8');
  const result = new CleanCSS({}).minify(src);
  if (result.errors.length) throw new Error(result.errors.join('\n'));
  writeFileSync(join(ROOT, 'style.min.css'), result.styles);
  console.log(`style.css ${src.length} B → style.min.css ${result.styles.length} B`);
  return hash8(result.styles);
}

function patchIndexHtml(jsHash, cssHash) {
  const file = join(ROOT, 'index.html');
  let html = readFileSync(file, 'utf8');
  const before = html;
  html = html.replace(
    /href="(\/style\.min\.css)(\?v=[0-9a-f]+)?"/,
    `href="$1?v=${cssHash}"`
  );
  html = html.replace(
    /src="(app\.min\.js)(\?v=[0-9a-f]+)?"/,
    `src="$1?v=${jsHash}"`
  );
  if (html !== before) {
    writeFileSync(file, html);
    console.log(`index.html: posodobljena ?v= za style.min.css/app.min.js.`);
  }
}

const jsHash = await minifyJs();
const cssHash = minifyCss();
patchIndexHtml(jsHash, cssHash);
