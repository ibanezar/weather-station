/*
 * tools/_parity_js.mjs — pomočnik za tools/test_parity.py.
 *
 * Iz izvorne datoteke (app.js, worker.js, gasilec.js ali ŽE GENERIRANE strani
 * HTML, v kateri je JS) izreže imenovane funkcije/konstante, jih izvede v
 * izoliranem vm kontekstu in vrne rezultate klicev. Tako se testira PRAVA
 * koda iz repozitorija in ne njena kopija v testu.
 *
 * stdin:  {"file": "app.js", "names": ["fnA", "CONST_B"], "prelude": "var X=1;",
 *          "calls": [{"fn": "fnA", "args": [1, 2]}, {"expr": "fnA(1,2)+3"}]}
 * stdout: {"results": [...]}   (ali {"error": "..."} z izhodom 1)
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// Najde konec bloka, ki se začne pri `open` ({ ali [ ali ( ), in preskoči
// nize ter komentarje. Regexov z oklepaji v telesu teh funkcij ni.
function matchEnd(src, open) {
  const pairs = { '{': '}', '[': ']', '(': ')' };
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    const c = src[i];
    if (c === '"' || c === "'" || c === '`') {
      const q = c; i++;
      while (i < src.length && src[i] !== q) { if (src[i] === '\\') i++; i++; }
      continue;
    }
    if (c === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i++; continue; }
    if (c === '/' && src[i + 1] === '*') { i = src.indexOf('*/', i + 2) + 1; continue; }
    if (c in pairs || c === '}' || c === ']' || c === ')') {
      if (c in pairs) depth++; else depth--;
      if (depth === 0) return i + 1;
    }
  }
  throw new Error('nezaključen blok');
}

function extract(src, name) {
  const esc = name.replace(/[$]/g, '\\$&');
  let m = new RegExp(`(?:async\\s+)?function\\s+${esc}\\s*\\(`).exec(src);
  if (m) {
    const parenOpen = src.indexOf('(', m.index + m[0].length - 1);
    const braceOpen = src.indexOf('{', matchEnd(src, parenOpen));
    return src.slice(m.index, matchEnd(src, braceOpen));
  }
  m = new RegExp(`(?:const|let|var)\\s+${esc}\\s*=`).exec(src);
  if (m) {
    let i = m.index + m[0].length;
    while (/\s/.test(src[i])) i++;
    let end;
    if ('[{('.includes(src[i])) end = matchEnd(src, i);
    else { end = src.indexOf(';', i); }
    while (src[end] !== ';' && end < src.length && /[\s]/.test(src[end])) end++;
    if (src[end] === ';') end++;
    return src.slice(m.index, end).replace(/;?$/, ';');
  }
  throw new Error(`ni najdeno: ${name}`);
}

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
try {
  const src = fs.readFileSync(path.join(ROOT, input.file), 'utf8');
  const parts = [input.prelude || ''];
  for (const n of input.names || []) parts.push(extract(src, n));
  const ctx = vm.createContext({ Math, Date, JSON, Number, String, Array, Object, isFinite, parseFloat, parseInt });
  vm.runInContext(parts.join('\n'), ctx, { timeout: 5000 });
  const results = (input.calls || []).map((c) => {
    const code = c.expr != null ? c.expr : `${c.fn}(...${JSON.stringify(c.args || [])})`;
    return JSON.parse(JSON.stringify(vm.runInContext(code, ctx, { timeout: 5000 }) ?? null));
  });
  process.stdout.write(JSON.stringify({ results }));
} catch (e) {
  process.stdout.write(JSON.stringify({ error: String(e && e.message || e) }));
  process.exit(1);
}
