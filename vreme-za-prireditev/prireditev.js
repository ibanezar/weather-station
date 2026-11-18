/*
 * vreme-za-prireditev/prireditev.js — »Kateri datum je najboljši za poroko ali prireditev?« (ROČNO pisana datoteka, ni generirana).
 * MODEL (brez DOM-a; izvožen za Node, tools/test_prireditev.mjs): buildDays, share, exact, best, wilson.
 * PRIKAZ: obrazec in rezultati. Podatki (najvišja, najnižja temperatura, padavine po dneh postaje IREICA1) so vdelani v stran
 * (#pr-data), piše jih tools/generate_prireditev_page.py iz history.json (samo zunanja polja, brez ERA5).
 *
 * Merilo »primeren dan« = padavine pod pragom IN najvišja temperatura v obsegu IN (neobvezno) najnižja ≥ meja. Delež primernih dni
 * v oknu ±w dni okoli datuma v vseh letih meritev. To je klimatologija (kaj se je dogajalo), ne napoved.
 */
(function (root) {
  'use strict';
  var DAY = 86400000;

  // data = { start: 'YYYY-MM-DD', t: [Tmax], n: [Tmin], p: [padavine] }; manjkajoč podatek = null; vrne zemljevid ms → dan
  function buildDays(data) {
    var map = {}, t0 = Date.parse(data.start + 'T00:00:00Z');
    for (var i = 0; i < data.t.length; i++) {
      if (data.t[i] == null || data.n[i] == null || data.p[i] == null) continue;
      map[t0 + i * DAY] = { t: data.t[i], n: data.n[i], p: data.p[i] };
    }
    return map;
  }
  function years(map) {
    var s = {}; Object.keys(map).forEach(function (k) { s[new Date(+k).getUTCFullYear()] = 1; });
    return Object.keys(s).map(Number).sort();
  }
  // crit = { rain: mm (padavine pod), tmin_: najvišja od, tmax_: najvišja do, nmin: najnižja od ali null }
  function ok(d, c) {
    return d.p < c.rain && d.t >= c.tmaxLo && d.t <= c.tmaxHi && (c.nmin == null || d.n >= c.nmin);
  }
  function wilson(k, n, z) {                      // Wilsonov interval za delež; dnevi v oknu so soodvisni, zato je OPTIMISTIČEN
    if (!n) return [null, null];
    z = z || 1.645; var p = k / n, d = 1 + z * z / n;
    var c = p + z * z / (2 * n), h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n));
    return [Math.max(0, (c - h) / d), Math.min(1, (c + h) / d)];
  }
  // delež primernih dni v oknu ±w okoli (m, d) po vseh letih; leto, kjer datum ne obstaja (29. 2.), se izpusti
  function share(map, m, d, w, crit) {
    var ys = years(map), n = 0, k = 0, per = [];
    ys.forEach(function (y) {
      var c = Date.UTC(y, m - 1, d);
      if (new Date(c).getUTCMonth() !== m - 1) return;
      var yn = 0, yk = 0;
      for (var o = -w; o <= w; o++) {
        var day = map[c + o * DAY];
        if (!day) continue;
        yn++; if (ok(day, crit)) yk++;
      }
      if (yn) { per.push({ y: y, n: yn, k: yk }); n += yn; k += yk; }
    });
    var ci = wilson(k, n);
    return { n: n, k: k, p: n ? k / n : null, lo: ci[0], hi: ci[1], per: per };
  }
  // točno ta datum po letih: [{y, t, n, p, ok}]
  function exact(map, m, d, crit) {
    var out = [];
    years(map).forEach(function (y) {
      var c = Date.UTC(y, m - 1, d); if (new Date(c).getUTCMonth() !== m - 1) return;
      var day = map[c]; if (day) out.push({ y: y, t: day.t, n: day.n, p: day.p, ok: ok(day, crit) });
    });
    return out;
  }
  // najboljši datumi v ±range dneh od (m, d) (referenčno neprestopno leto 2027); pri izenačenju bližji izbranemu
  function best(map, m, d, range, w, crit, top) {
    var base = Date.UTC(2027, m - 1, d), list = [];
    for (var o = -range; o <= range; o++) {
      var dt = new Date(base + o * DAY), s = share(map, dt.getUTCMonth() + 1, dt.getUTCDate(), w, crit);
      if (s.n) list.push({ m: dt.getUTCMonth() + 1, d: dt.getUTCDate(), off: o, p: s.p, n: s.n });
    }
    list.sort(function (a, b) { return b.p - a.p || Math.abs(a.off) - Math.abs(b.off); });
    return list.slice(0, top || 3);
  }
  function fmt(x, dec) { return x.toFixed(dec == null ? 1 : dec).replace('.', ',').replace('-', '\u2013'); }
  function dm(m, d) { return d + '. ' + m + '.'; }

  var model = { buildDays: buildDays, years: years, ok: ok, wilson: wilson, share: share, exact: exact, best: best, fmt: fmt, dm: dm };
  if (typeof module !== 'undefined' && module.exports) { module.exports = model; }
  if (typeof document === 'undefined') return;

  // ───────────────────────── prikaz ─────────────────────────
  var el = document.getElementById('pr-data'); if (!el) return;
  var DATA; try { DATA = JSON.parse(el.textContent); } catch (e) { return; }
  var MAP = buildDays(DATA);
  var $ = function (id) { return document.getElementById(id); };
  function ls(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } return null; }
  var PROFILES = {
    poroka: { rain: 0.2, tmaxLo: 18, tmaxHi: 30, nmin: null },
    veselica: { rain: 0.2, tmaxLo: 18, tmaxHi: 33, nmin: 9 },
    sport: { rain: 1, tmaxLo: 10, tmaxHi: 25, nmin: null },
  };
  var KEY = 'wx-prireditev-v1';
  function num(id) { var v = parseFloat(String($(id).value).replace(',', '.')); return isFinite(v) ? v : NaN; }
  function crit() {
    var nm = String($('pr-nmin').value).trim();
    return { rain: num('pr-rain'), tmaxLo: num('pr-tlo'), tmaxHi: num('pr-thi'), nmin: nm === '' ? null : parseFloat(nm.replace(',', '.')) };
  }
  function cell(tag, text, cls) { var e = document.createElement(tag); e.textContent = text; if (cls) e.className = cls; return e; }
  function render() {
    var dv = $('pr-datum').value, out = $('pr-out'), msg = $('pr-msg'); out.innerHTML = ''; msg.textContent = '';
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dv)) { msg.textContent = 'Izberite datum.'; return; }
    var m = +dv.slice(5, 7), d = +dv.slice(8, 10), w = +$('pr-w').value, c = crit();
    if (!isFinite(c.rain) || !isFinite(c.tmaxLo) || !isFinite(c.tmaxHi) || (c.nmin != null && !isFinite(c.nmin)) || c.tmaxLo > c.tmaxHi) { msg.textContent = 'Preverite merila (padavine, najvišja od–do, najnižja).'; return; }
    var s = share(MAP, m, d, w, c);
    if (!s.n) { msg.textContent = 'Za ta datum ni podatkov.'; return; }
    var big = document.createElement('p'); big.className = 'archive-intro';
    var b = document.createElement('b'); b.textContent = 'Primeren dan v ' + Math.round(100 * s.p) + ' % primerov'; big.appendChild(b);
    big.appendChild(document.createTextNode(' (' + s.k + ' od ' + s.n + ' dni, okno ±' + w + ' dni okoli ' + dm(m, d) + ' v ' + s.per.length + ' letih; razpon ' +
      Math.round(100 * s.lo) + '–' + Math.round(100 * s.hi) + ' %, optimistično, ker so sosednji dnevi podobni).'));
    out.appendChild(big);
    // točno ta datum po letih
    var ex = exact(MAP, m, d, c), t1 = document.createElement('table'), tb = document.createElement('tbody'), hd = document.createElement('thead'), hr = document.createElement('tr');
    ['Leto', 'Najvišja (°C)', 'Najnižja (°C)', 'Padavine (mm)', 'Primeren'].forEach(function (h) { hr.appendChild(cell('th', h)); }); hd.appendChild(hr); t1.appendChild(hd);
    ex.forEach(function (r) {
      var tr = document.createElement('tr'); tr.appendChild(cell('th', String(r.y))); tr.lastChild.scope = 'row';
      [fmt(r.t), fmt(r.n), fmt(r.p), r.ok ? 'da' : 'ne'].forEach(function (x) { tr.appendChild(cell('td', x)); }); tb.appendChild(tr);
    });
    t1.appendChild(tb);
    var h2 = cell('h3', 'Točno ' + dm(m, d) + ' v prejšnjih letih'); out.appendChild(h2); var wrap = document.createElement('div'); wrap.className = 'pr-tbl'; wrap.appendChild(t1); out.appendChild(wrap);
    // boljši datumi
    var bs = best(MAP, m, d, 14, w, c, 4), ul = document.createElement('ol'); ul.className = 'pr-best';
    bs.forEach(function (x) { var li = document.createElement('li'); li.textContent = dm(x.m, x.d) + ': ' + Math.round(100 * x.p) + ' % primernih dni' + (x.off ? ' (' + (x.off > 0 ? '+' : '\u2013') + Math.abs(x.off) + ' dni)' : ' (izbrani datum)'); ul.appendChild(li); });
    out.appendChild(cell('h3', 'Najboljši datumi v ±14 dneh')); out.appendChild(ul);
    out.appendChild(cell('p', 'Razlike med sosednjimi datumi so v okviru naključja: sedem let je malo. Datum izberite predvsem po tem, ali se vam izplača tvegati; za zadnji teden pred dogodkom velja napoved, ne ta stran.', 'pr-note'));
    ls(KEY, JSON.stringify({ d: dv, w: $('pr-w').value, prof: $('pr-prof').value, rain: $('pr-rain').value, tlo: $('pr-tlo').value, thi: $('pr-thi').value, nmin: $('pr-nmin').value }));
  }
  function applyProfile(name) {
    var p = PROFILES[name]; if (!p) return;
    $('pr-rain').value = p.rain; $('pr-tlo').value = p.tmaxLo; $('pr-thi').value = p.tmaxHi; $('pr-nmin').value = p.nmin == null ? '' : p.nmin;
  }
  var s0 = null; try { s0 = JSON.parse(ls(KEY)); } catch (e) { s0 = null; }
  applyProfile('poroka');
  if (s0) { ['datum:d', 'w:w', 'prof:prof', 'rain:rain', 'tlo:tlo', 'thi:thi', 'nmin:nmin'].forEach(function (p) { var a = p.split(':'); if (s0[a[1]] != null && $('pr-' + a[0])) $('pr-' + a[0]).value = s0[a[1]]; }); }
  $('pr-prof').addEventListener('change', function () { applyProfile(this.value); render(); });
  document.querySelectorAll('#pr-form input,#pr-form select').forEach(function (e) { e.addEventListener('input', render); e.addEventListener('change', render); });
  $('pr-form').addEventListener('submit', function (ev) { ev.preventDefault(); render(); });
  render();
})(typeof window !== 'undefined' ? window : this);
