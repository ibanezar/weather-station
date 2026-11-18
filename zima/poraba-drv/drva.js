/*
 * zima/poraba-drv/drva.js — kalkulator porabe drv po stopinjskih dneh (ROČNO pisana datoteka, ni generirana).
 * MODEL (brez DOM-a; izvožen za Node, tools/test_drva.mjs): remaining, scenarios, modeA, modeB, withReserve, dayIndex.
 * PRIKAZ: obrazec in tabela rezultatov. Podatki (krivulje stopinjskih dni po sezonah) so vdelani v stran (#drva-data),
 * piše jih tools/generate_drva_page.py iz history.json (postaja IREICA1, samo zunanja temperatura).
 *
 * Predpostavka: potreba po toploti je sorazmerna s stopinjskimi dnevi (12/20 °C: dan s povprečjem pod 12 °C prispeva 20 − T).
 * To je poenostavitev (topla voda, sončni dobitki, način ogrevanja); izračun je orientacijski, ne obračun.
 */
(function (root) {
  'use strict';

  // curve = kumulativa stopinjskih dni po dnevih od 1. 10. (curve[i] = vsota do vključno i-tega dne); idx = dni od 1. 10. do danes
  // (0 = danes je 1. 10., vključuje se vse do včeraj). Po koncu sezone (idx > 211) ostane 0, pred njo (idx < 0) cela sezona.
  function remaining(curve, total, idx) {
    if (idx <= 0) return total;
    if (idx > curve.length) return 0;
    return Math.max(0, total - curve[idx - 1]);
  }
  // data = { totals: {leto: skupaj}, curves: {leto: [kumulativa]} }; vrne tri scenarije: toplo, povprečno, hladno (sezone iz data.scenarios)
  function scenarios(data, idx) {
    var years = Object.keys(data.curves);
    function one(y) { return { leto: y, total: data.totals[y], rem: remaining(data.curves[y], data.totals[y], idx) }; }
    var mean = function (f) { return years.reduce(function (s, y) { return s + f(y); }, 0) / years.length; };
    var sorted = years.slice().sort(function (a, b) { return data.totals[a] - data.totals[b]; });
    return {
      topla: one(sorted[0]),
      povp: { leto: null, total: mean(function (y) { return data.totals[y]; }),
        rem: mean(function (y) { return remaining(data.curves[y], data.totals[y], idx); }) },
      hladna: one(sorted[sorted.length - 1]),
    };
  }
  // Način A: poznam lansko porabo (prm) v sezoni z baseTotal stopinjskimi dnevi; fixed = del porabe, neodvisen od vremena (0–1);
  // frac = delež sezone, ki ga računamo (1 = cela sezona, rem/total = od danes do konca): stalni del se porazdeli čez sezono
  function modeA(lastPrm, baseTotal, fixed, hdd, frac) {
    return lastPrm * (fixed * (frac == null ? 1 : frac) + (1 - fixed) * hdd / baseTotal);
  }
  // Način B: iz hiše. q = potreba po toploti (kWh/m²·leto) v povprečni sezoni (refTotal), eff 0–1, kwhPrm = energija v 1 prm
  function modeB(area, q, eff, kwhPrm, hdd, refTotal) {
    return area * q / eff * (hdd / refTotal) / kwhPrm;
  }
  function withReserve(x, pct) { return x * (1 + pct / 100); }
  // dni od 1. 10. za datum (ISO); zunaj sezone (maj–september): vrne −1 (celotna prihajajoča sezona), po 30. 4.
  function dayIndex(iso) {
    var p = iso.split('-').map(Number), y = p[0], m = p[1];
    if (m >= 10) return Math.round((Date.UTC(y, m - 1, p[2]) - Date.UTC(y, 9, 1)) / 86400000);
    if (m <= 4) return Math.round((Date.UTC(y, m - 1, p[2]) - Date.UTC(y - 1, 9, 1)) / 86400000);
    return -1;
  }
  function fmt(x, d) { return x.toFixed(d == null ? 1 : d).replace('.', ','); }

  var model = { remaining: remaining, scenarios: scenarios, modeA: modeA, modeB: modeB, withReserve: withReserve, dayIndex: dayIndex, fmt: fmt };
  if (typeof module !== 'undefined' && module.exports) { module.exports = model; }
  if (typeof document === 'undefined') return;

  // ───────────────────────── prikaz ─────────────────────────
  var dataEl = document.getElementById('drva-data');
  if (!dataEl) return;
  var D;
  try { D = JSON.parse(dataEl.textContent); } catch (e) { return; }
  var $ = function (id) { return document.getElementById(id); };
  function ls(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } return null; }
  var today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Ljubljana' });
  var idx = dayIndex(today);                      // −1 = zunaj sezone
  var KEY = 'wx-drva-v1';
  var DRY = { suha: 2000, polsuha: 1760, sveza: 1550 };

  function num(id) { var v = parseFloat(String($(id).value).replace(',', '.')); return isFinite(v) ? v : NaN; }
  function row(label, a, b, c, bold) {
    var tr = document.createElement('tr'); if (bold) tr.style.fontWeight = '700';
    [label, a, b, c].forEach(function (t, i) { var td = document.createElement(i ? 'td' : 'th'); td.textContent = t; if (!i) td.scope = 'row'; tr.appendChild(td); });
    return tr;
  }
  function hint(out) { var p = document.createElement('p'); p.className = 'archive-intro'; p.textContent = 'Rezultat se prikaže, ko vpišete podatke.'; out.appendChild(p); }
  function render() {
    var mode = document.querySelector('input[name=dr-mode]:checked').value;
    $('dr-a').hidden = mode !== 'a'; $('dr-b').hidden = mode !== 'b';
    var fixed = Math.min(60, Math.max(0, num('dr-fixed') || 0)) / 100;
    var rez = Math.min(50, Math.max(0, num('dr-rez') || 0));
    var sc = scenarios(D, idx < 0 ? 0 : idx);
    var out = $('dr-out'); out.innerHTML = '';
    var msg = $('dr-msg'); msg.textContent = '';
    var f;
    if (mode === 'a') {
      var last = num('dr-last'), base = D.totalsAll[$('dr-base').value];
      if (!(last > 0)) { msg.textContent = 'Vpišite lansko porabo (prm).'; hint(out); return; }
      f = function (hdd, frac) { return modeA(last, base, fixed, hdd, frac); };
    } else {
      var area = num('dr-area'), q = num('dr-q'), eff = num('dr-eff') / 100, kwh = num('dr-kwh');
      if (!(area > 0) || !(q > 0) || !(eff > 0.3 && eff <= 1) || !(kwh > 0)) { msg.textContent = 'Preverite površino, potrebo po toploti, izkoristek (30–100 %) in energijo v prm.'; hint(out); return; }
      f = function (hdd) { return modeB(area, q, eff, kwh, hdd, D.mean); };
    }
    var price = num('dr-price'), hasPrice = price > 0;
    var tbl = document.createElement('table'); var tb = document.createElement('tbody');
    var head = document.createElement('thead'); var hr = document.createElement('tr');
    ['Sezona', 'Cela sezona', idx < 0 ? 'Od začetka (1. 10.)' : 'Od danes do 30. 4.', 'S ' + fmt(rez, 0) + ' % rezerve (cela)'].forEach(function (t) { var th = document.createElement('th'); th.textContent = t; hr.appendChild(th); });
    head.appendChild(hr); tbl.appendChild(head);
    [['Kot najtoplejša (' + D.labels[sc.topla.leto] + ')', sc.topla], ['Povprečna (' + D.nSeasons + ' sezon)', sc.povp], ['Kot najhladnejša (' + D.labels[sc.hladna.leto] + ')', sc.hladna]].forEach(function (p, i) {
      var tot = f(p[1].total, 1), rem = f(p[1].rem, p[1].total ? p[1].rem / p[1].total : 0);
      tb.appendChild(row(p[0], fmt(tot) + ' prm', fmt(rem) + ' prm', fmt(withReserve(tot, rez)) + ' prm', i === 1));
    });
    tbl.appendChild(tb); out.appendChild(tbl);
    if (hasPrice) {
      var avg = f(sc.povp.total, 1);
      var p = document.createElement('p'); p.className = 'vs-note';
      p.textContent = 'Strošek povprečne sezone: približno ' + fmt(avg * price, 0) + ' € (' + fmt(avg) + ' prm × ' + fmt(price, 0) + ' €).'; out.appendChild(p);
    }
    ls(KEY, JSON.stringify({ mode: mode, last: $('dr-last').value, base: $('dr-base').value, area: $('dr-area').value, q: $('dr-q').value,
      eff: $('dr-eff').value, dry: $('dr-dry').value, kwh: $('dr-kwh').value, fixed: $('dr-fixed').value, rez: $('dr-rez').value, price: $('dr-price').value }));
  }
  // privzeto in shranjeno
  var s = null; try { s = JSON.parse(ls(KEY)); } catch (e) { s = null; }
  if (s) {
    var set = function (id, v) { if (v != null && $(id)) $(id).value = v; };
    set('dr-last', s.last); set('dr-base', s.base); set('dr-area', s.area); set('dr-q', s.q); set('dr-eff', s.eff); set('dr-dry', s.dry);
    set('dr-kwh', s.kwh); set('dr-fixed', s.fixed); set('dr-rez', s.rez); set('dr-price', s.price);
    if (s.mode) { var r = document.querySelector('input[name=dr-mode][value=' + s.mode + ']'); if (r) r.checked = true; }
  }
  $('dr-dry').addEventListener('change', function () { if (DRY[this.value]) $('dr-kwh').value = DRY[this.value]; render(); });
  $('dr-preset').addEventListener('change', function () { if (this.value) $('dr-q').value = this.value; render(); });
  document.querySelectorAll('#dr-form input,#dr-form select').forEach(function (e) { e.addEventListener('input', render); e.addEventListener('change', render); });
  $('dr-form').addEventListener('submit', function (ev) { ev.preventDefault(); render(); });
  render();
})(typeof window !== 'undefined' ? window : this);
