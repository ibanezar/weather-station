/* vodostaj-savinje/reka.js — »živa struga« (hero) in »merilna lata« za /vodostaj-savinje/.
 *
 * ROČNO pisana datoteka (ni generirana). Prikaz, ne simulacija: hitrost delcev in višina vode na sliki
 * sta ocena iz IZMERJENEGA pretoka ARSO (ne izmerjena hitrost vode, ne izmerjena globina).
 *
 * Ocena stanja (THRESH, cardLevel, cardLabel) je namerna podvojitev tools/generate_vodostaj_page.py
 * (station_level / card_level / card_label); test_parity.vodostaj_reka ju primerja na istih vhodih.
 * Zato so te funkcije na vrhu, brez odvisnosti od DOM-a.
 *
 * Podatki: vgrajen posnetek (#vod-data, ob generiranju strani) + živ klic /arso-water?pritoki=1
 * (rob 5 min; klic ob nalaganju in nato največ na 5 min, samo ko je zavihek viden).
 * Ob nedosegljivem viru ali meritvi starejši od STALE_MIN se voda NE premika (raje stoječa voda
 * kot izmišljen tok).
 */

// ── Ocena stanja (usklajeno s Pythonom) ─────────────────────────────────────
const THRESH = { raised: 80, warning: 200, alarm: 400 };
const LV_COLORS = ['#059669', '#f59e0b', '#fb923c', '#ef4444'];
const LV_LABELS = ['Normalno', 'Povečano', 'Opozorilo', 'Alarm'];
const NEUTRAL = '#94a3b8';

function stationLevel(q, p) {
  if (q == null) return null;
  const vv1 = p.vv1 == null ? null : p.vv1, vv2 = p.vv2 == null ? null : p.vv2, vv3 = p.vv3 == null ? null : p.vv3;
  if (vv1 !== null) {
    if (vv3 !== null && q >= vv3) return 3;
    if (vv2 !== null && q >= vv2) return 2;
    return q >= vv1 ? 1 : 0;
  }
  if (q >= THRESH.alarm) return 3;
  if (q >= THRESH.warning) return 2;
  return q >= THRESH.raised ? 1 : 0;
}

function stationStatus(q, p) {
  const lvl = stationLevel(q, p);
  if (lvl === null) return '—';
  if (p.vv1 != null) {
    if (lvl) return lvl + '. prag ARSO';
    const zn = p.znacilni;
    return zn ? zn.charAt(0).toUpperCase() + zn.slice(1) : 'Pod pragom';
  }
  return ['Normalen (ocena)', 'Povečan (ocena)', 'Opozorilo (ocena)', 'Alarm (ocena)'][lvl];
}

// Pritok brez pragov ARSO ostane neocenjen (enotni približek je umerjen na Letuš).
function cardLevel(p) {
  if (p.pretok == null) return null;
  if (p.vv1 == null && p.sav === false) return null;
  return stationLevel(p.pretok, p);
}

function cardLabel(p) {
  if (cardLevel(p) !== null) return stationStatus(p.pretok, p);
  if (p.pretok == null) return 'Pretok ni merjen';
  const zn = p.znacilni;
  return zn ? zn.charAt(0).toUpperCase() + zn.slice(1) : 'Brez pragov ARSO';
}

function cardColor(p) {
  const l = cardLevel(p);
  return l === null ? NEUTRAL : LV_COLORS[l];
}

// ── Vse spodaj je v IIFE (ne onesnažuje globalnega imenskega prostora) ─────
(function () {
// ── Pomožne funkcije ────────────────────────────────────────────────────────
const VOD_PROXY = 'https://weatherireica1.filip-eremita.workers.dev';
const STALE_MIN = 120;          // starejša meritev: voda stoji
const REFRESH_MS = 5 * 60 * 1000;
const FPS = 30;

function vFmt(x, d) { return x == null ? '—' : Number(x).toFixed(d).replace('.', ','); }
function shortName(p) { const i = p.name.indexOf(' - '); return i >= 0 ? p.name.slice(i + 3).trim() : p.name; }
function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
function flowNorm(q) { return q == null ? 0 : clamp01(Math.log10(1 + q) / Math.log10(1 + 500)); }

// ARSO »2026-11-13 15:30« je lokalni čas (Ljubljana). Vrne starost v minutah ali null.
function ageMin(datum) {
  const m = /^(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d)/.exec(datum || '');
  if (!m) return null;
  let off = '+01:00';
  try {
    const part = new Intl.DateTimeFormat('en', { timeZone: 'Europe/Ljubljana', timeZoneName: 'longOffset' })
      .formatToParts(new Date()).find(x => x.type === 'timeZoneName');
    const mm = part && /GMT([+-]\d\d):?(\d\d)?/.exec(part.value);
    if (mm) off = mm[1] + ':' + (mm[2] || '00');
  } catch (_) { /* ostane +01:00 */ }
  const t = Date.parse(m[1] + '-' + m[2] + '-' + m[3] + 'T' + m[4] + ':' + m[5] + ':00' + off);
  return isNaN(t) ? null : (Date.now() - t) / 60000;
}

function fmtMeas(datum) {
  const m = /^\d{4}-(\d\d)-(\d\d)[ T](\d\d):(\d\d)/.exec(datum || '');
  return m ? (+m[2]) + '. ' + (+m[1]) + '. ob ' + (+m[3]) + '.' + m[4] : (datum || '—');
}

function fromWorker(f) {
  const p = f.properties || {}, c = f.geometry && f.geometry.coordinates || [null, null];
  return {
    id: p.sifra, reka: p.reka || '', name: p.postaja || p.merilno_mesto || '', lon: c[0], lat: c[1],
    vodostaj: p.vodostaj, pretok: p.pretok, temp: p.temperatura, datum: p.datum || '',
    vv1: p.vv1, vv2: p.vv2, vv3: p.vv3, znacilni: p.znacilni || null,
    sav: /savinj/i.test(p.reka || ''),
  };
}

// Rekord iz zgodovine poplav velja samo za Letuš (vršni pretok avgusta 2023).
function recordFor(p) { return /Letu/i.test(p.name) ? { q: 1100, label: 'Avgust 2023' } : null; }

// ── Stanje ──────────────────────────────────────────────────────────────────
const VS = { stations: [], sel: null, live: false, liveAt: null, fetchFailed: false, hero: null, lata: null, colors: null, colorsAt: 0 };

function mainStations() { return VS.stations.filter(s => s.sav).sort((a, b) => a.lon - b.lon); }
function tribStations() { return VS.stations.filter(s => !s.sav); }
function isFresh(s) { const a = ageMin(s.datum); return a !== null && a <= STALE_MIN; }

function themeColors() {
  const now = performance.now();
  if (VS.colors && now - VS.colorsAt < 1000) return VS.colors;
  const cs = getComputedStyle(document.documentElement);
  const g = (n, d) => (cs.getPropertyValue(n) || '').trim() || d;
  VS.colors = { text: g('--text', '#e5e7eb'), muted: g('--muted', '#94a3b8'), card: g('--card-bg', '#0f172a'), border: g('--card-border', 'rgba(255,255,255,.12)') };
  VS.colorsAt = now;
  return VS.colors;
}

function setupCanvas(cv, w, h) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
  cv.style.width = w + 'px'; cv.style.height = h + 'px';
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return ctx;
}

// ── Hero: živa struga ───────────────────────────────────────────────────────
const HERO_H = 410;        // enako kot .vod-live-stage v CSS generatorja (rezervirana višina, brez CLS)

function heroLayout(W) {
  const main = mainStations(), tribs = tribStations();
  const n = main.length;
  const x0 = 56, x1 = W - 165, ym = 112;
  const xs = main.map((_, i) => n > 1 ? x0 + (x1 - x0) * i / (n - 1) : (x0 + x1) / 2);
  const riverY = (x) => ym + 9 * Math.sin(x / 95) + 5 * Math.sin(x / 41 + 1.3);
  const mainX = (lon) => {
    if (!n) return x0;
    if (lon <= main[0].lon) return xs[0];
    for (let i = 0; i < n - 1; i++) {
      const a = main[i].lon, b = main[i + 1].lon;
      if (lon >= a && lon <= b) return xs[i] + (xs[i + 1] - xs[i]) * (b > a ? (lon - a) / (b - a) : 0);
    }
    return xs[n - 1];
  };
  // pritoki: od desne proti levi, vsak za vrstico globlje od bližnjih desnih (veje se ne križajo z oznakami)
  const LABEL_W = 135, ROW_H = 44;
  const list = tribs.map(t => ({ t, x: mainX(t.lon) })).sort((a, b) => b.x - a.x);
  const placed = [];
  for (const it of list) {
    const near = placed.filter(p => p.x - it.x >= 0 && p.x - it.x < LABEL_W + 14).map(p => p.row);
    it.row = near.length ? Math.max(...near) + 1 : 0;
    placed.push(it);
  }
  const maxRow = placed.length ? Math.max(...placed.map(p => p.row)) : 0;
  const rowH = maxRow ? Math.min(ROW_H, (HERO_H - ym - 88 - 34) / maxRow) : ROW_H;
  for (const it of list) it.y = ym + 88 + it.row * rowH;
  return { main, tribs: list, xs, riverY, ym, W };
}

function heroInit(stage) {
  const cv = document.createElement('canvas');
  cv.className = 'vod-live-cv';
  cv.setAttribute('role', 'img');
  cv.setAttribute('aria-label', 'Animirana shema Savinje in pritokov: hitrost toka sledi izmerjenemu pretoku na ' + VS.stations.length + ' postajah ARSO. Številke so v tabeli spodaj.');
  stage.appendChild(cv);
  const H = { cv, ctx: null, W: 0, lay: null, parts: [], t0: performance.now(), hover: null, lastSz: 0 };
  VS.hero = H;
  heroResize();
  cv.addEventListener('pointermove', (e) => {
    const r = cv.getBoundingClientRect();
    H.hover = heroHit(e.clientX - r.left, e.clientY - r.top);
    cv.style.cursor = H.hover ? 'pointer' : 'default';
    if (VS.reduced) drawAll(true);
  });
  cv.addEventListener('pointerleave', () => { H.hover = null; });
  cv.addEventListener('click', (e) => {
    const r = cv.getBoundingClientRect();
    const hit = heroHit(e.clientX - r.left, e.clientY - r.top);
    if (hit) selectStation(hit.id, true);
  });
  stage.classList.add('is-live');
}

function heroResize() {
  const H = VS.hero; if (!H) return;
  const stage = H.cv.parentElement;
  const W = Math.max(stage.clientWidth, 660);
  if (W === H.W && H.lay) return;
  H.W = W; H.ctx = setupCanvas(H.cv, W, HERO_H); H.lay = heroLayout(W);
  const n = Math.round(W / 5);
  H.parts = [];
  for (let i = 0; i < n; i++) H.parts.push({ x: Math.random() * W, lane: Math.random() * 2 - 1, k: 0.7 + Math.random() * 0.6, len: 8 + Math.random() * 14 });
  H.tp = [];
  for (const it of H.lay.tribs) for (let i = 0; i < 7; i++) H.tp.push({ it, u: Math.random(), k: 0.7 + Math.random() * 0.6 });
}

function heroHit(px, py) {
  const H = VS.hero; if (!H || !H.lay) return null;
  const L = H.lay;
  for (let i = 0; i < L.main.length; i++) {
    const sx = L.xs[i], sy = L.riverY(sx);
    if (Math.hypot(px - sx, py - sy) < 18) return L.main[i];
  }
  for (const it of L.tribs) if (Math.hypot(px - it.x, py - it.y) < 14) return it.t;
  return null;
}

// tok (px/s) in širina struge v točki x iz pretokov postaj (log lestvica, interpolacija)
function flowAt(L, x) {
  const pts = [];
  L.main.forEach((s, i) => { if (s.pretok != null && isFresh(s)) pts.push([L.xs[i], flowNorm(s.pretok)]); });
  if (!pts.length) return null;
  if (x <= pts[0][0]) return pts[0][1];
  for (let i = 0; i < pts.length - 1; i++) if (x <= pts[i + 1][0]) {
    const a = pts[i], b = pts[i + 1], u = (x - a[0]) / (b[0] - a[0] || 1);
    return a[1] + (b[1] - a[1]) * u;
  }
  return pts[pts.length - 1][1];
}

function plate(ctx, text, x, y, color, bg) {
  const w = ctx.measureText(text).width + 8;
  ctx.fillStyle = bg; ctx.globalAlpha = 0.82;
  ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x - w / 2, y - 12, w, 17, 5) : ctx.rect(x - w / 2, y - 12, w, 17);
  ctx.fill(); ctx.globalAlpha = 1;
  ctx.fillStyle = color; ctx.fillText(text, x, y);
}

function heroDraw(t, dt, animate) {
  const H = VS.hero; if (!H || !H.ctx || !H.lay) return;
  const ctx = H.ctx, L = H.lay, W = H.W, C = themeColors();
  ctx.clearRect(0, 0, W, HERO_H);
  const anyFlow = L.main.some(s => s.pretok != null && isFresh(s));
  const sec = t / 1000;

  // struga: bregova, voda, bleščeče črte
  const xsamp = []; for (let x = -12; x <= W + 12; x += 6) xsamp.push(x);
  const widths = xsamp.map(x => { const f = flowAt(L, x); return 5 + 13 * (f == null ? 0.25 : f); });
  const bank = (extra, style) => {
    ctx.beginPath();
    xsamp.forEach((x, i) => ctx.lineTo(x, L.riverY(x) - widths[i] - extra));
    for (let i = xsamp.length - 1; i >= 0; i--) ctx.lineTo(xsamp[i], L.riverY(xsamp[i]) + widths[i] + extra);
    ctx.closePath(); ctx.fillStyle = style; ctx.fill();
  };
  bank(6, 'rgba(34,197,94,.10)');                       // breg
  const g = ctx.createLinearGradient(0, 0, W, 0);
  g.addColorStop(0, '#38bdf8'); g.addColorStop(1, '#1d4ed8');
  bank(0, g);
  // tok: črtkane svetle črte, ki se premikajo (hitrost po srednjem pretoku)
  const meanF = (() => { const a = L.main.filter(s => s.pretok != null && isFresh(s)).map(s => flowNorm(s.pretok)); return a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0; })();
  const spd = anyFlow ? 18 + 90 * meanF : 0;
  for (const [lane, dash, alpha] of [[-0.45, [16, 26], .22], [0.1, [9, 19], .18], [0.55, [22, 30], .16]]) {
    ctx.beginPath();
    xsamp.forEach((x, i) => ctx.lineTo(x, L.riverY(x) + lane * widths[i]));
    ctx.setLineDash(dash); ctx.lineDashOffset = -sec * spd * (1 + lane * 0.3);
    ctx.strokeStyle = 'rgba(255,255,255,' + alpha + ')'; ctx.lineWidth = 1.6; ctx.stroke();
  }
  ctx.setLineDash([]);

  // delci
  if (anyFlow && animate) {
    for (const p of H.parts) {
      const f = flowAt(L, p.x); const v = (14 + 95 * (f == null ? 0.2 : f)) * p.k;
      p.x += v * dt; if (p.x > W + 20) { p.x = -20; p.lane = Math.random() * 2 - 1; }
    }
  }
  ctx.lineCap = 'round';
  for (const p of H.parts) {
    const f = flowAt(L, p.x); const w = 5 + 13 * (f == null ? 0.25 : f);
    const y = L.riverY(p.x) + p.lane * w * 0.85;
    const len = p.len * (0.5 + (f || 0.2));
    ctx.beginPath(); ctx.moveTo(p.x, y); ctx.lineTo(p.x - len, L.riverY(p.x - len) + p.lane * w * 0.85);
    ctx.strokeStyle = 'rgba(255,255,255,' + (0.18 + 0.4 * (f || 0.2)) + ')'; ctx.lineWidth = 1.1; ctx.stroke();
  }

  // pritoki
  for (const it of L.tribs) {
    const t = it.t, f = flowNorm(t.pretok), fresh = isFresh(t) && t.pretok != null;
    const jy = L.riverY(it.x), w = 2 + 6 * (fresh ? f : 0.3);
    ctx.beginPath(); ctx.moveTo(it.x, it.y - 8); ctx.lineTo(it.x, jy + 4);
    ctx.strokeStyle = 'rgba(56,189,248,.8)'; ctx.lineWidth = w; ctx.lineCap = 'round'; ctx.stroke();
    // ovinek ob sotočju
    if (fresh) {
      const rr = 6 + 4 * ((sec * 0.6 + it.x * 0.01) % 1);
      ctx.beginPath(); ctx.arc(it.x, jy, rr, 0, 6.2832);
      ctx.strokeStyle = 'rgba(255,255,255,' + (0.35 * (1 - (rr - 6) / 4)) + ')'; ctx.lineWidth = 1; ctx.stroke();
    }
  }
  if (animate) for (const q of H.tp) { const f = flowNorm(q.it.t.pretok); if (!isFresh(q.it.t) || q.it.t.pretok == null) continue; q.u -= dt * (0.25 + 0.9 * f) * q.k / ((q.it.y - L.riverY(q.it.x)) / 60 || 1); if (q.u < 0) q.u = 1; }
  for (const q of H.tp) {
    const it = q.it; if (!isFresh(it.t) || it.t.pretok == null) continue;
    const y = L.riverY(it.x) + 4 + (it.y - 8 - L.riverY(it.x) - 4) * q.u;
    ctx.beginPath(); ctx.arc(it.x + Math.sin(q.u * 9 + it.x) * 1.2, y, 1.6, 0, 6.2832);
    ctx.fillStyle = 'rgba(255,255,255,.7)'; ctx.fill();
  }

  // postaje na glavni strugi
  ctx.textAlign = 'center';
  L.main.forEach((s, i) => {
    const sx = L.xs[i], base = L.riverY(sx), bob = Math.sin(sec * 1.4 + i * 1.7) * (anyFlow ? 2 : 0), sy = base + bob;
    const c = isFresh(s) ? cardColor(s) : NEUTRAL;
    const sel = VS.sel === s.id, hov = H.hover && H.hover.id === s.id;
    // krožni val
    const ph = ((sec * 0.45 + i * 0.23) % 1);
    if (isFresh(s)) {
      ctx.beginPath(); ctx.arc(sx, sy, 13 + ph * 17, 0, 6.2832);
      ctx.strokeStyle = c; ctx.globalAlpha = (1 - ph) * 0.5; ctx.lineWidth = 2; ctx.stroke(); ctx.globalAlpha = 1;
    }
    ctx.beginPath(); ctx.arc(sx, sy, sel || hov ? 15 : 13, 0, 6.2832);
    ctx.fillStyle = c; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = C.card; ctx.stroke();
    ctx.beginPath(); ctx.arc(sx, sy, 4.5, 0, 6.2832); ctx.fillStyle = 'rgba(255,255,255,.92)'; ctx.fill();
    if (sel) { ctx.beginPath(); ctx.arc(sx, sy, 21, 0, 6.2832); ctx.strokeStyle = C.text; ctx.lineWidth = 1.5; ctx.setLineDash([3, 4]); ctx.stroke(); ctx.setLineDash([]); }
    const top = s.pretok != null ? vFmt(s.pretok, s.pretok < 10 ? 1 : 0) : (s.vodostaj != null ? vFmt(s.vodostaj, 0) + ' cm' : '—');
    ctx.font = '800 15px Inter, system-ui, sans-serif'; ctx.fillStyle = C.text; ctx.fillText(top, sx, base - 28);
    if (s.pretok != null) { ctx.font = '600 9.5px Inter, system-ui, sans-serif'; ctx.fillStyle = C.muted; ctx.fillText('m³/s', sx, base - 43); }
    ctx.font = '600 11.5px Inter, system-ui, sans-serif'; plate(ctx, shortName(s), sx, base + 38, C.text, C.card);
  });
  // pritoki: vozlišča in oznake
  ctx.textAlign = 'left';
  for (const it of L.tribs) {
    const t = it.t, c = isFresh(t) ? cardColor(t) : NEUTRAL, sel = VS.sel === t.id, hov = H.hover && H.hover.id === t.id;
    ctx.beginPath(); ctx.arc(it.x, it.y, sel || hov ? 9.5 : 8, 0, 6.2832);
    ctx.fillStyle = c; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = C.card; ctx.stroke();
    if (sel) { ctx.beginPath(); ctx.arc(it.x, it.y, 14, 0, 6.2832); ctx.strokeStyle = C.text; ctx.lineWidth = 1.5; ctx.setLineDash([3, 4]); ctx.stroke(); ctx.setLineDash([]); }
    const val = t.pretok != null ? vFmt(t.pretok, 1) + ' m³/s' : (t.vodostaj != null ? vFmt(t.vodostaj, 0) + ' cm' : '—');
    ctx.font = '700 11.5px Inter, system-ui, sans-serif'; ctx.fillStyle = C.text; ctx.fillText(shortName(t), it.x + 14, it.y - 1);
    ctx.font = '500 10.5px Inter, system-ui, sans-serif'; ctx.fillStyle = C.muted; ctx.fillText(t.reka + ' · ' + val, it.x + 14, it.y + 12);
  }
  ctx.textAlign = 'center';
  ctx.font = '500 10px Inter, system-ui, sans-serif'; ctx.fillStyle = C.muted;
  ctx.textAlign = 'left'; ctx.fillText('← gorvodno', 8, 20);
  ctx.textAlign = 'right'; ctx.fillText('dolvodno →', W - 8, 20);
}

// ── Merilna lata ────────────────────────────────────────────────────────────
const LATA_H = 340;

function lataScale(s) {
  // vrednost, ki je na sliki na vrhu lestvice (m³/s) in ali so pragovi znani
  const rec = recordFor(s);
  if (s.vv3 != null) return { max: Math.max(s.vv3 * 1.15, rec ? rec.q * 1.06 : 0), known: true };
  if (s.sav) return { max: THRESH.alarm * 1.15, known: true, approx: true };
  return { max: null, known: false };
}

function lataTargetFrac(s) {
  const sc = lataScale(s);
  if (s.pretok == null) return 0.12;
  if (!sc.known) return 0.4;                         // brez pragov višina na sliki ni primerljiva
  return clamp01(s.pretok / sc.max);
}

function lataInit(box) {
  const cv = document.createElement('canvas');
  cv.className = 'vod-lata-canvas'; cv.setAttribute('role', 'img');
  box.appendChild(cv);
  VS.lata = { cv, ctx: null, W: 0, level: null, trees: [], bub: [] };
  lataResize();
}

function lataResize() {
  const L = VS.lata; if (!L) return;
  const W = Math.max(L.cv.parentElement.clientWidth, 280);
  if (W === L.W && L.ctx) return;
  L.W = W; L.ctx = setupCanvas(L.cv, W, LATA_H);
  L.trees = [];
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 9; i++) L.trees.push({ x: rnd() * W, h: 16 + rnd() * 22, side: 0 });
  L.bub = []; for (let i = 0; i < 26; i++) L.bub.push({ x: rnd(), y: rnd(), r: 1 + rnd() * 1.6, k: 0.5 + rnd() });
}

function lataDraw(t, dt, animate) {
  const L = VS.lata, s = VS.stations.find(x => x.id === VS.sel); if (!L || !L.ctx || !s) return;
  const ctx = L.ctx, W = L.W, H = LATA_H, C = themeColors();
  ctx.clearRect(0, 0, W, H);
  const yTop = 34, yBed = H - 28, span = yBed - yTop, sc = lataScale(s);
  const target = lataTargetFrac(s);
  if (L.level == null) L.level = 0;
  L.level += (target - L.level) * (animate ? Math.min(1, dt * 2.2) : 1);
  if (Math.abs(target - L.level) < 0.0005) L.level = target;
  const yw = yBed - span * L.level;
  const yGround = yTop + 6;
  // struga: trapezni prerez
  const xl0 = W * 0.10, xl1 = W * 0.36, xr1 = W * 0.64, xr0 = W * 0.90;
  const edgeX = (y, left) => { const u = (y - yGround) / (yBed - yGround); return left ? xl0 + (xl1 - xl0) * u : xr0 - (xr0 - xr1) * u; };
  // nebo/zrak
  ctx.fillStyle = 'rgba(127,127,127,.06)'; ctx.fillRect(0, 0, W, yGround);
  // zemlja
  ctx.beginPath(); ctx.moveTo(0, yGround); ctx.lineTo(xl0, yGround); ctx.lineTo(xl1, yBed); ctx.lineTo(xr1, yBed); ctx.lineTo(xr0, yGround); ctx.lineTo(W, yGround); ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath();
  const gg = ctx.createLinearGradient(0, yGround, 0, H); gg.addColorStop(0, '#3f6212'); gg.addColorStop(0.18, '#57534e'); gg.addColorStop(1, '#292524');
  ctx.fillStyle = gg; ctx.fill();
  ctx.fillStyle = '#4d7c0f'; ctx.fillRect(0, yGround - 3, xl0, 4); ctx.fillRect(xr0, yGround - 3, W - xr0, 4);
  // drevesa
  for (const tr of L.trees) {
    if (tr.x > xl0 - 16 && tr.x < xr0 + 16) continue;
    ctx.beginPath(); ctx.moveTo(tr.x, yGround - 3 - tr.h); ctx.lineTo(tr.x - tr.h * 0.28, yGround - 3); ctx.lineTo(tr.x + tr.h * 0.28, yGround - 3); ctx.closePath();
    ctx.fillStyle = '#166534'; ctx.fill();
  }
  // voda (z valovi), izrezana na korito
  ctx.save();
  ctx.beginPath(); ctx.moveTo(xl0, yGround); ctx.lineTo(xl1, yBed); ctx.lineTo(xr1, yBed); ctx.lineTo(xr0, yGround); ctx.closePath(); ctx.clip();
  const sec = t / 1000, f = target, amp = 1.6 + 3.2 * f, spd = (s.pretok != null && isFresh(s) ? 1.2 + 2.6 * f : 0);
  ctx.beginPath(); ctx.moveTo(0, H);
  for (let x = 0; x <= W; x += 4) ctx.lineTo(x, yw + Math.sin(x / 22 - sec * spd) * amp + Math.sin(x / 9 + sec * spd * 1.7) * amp * 0.4);
  ctx.lineTo(W, H); ctx.closePath();
  const wg = ctx.createLinearGradient(0, yw, 0, yBed); wg.addColorStop(0, 'rgba(56,189,248,.92)'); wg.addColorStop(1, 'rgba(29,78,216,.95)');
  ctx.fillStyle = wg; ctx.fill();
  // mehurčki / lebdeči delci
  if (spd > 0) {
    for (const b of L.bub) {
      if (animate) { b.x += dt * 0.05 * spd * b.k; if (b.x > 1) b.x = 0; }
      const bx = xl1 + (xr1 - xl1) * 0 + b.x * W, by = yw + 8 + b.y * Math.max(0, yBed - yw - 12);
      ctx.beginPath(); ctx.arc(bx, by, b.r, 0, 6.2832); ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.fill();
    }
  }
  ctx.restore();
  // pragovi
  const yOf = (q) => yBed - span * clamp01(q / sc.max);
  ctx.font = '600 11px Inter, system-ui, sans-serif'; ctx.textBaseline = 'middle';
  if (sc.known) {
    const marks = [];
    if (s.vv1 != null) marks.push([s.vv1, 1], [s.vv2, 2], [s.vv3, 3]); else marks.push([THRESH.raised, 1], [THRESH.warning, 2], [THRESH.alarm, 3]);
    for (const [q, l] of marks) {
      if (q == null) continue;
      const y = yOf(q);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.setLineDash([6, 5]); ctx.strokeStyle = LV_COLORS[l]; ctx.globalAlpha = 0.9; ctx.lineWidth = 1.4; ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
      ctx.textAlign = 'left'; ctx.fillStyle = LV_COLORS[l];
      ctx.fillText(l + '. prag · ' + vFmt(q, 0) + ' m³/s' + (s.vv1 == null ? ' (ocena)' : ''), 8, y - 8);
    }
    const rec = recordFor(s);
    if (rec) {
      const y = yOf(rec.q);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.setLineDash([2, 5]); ctx.strokeStyle = '#ef4444'; ctx.lineWidth = 2; ctx.stroke(); ctx.setLineDash([]);
      ctx.textAlign = 'right'; ctx.fillStyle = '#ef4444'; ctx.fillText(rec.label + ' · ' + vFmt(rec.q, 0) + ' m³/s', W - 8, y - 8);
    }
  }
  // oznaka trenutne gladine
  ctx.textAlign = 'right'; ctx.fillStyle = C.text; ctx.font = '800 13px Inter, system-ui, sans-serif';
  ctx.beginPath(); ctx.moveTo(W * 0.5 - 7, yw - 14); ctx.lineTo(W * 0.5 + 7, yw - 14); ctx.lineTo(W * 0.5, yw - 4); ctx.closePath(); ctx.fillStyle = C.text; ctx.fill();
  ctx.textBaseline = 'alphabetic';
}

function lataInfo(s) {
  const el = document.getElementById('vod-lata-info'); if (!el) return;
  const c = cardColor(s), fresh = isFresh(s), a = ageMin(s.datum);
  const approx = (s.vv1 == null);
  const note = !(s.vv3 != null || s.sav)
    ? 'ARSO za to postajo ne objavlja pragov visokih voda: višina vode na sliki ni primerljiva z drugimi postajami.'
    : 'Višina vode na sliki je sorazmerna s pretokom do tretjega praga ARSO (ne s centimetri vodostaja; razmerje med njima ni premo).' + (approx ? ' Pragovi so enotni približek, umerjen na Letuš.' : '');
  el.innerHTML =
    '<div class="vod-eyebrow"></div><h3></h3><div class="vod-q"></div><span class="vod-pill"></span><div class="vod-facts"></div><p class="vod-note"></p><p class="vod-note vod-stale"></p>';
  el.querySelector('.vod-eyebrow').textContent = s.reka;
  el.querySelector('h3').textContent = shortName(s);
  const q = el.querySelector('.vod-q');
  q.textContent = s.pretok != null ? vFmt(s.pretok, 1) : (s.vodostaj != null ? vFmt(s.vodostaj, 0) : '—');
  const u = document.createElement('small'); u.textContent = s.pretok != null ? ' m³/s' : ' cm'; q.appendChild(u);
  const pill = el.querySelector('.vod-pill'); pill.textContent = cardLabel(s); pill.style.setProperty('--c', c);
  const facts = [];
  if (s.pretok != null && s.vodostaj != null) facts.push('vodostaj <b>' + vFmt(s.vodostaj, 0) + ' cm</b>');
  if (s.temp != null) facts.push('voda <b>' + vFmt(s.temp, 1) + ' °C</b>');
  facts.push('meritev <b>' + fmtMeas(s.datum) + '</b>');
  el.querySelector('.vod-facts').innerHTML = facts.map(x => '<span>' + x + '</span>').join('');
  el.querySelector('.vod-note').textContent = note;
  el.querySelector('.vod-stale').textContent = fresh ? '' : (a === null ? 'Starost meritve ni znana, voda miruje.' : 'Meritev je stara ' + Math.round(a / 60 * 10) / 10 + ' h: voda na sliki miruje, dokler ne pride sveža.');
  document.querySelectorAll('#vod-lata-chips button').forEach(b => b.setAttribute('aria-selected', b.dataset.id === s.id ? 'true' : 'false'));
}

function lataChips() {
  const box = document.getElementById('vod-lata-chips'); if (!box) return;
  box.innerHTML = '';
  const add = (s) => {
    const b = document.createElement('button'); b.type = 'button'; b.dataset.id = s.id; b.setAttribute('role', 'tab');
    b.style.setProperty('--c', cardColor(s)); b.textContent = (s.sav ? '' : s.reka + ': ') + shortName(s);
    b.addEventListener('click', () => selectStation(s.id, false)); box.appendChild(b);
  };
  mainStations().forEach(add); tribStations().forEach(add);
}

function selectStation(id, scroll) {
  const s = VS.stations.find(x => x.id === id); if (!s) return;
  VS.sel = id; lataInfo(s);
  if (VS.lata) VS.lata.level = VS.lata.level == null ? 0 : VS.lata.level;
  drawAll(true);
  if (scroll) { const el = document.getElementById('vod-lata'); if (el && el.scrollIntoView) el.scrollIntoView({ behavior: VS.reduced ? 'auto' : 'smooth', block: 'center' }); }
}

// ── Zanka, podatki, zagon ───────────────────────────────────────────────────
let _last = 0, _raf = 0, _visible = { hero: true, lata: true };

function drawAll(force) {
  const now = performance.now(), dt = _last ? Math.min((now - _last) / 1000, 0.1) : 0.033;
  _last = now;
  const animate = !force && !VS.reduced;      // prisiljeno risanje (izbira, podatki) ne premakne delcev
  if (VS.hero && (_visible.hero || force)) heroDraw(now, dt, animate);
  if (VS.lata && (_visible.lata || force)) lataDraw(now, dt, animate);
}

function loop(ts) {
  _raf = 0;
  if (document.hidden || VS.reduced || !(_visible.hero || _visible.lata)) return;
  if (ts - (loop._t || 0) >= 1000 / FPS - 2) { loop._t = ts; drawAll(false); }
  _raf = requestAnimationFrame(loop);
}
function kick() { if (!_raf && !VS.reduced && !document.hidden) { _last = 0; _raf = requestAnimationFrame(loop); } }

function setStations(list, live) {
  VS.stations = list;
  if (live) { VS.live = true; VS.liveAt = new Date(); VS.fetchFailed = false; }
  if (!VS.sel || !list.some(s => s.id === VS.sel)) {
    VS.sel = (list.find(s => /Nazarje/.test(s.name)) || mainStations()[0] || list[0] || {}).id;
  }
  lataChips(); const s = VS.stations.find(x => x.id === VS.sel); if (s) lataInfo(s);
  if (VS.hero) { VS.hero.lay = null; VS.hero.W = 0; heroResize(); }
  pill(); drawAll(true); kick();
}

function pill() {
  const el = document.getElementById('vod-live-pill'); if (!el) return;
  // najsvežejša meritev med postajami (ne uspeh prenosa) odloča, ali je to »živo«
  const ages = VS.stations.map(s => ageMin(s.datum)).filter(a => a !== null);
  const best = ages.length ? Math.min.apply(null, ages) : null;
  let txt, state;
  if (VS.live && best !== null && best <= STALE_MIN) { txt = 'Živo · ARSO · osveženo ob ' + VS.liveAt.getHours() + '.' + String(VS.liveAt.getMinutes()).padStart(2, '0'); state = 'ok'; }
  else if (VS.live) { txt = 'ARSO je prenesen, a meritve so stare' + (best !== null ? ' (' + Math.round(best / 6) / 10 + ' h)' : '') + ' · voda miruje'; state = 'warn'; }
  else if (VS.fetchFailed) { txt = 'Živih podatkov ni mogoče prebrati · prikazan je dnevni posnetek' + (best !== null && best > STALE_MIN ? ', voda miruje' : ''); state = 'warn'; }
  else { txt = 'Dnevni posnetek · osvežujem …'; state = 'load'; }
  el.textContent = txt; el.dataset.state = state;
}

async function refresh() {
  try {
    const ctrl = new AbortController(); const tid = setTimeout(() => ctrl.abort(), 9000);
    const r = await fetch(VOD_PROXY + '/arso-water?pritoki=1', { signal: ctrl.signal }); clearTimeout(tid);
    if (!r.ok) throw new Error('http ' + r.status);
    const d = await r.json();
    const list = (d.stations || []).map(fromWorker).filter(s => s.id && s.lon != null);
    if (!list.length) throw new Error('prazno');
    setStations(list, true);
  } catch (_) { VS.fetchFailed = true; pill(); }
}

function vodStart() {
  const dataEl = document.getElementById('vod-data'), stage = document.getElementById('vod-live-stage'), lbox = document.getElementById('vod-lata-cv');
  if (!dataEl || !stage || !lbox) return;
  let snap = [];
  try { snap = JSON.parse(dataEl.textContent); } catch (_) { return; }
  VS.reduced = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  VS.stations = snap;
  heroInit(stage); lataInit(lbox);
  document.getElementById('vod-lata').classList.add('is-live');
  setStations(snap, false);
  const io = ('IntersectionObserver' in window) ? new IntersectionObserver((es) => {
    es.forEach(e => { if (e.target === stage) _visible.hero = e.isIntersecting; else _visible.lata = e.isIntersecting; });
    kick();
  }, { rootMargin: '80px' }) : null;
  if (io) { io.observe(stage); io.observe(lbox); }
  if ('ResizeObserver' in window) new ResizeObserver(() => { heroResize(); lataResize(); drawAll(true); }).observe(document.getElementById('vod-lata'));
  addEventListener('resize', () => { heroResize(); lataResize(); drawAll(true); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { kick(); refreshIfOld(); } });
  if (window.matchMedia) { const mq = matchMedia('(prefers-reduced-motion: reduce)'); (mq.addEventListener ? mq.addEventListener.bind(mq, 'change') : mq.addListener.bind(mq))((e) => { VS.reduced = e.matches; if (!VS.reduced) kick(); else drawAll(true); }); }
  refresh();
  setInterval(refreshIfOld, 60 * 1000);
}

function refreshIfOld() {
  if (document.hidden) return;
  if (!VS.liveAt || Date.now() - VS.liveAt.getTime() >= REFRESH_MS) refresh();
}

if (typeof document !== 'undefined') {
  const go = () => setTimeout(vodStart, 600);      // okrasno delo šele po prvem izrisu
  if (document.readyState === 'complete') go(); else addEventListener('load', go);
}
})();
