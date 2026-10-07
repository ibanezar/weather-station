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
import { parse as acornParse } from 'acorn';
import CleanCSS from 'clean-css';
import { createHash } from 'crypto';
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

function hash8(content) {
  return createHash('sha256').update(content).digest('hex').slice(0, 8);
}

// ── Razrez app.js na jedro + leni paket ──────────────────────────────────────
// Oznaka `// @@LAZY-PACK` na začetku vrstice loči jedro (app.min.js) od lenega paketa (app-lazy.min.js, do konca
// datoteke). Paket se naloži šele ob prvi uporabi (glej _lazyStubs v app.js), zato mora veljati:
//   1. v paketu so samo deklaracije (funkcije, let/const/var, class) — nič, kar bi se izvedlo ob nalaganju;
//   2. jedro in index.html kličeta/navajata iz paketa samo FUNKCIJE (za nje build zapiše nadomestke); če jedro
//      bere spremenljivko iz paketa, build javi napako — brez nadomestka bi bila ob nenaloženem paketu prazna.
// Preverjanje je razčlenjevanje (acorn), ne iskanje po besedilu: komentarji in imena lastnosti ne štejejo.
const LAZY_MARK = /^\/\/ @@LAZY-PACK\b/m;

function declaredNames(node) {
  const out = [];
  const pat = p => {
    if (!p) return;
    if (p.type === 'Identifier') out.push(p.name);
    else if (p.type === 'ObjectPattern') p.properties.forEach(x => pat(x.value || x.argument));
    else if (p.type === 'ArrayPattern') p.elements.forEach(pat);
    else if (p.type === 'AssignmentPattern') pat(p.left);
    else if (p.type === 'RestElement') pat(p.argument);
  };
  if (node.type === 'FunctionDeclaration' || node.type === 'ClassDeclaration') out.push(node.id.name);
  else if (node.type === 'VariableDeclaration') node.declarations.forEach(d => pat(d.id));
  return out;
}

// Vsa imena iz `names`, ki jih koda `ast` dejansko uporablja kot spremenljivke (Identifier, ne ime lastnosti) ali
// ki so v nizih/predlogah kot klic (`ime(`) — to ujame onclick="ime()" v HTML, ki ga sestavi JS.
function referencedNames(ast, source, names) {
  const hit = new Set();
  (function walk(n, parent, key) {
    if (!n || typeof n.type !== 'string') return;
    if (n.type === 'Identifier') {
      const isProp = parent && ((parent.type === 'MemberExpression' && key === 'property' && !parent.computed)
        || (parent.type === 'Property' && key === 'key' && !parent.computed && !parent.shorthand)
        || (parent.type === 'MethodDefinition' && key === 'key' && !parent.computed));
      if (!isProp && names.has(n.name)) hit.add(n.name);
    } else if ((n.type === 'Literal' && typeof n.value === 'string') || n.type === 'TemplateElement') {
      const text = n.type === 'Literal' ? n.value : n.value.cooked || n.value.raw;
      for (const m of text.matchAll(/([A-Za-z_$][\w$]*)\s*\(/g)) if (names.has(m[1])) hit.add(m[1]);
    }
    for (const k of Object.keys(n)) {
      const v = n[k];
      if (Array.isArray(v)) v.forEach(c => walk(c, n, k));
      else if (v && typeof v.type === 'string') walk(v, n, k);
    }
  })(ast, null, null);
  return hit;
}

function splitLazy(src) {
  const m = LAZY_MARK.exec(src);
  if (!m) return { head: src, tail: null, stubs: [] };
  const head = src.slice(0, m.index);
  const tail = src.slice(m.index);
  const headAst = acornParse(head, { ecmaVersion: 'latest', sourceType: 'script' });
  const tailAst = acornParse(tail, { ecmaVersion: 'latest', sourceType: 'script' });
  const tailNames = new Map(); // ime → vrsta deklaracije
  for (const st of tailAst.body) {
    const names = declaredNames(st);
    if (!names.length) {
      throw new Error(`Leni paket: stavek tipa ${st.type} na mestu ${st.start} se ne sme izvesti ob nalaganju — premakni ga v jedro ali v funkcijo.`);
    }
    names.forEach(nm => tailNames.set(nm, st.type));
  }
  const nameSet = new Set(tailNames.keys());
  const used = referencedNames(headAst, head, nameSet);
  const html = readFileSync(join(ROOT, 'index.html'), 'utf8');
  // Inline obravnavalci (onclick="…") in vgrajene skripte v index.html.
  for (const mm of html.matchAll(/\bon[a-z]+="([^"]*)"/g)) for (const w of mm[1].matchAll(/[A-Za-z_$][\w$]*/g)) if (nameSet.has(w[0])) used.add(w[0]);
  for (const mm of html.matchAll(/<script(?![^>]*\bsrc\b)[^>]*>([\s\S]*?)<\/script>/g)) {
    try { referencedNames(acornParse(mm[1], { ecmaVersion: 'latest', sourceType: 'script' }), mm[1], nameSet).forEach(x => used.add(x)); } catch (_) { /* ni JS (JSON-LD) */ }
  }
  const stubs = [];
  for (const nm of [...used].sort()) {
    if (tailNames.get(nm) !== 'FunctionDeclaration') {
      throw new Error(`Leni paket: jedro uporablja »${nm}« (${tailNames.get(nm)}), ki je v paketu — nadomestek je mogoč samo za funkcije. Premakni deklaracijo v jedro.`);
    }
    stubs.push(nm);
  }
  return { head, tail, stubs };
}

async function minifyJs() {
  const src = readFileSync(join(ROOT, 'app.js'), 'utf8');
  const opts = { compress: true, mangle: { toplevel: false }, format: { comments: false } };
  const { head, tail, stubs } = splitLazy(src);
  const mainMin = await minify(head, opts);
  if (mainMin.error) throw mainMin.error;
  let code = mainMin.code;
  if (tail) {
    const lazyMin = await minify(tail, opts);
    if (lazyMin.error) throw lazyMin.error;
    writeFileSync(join(ROOT, 'app-lazy.min.js'), lazyMin.code);
    const lazyHash = hash8(lazyMin.code);
    // Klic je v jedru (ne v index.html), zato hash jedra krije tudi hash paketa. Stoji NA ZAČETKU: jedro sme ob
    // nalaganju že vzeti referenco na funkcijo paketa (npr. { init: initGlossary }) — nadomestek mora takrat obstajati.
    code = `_lazyStubs("/app-lazy.min.js?v=${lazyHash}",${JSON.stringify(stubs)});` + code;
    console.log(`app-lazy.min.js ${lazyMin.code.length} B (${stubs.length} nadomestkov: ${stubs.join(', ')})`);
  }
  writeFileSync(join(ROOT, 'app.min.js'), code);
  console.log(`app.js ${src.length} B → app.min.js ${code.length} B`);
  return hash8(code);
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
    /href="(\/style\.min\.css)(\?v=[0-9a-f]+)?"/g,
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
