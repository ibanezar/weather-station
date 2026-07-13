#!/usr/bin/env node
// Minificira app.js -> app.min.js in style.css -> style.min.css.
// app.js ostaja edini vir za urejanje; app.min.js/style.min.css sta izpeljana
// datoteki, ki ju dejansko servira index.html (statični site brez build koraka,
// zato morata biti commitana v repo — glej .github/workflows/minify-assets.yml).
//
// Pomembno: mangle NE sme uporabljati `toplevel`, ker index.html kliče
// vrsto funkcij prek inline onclick="funkcija()" — top-level imena funkcij
// morajo ostati nespremenjena.
import { minify } from 'terser';
import CleanCSS from 'clean-css';
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

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
}

function minifyCss() {
  const src = readFileSync(join(ROOT, 'style.css'), 'utf8');
  const result = new CleanCSS({}).minify(src);
  if (result.errors.length) throw new Error(result.errors.join('\n'));
  writeFileSync(join(ROOT, 'style.min.css'), result.styles);
  console.log(`style.css ${src.length} B → style.min.css ${result.styles.length} B`);
}

await minifyJs();
minifyCss();
