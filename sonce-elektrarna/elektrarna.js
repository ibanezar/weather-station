// Napoved proizvodnje sončne elektrarne: model brez DOM-a (izvožen za Node) + prikaz.
// Vir: Open-Meteo global_tilted_irradiance (W/m² na nagnjeno ploskev, povprečje ure). Energija = Σ GTI/1000 [kWh/m²] × kWp × PR.
(function (root) {
  'use strict';
  var DEF = { kwp: 5, tilt: 35, az: 0, pr: 0.8 };
  function clamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
  // Sanitizacija vhodov: kWp 0,1–1000, naklon 0–90°, azimut −180…180 (0 = jug), PR 0,5–0,95.
  function inputs(o) {
    function num(v, d) { v = parseFloat(String(v).replace(',', '.')); return isNaN(v) ? d : v; }
    return { kwp: clamp(num(o.kwp, DEF.kwp), 0.1, 1000), tilt: clamp(num(o.tilt, DEF.tilt), 0, 90), az: clamp(num(o.az, DEF.az), -180, 180), pr: clamp(num(o.pr, DEF.pr), 0.5, 0.95) };
  }
  // Dnevne vsote: times = ISO lokalni nizi, gti = W/m² (null = manjka). Dan z manjkajočo uro je označen incomplete (vsota je spodnja ocena).
  function daily(times, gti, kwp, pr) {
    var days = {}, order = [];
    for (var i = 0; i < times.length; i++) {
      var d = times[i].slice(0, 10);
      if (!days[d]) { days[d] = { date: d, kwh: 0, missing: 0 }; order.push(d); }
      if (gti[i] == null) days[d].missing++;
      else days[d].kwh += Math.max(0, gti[i]) / 1000 * kwp * pr;
    }
    return order.map(function (d) { var r = days[d]; return { date: d, kwh: r.kwh, incomplete: r.missing > 0 }; });
  }
  // Preostanek današnjega dne: ure od vključno nowHour (lokalna ura).
  function remainingToday(times, gti, kwp, pr, nowHour) {
    var d0 = times[0].slice(0, 10), s = 0;
    for (var i = 0; i < times.length; i++) if (times[i].slice(0, 10) === d0 && +times[i].slice(11, 13) >= nowHour && gti[i] != null) s += Math.max(0, gti[i]) / 1000 * kwp * pr;
    return s;
  }
  var api = { inputs: inputs, daily: daily, remainingToday: remainingToday, DEF: DEF };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ElektrarnaModel = api;
  if (typeof document === 'undefined') return;
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function f1(x) { return (Math.round(x * 10) / 10).toFixed(1).replace('.', ','); }
  var form = document.getElementById('el-form'), out = document.getElementById('el-out'), msg = document.getElementById('el-msg');
  function read() { var o = {}; ['kwp', 'tilt', 'az', 'pr'].forEach(function (k) { o[k] = document.getElementById('el-' + k).value; }); var v = inputs(o); v.pr = v.pr > 1 ? v.pr / 100 : v.pr; return v; }
  function run() {
    var v = inputs({ kwp: document.getElementById('el-kwp').value, tilt: document.getElementById('el-tilt').value, az: document.getElementById('el-az').value, pr: parseFloat(document.getElementById('el-pr').value) / 100 });
    msg.textContent = 'Nalagam napoved …';
    var url = 'https://api.open-meteo.com/v1/forecast?latitude=46.3258&longitude=14.9211&hourly=global_tilted_irradiance&tilt=' + v.tilt + '&azimuth=' + v.az + '&timezone=Europe%2FLjubljana&forecast_days=7';
    fetch(url).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (j) {
      var days = daily(j.hourly.time, j.hourly.global_tilted_irradiance, v.kwp, v.pr);
      out.textContent = '';
      var mx = 0; days.forEach(function (d) { if (d.kwh > mx) mx = d.kwh; });
      days.forEach(function (d) {
        var row = el('div', 'el-row'), bar = el('div', 'el-bar');
        bar.style.width = (mx ? Math.round(100 * d.kwh / mx) : 0) + '%';
        var dt = d.date.split('-');
        row.appendChild(el('span', 'el-d', +dt[2] + '. ' + +dt[1] + '.'));
        var wrap = el('div', 'el-w'); wrap.appendChild(bar); row.appendChild(wrap);
        row.appendChild(el('span', 'el-v', f1(d.kwh) + ' kWh' + (d.incomplete ? ' *' : '')));
        out.appendChild(row);
      });
      var tot = 0; days.forEach(function (d) { tot += d.kwh; });
      out.appendChild(el('p', 'vs-note', 'Skupaj 7 dni: ' + f1(tot) + ' kWh. * manjkajo podatki za nekaj ur (vsota je spodnja ocena).'));
      msg.textContent = '';
    }).catch(function () { out.textContent = ''; msg.textContent = 'Napovedi sevanja zdaj ni mogoče prebrati. Poskusite znova pozneje.'; });
  }
  form.addEventListener('submit', function (e) { e.preventDefault(); run(); });
  run();
})(typeof window !== 'undefined' ? window : globalThis);
