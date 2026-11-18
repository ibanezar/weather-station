// Rojstnodnevno vreme: model brez DOM-a (izvožen za Node) + prikaz. Podatki: #rd-data {start, t, n, p} (nizi po dnevih od start).
(function (root) {
  'use strict';
  function pad(x) { return (x < 10 ? '0' : '') + x; }
  function addDays(iso, k) { var d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + k); return d; }
  function isoOf(d) { return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate()); }
  // Vsi zapisi za koledarski dan m/d (1-12, 1-31): [{y, t, n, p}] samo dnevi z vsemi tremi polji.
  function byDate(data, m, d) {
    var out = [];
    for (var i = 0; i < data.t.length; i++) {
      var dt = addDays(data.start, i);
      if (dt.getUTCMonth() + 1 !== m || dt.getUTCDate() !== d) continue;
      if (data.t[i] == null || data.n[i] == null || data.p[i] == null) continue;
      out.push({ y: dt.getUTCFullYear(), t: data.t[i], n: data.n[i], p: data.p[i] });
    }
    return out;
  }
  function validDate(m, d) { return m >= 1 && m <= 12 && d >= 1 && d <= [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]; }
  function mean(a) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i]; return s / a.length; }
  // Povzetek: točno leto (če obstaja) + povprečje, ekstremi.
  function summary(rows, year) {
    if (!rows.length) return null;
    var exact = null;
    for (var i = 0; i < rows.length; i++) if (rows[i].y === year) exact = rows[i];
    var warm = rows[0], cold = rows[0], wet = rows[0];
    for (var j = 1; j < rows.length; j++) {
      if (rows[j].t > warm.t) warm = rows[j];
      if (rows[j].n < cold.n) cold = rows[j];
      if (rows[j].p > wet.p) wet = rows[j];
    }
    var rainy = 0;
    for (var k = 0; k < rows.length; k++) if (rows[k].p >= 0.2) rainy++;
    return { exact: exact, n: rows.length, tAvg: mean(rows.map(function (r) { return r.t; })), nAvg: mean(rows.map(function (r) { return r.n; })), warm: warm, cold: cold, wet: wet, rainy: rainy };
  }
  var api = { byDate: byDate, validDate: validDate, summary: summary };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.RojstniModel = api;
  if (typeof document === 'undefined') return;
  var data = JSON.parse(document.getElementById('rd-data').textContent);
  function f1(x) { return (Math.round(x * 10) / 10).toFixed(1).replace('.', ',').replace('-', '−'); }
  var out = document.getElementById('rd-out'), form = document.getElementById('rd-form');
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function run() {
    var v = document.getElementById('rd-datum').value; // YYYY-MM-DD
    out.textContent = '';
    if (!v) { out.appendChild(el('p', 'archive-intro', 'Izberite datum.')); return; }
    var p = v.split('-'), y = +p[0], m = +p[1], d = +p[2];
    if (!validDate(m, d)) { out.appendChild(el('p', 'archive-intro', 'Neveljaven datum.')); return; }
    var s = summary(byDate(data, m, d), y);
    if (!s) { out.appendChild(el('p', 'archive-intro', 'Za ta datum postaja nima nobene popolne meritve.')); return; }
    var c = el('div', 'card');
    c.appendChild(el('div', 'clabel', d + '. ' + m + '.'));
    if (s.exact) {
      c.appendChild(el('div', 'rd-big', 'Leta ' + y + ': ' + f1(s.exact.n) + ' do ' + f1(s.exact.t) + ' °C'));
      c.appendChild(el('p', null, s.exact.p >= 0.2 ? 'Padlo je ' + f1(s.exact.p) + ' mm padavin.' : 'Brez padavin.'));
    } else {
      c.appendChild(el('p', null, y < +data.start.slice(0, 4) ? 'Za leto ' + y + ' postaja nima meritve (merimo od ' + data.start.split('-').reverse().join('. ') + ').' : 'Za leto ' + y + ' ni popolne meritve.'));
    }
    c.appendChild(el('p', null, 'Na ta datum je v ' + s.n + ' letih meritev povprečna najnižja ' + f1(s.nAvg) + ' °C in najvišja ' + f1(s.tAvg) + ' °C; dež je bil v ' + s.rainy + ' od ' + s.n + ' let.'));
    c.appendChild(el('p', null, 'Najtoplejše: ' + f1(s.warm.t) + ' °C (' + s.warm.y + '), najhladneje: ' + f1(s.cold.n) + ' °C (' + s.cold.y + '), največ padavin: ' + f1(s.wet.p) + ' mm (' + s.wet.y + ').'));
    out.appendChild(c);
  }
  form.addEventListener('submit', function (e) { e.preventDefault(); run(); });
  document.getElementById('rd-datum').addEventListener('input', run);
})(typeof window !== 'undefined' ? window : globalThis);
