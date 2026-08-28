// meteohmeljar/hmeljar.js — MeteoHmeljar karta + engine, ROČNO PISANA (ni generirana).
//
// Klik na hmeljiško parcelo (MKGP RABA, prek Worker /hmeljar-raba) izračuna
// SprayScore/PeronosporaRisk/PepelovkaRisk/WaterBalance/StormRisk in Decision
// Engine za tisto točko, CLIENT-SIDE, na zahtevo. Formule so namerna kopija
// tools/hmeljar_model.py (Python ne teče v brskalniku, ni izvedljivo
// strežniško generirati stran za vsako od stotih možnih kliknjenih parcel v
// dolini) — isto načelo kot gasilec_model.py/app.js/gasilec.js (glej opombo
// na vrhu gasilec_model.py). Če spremeniš prag/formulo tu, popravi tudi tam.
//
// V primerjavi s tools/hmeljar_model.py je ta različica BREZ vztrajnega
// dnevnika (ni cron teka na strežniku, ki bi ga pisal za poljubno kliknjeno
// točko): WaterBalance zato kumulativni primanjkljaj računa iz enega
// daljšega Open-Meteo okna (60 pretečenih dni, resetira se ob >=15mm dnevu
// znotraj tega okna) namesto iz shranjenega stanja, PeronosporaRisk/
// PepelovkaRisk pa (za zdaj) ne kažeta dnevnega trenda — za trend bi
// potreboval včerajšnjo vrednost, ki je brez strežnika nima kje čakati.

(function () {
  var noteEl = document.getElementById('hm-map-note');
  if (typeof L === 'undefined') {
    if (noteEl) noteEl.textContent = 'Interaktivna karta trenutno ni na voljo (Leaflet se ni naložil) — poskusi znova.';
    return;
  }

  var WORKER = 'https://weatherireica1.filip-eremita.workers.dev';
  var DEFAULT_LAT = 46.325779, DEFAULT_LON = 14.921137; // IREICA1, Rečica ob Savinji

  // ── operation_profile — privzete meje (namerna kopija DEFAULT_OPERATION_PROFILE) ──
  var PROFILE = {
    windOptimalKmh: 2, windMaxKmh: 8, gustMaxKmh: 15,
    tempMinC: 8, tempMaxC: 25, tempShoulderLowC: 12, tempShoulderHighC: 22,
    rainfreeHoursRequired: 4, rhWetLeafPct: 95, rhTaperStartPct: 70,
    wetLeafAllowed: false, precipProbGatePct: 50, precipProbTaperPct: 40
  };

  function lerpDown(x, lo, hi) { if (hi <= lo) return x <= lo ? 100 : 0; return Math.max(0, Math.min(100, 100 * (hi - x) / (hi - lo))); }
  function lerpUp(x, lo, hi) { if (hi <= lo) return x >= hi ? 100 : 0; return Math.max(0, Math.min(100, 100 * (x - lo) / (hi - lo))); }

  // ── SprayScore ────────────────────────────────────────────────────────
  function windComponent(w) { return w <= PROFILE.windOptimalKmh ? 100 : lerpDown(w, PROFILE.windOptimalKmh, PROFILE.windMaxKmh); }
  function tempComponent(t) {
    if (t >= PROFILE.tempShoulderLowC && t <= PROFILE.tempShoulderHighC) return 100;
    if (t < PROFILE.tempShoulderLowC) return lerpUp(t, PROFILE.tempMinC, PROFILE.tempShoulderLowC);
    return lerpDown(t, PROFILE.tempShoulderHighC, PROFILE.tempMaxC);
  }
  function rhComponent(rh) { return rh <= PROFILE.rhTaperStartPct ? 100 : lerpDown(rh, PROFILE.rhTaperStartPct, PROFILE.rhWetLeafPct); }
  function rainfreeComponent(h) {
    var req = PROFILE.rainfreeHoursRequired;
    if (h < req) return 0;
    var span = Math.max(0.5 * req, 1e-6);
    return Math.max(0, Math.min(100, 100 * (h - req) / span));
  }
  function hoursToNextRain(hourly, startIdx, horizon) {
    horizon = horizon || 48;
    var precip = hourly.precipitation || [], prob = hourly.precipitation_probability || [];
    var n = Math.min(Math.max(precip.length, prob.length), startIdx + horizon);
    for (var i = startIdx; i < n; i++) {
      var p = precip[i], q = prob[i];
      if ((p != null && p > 0.1) || (q != null && q > PROFILE.precipProbTaperPct)) return i - startIdx;
    }
    return horizon;
  }
  function sprayScoreHour(hourly, idx) {
    var wind = hourly.wind_speed_10m[idx], gust = hourly.wind_gusts_10m[idx],
      precip = hourly.precipitation[idx], prob = hourly.precipitation_probability[idx],
      temp = hourly.temperature_2m[idx], rh = hourly.relative_humidity_2m[idx];
    if ([wind, gust, precip, temp, rh].some(function (v) { return v == null; }))
      return { score: 0, reason: 'manjkajoč podatek' };
    if (wind > PROFILE.windMaxKmh) return { score: 0, reason: 'veter' };
    if (gust > PROFILE.gustMaxKmh) return { score: 0, reason: 'sunki vetra' };
    if (precip > 0.1 || (prob != null && prob > PROFILE.precipProbGatePct)) return { score: 0, reason: 'padavine' };
    if (temp < PROFILE.tempMinC || temp > PROFILE.tempMaxC) return { score: 0, reason: 'temperatura' };
    if (!PROFILE.wetLeafAllowed && rh >= PROFILE.rhWetLeafPct) return { score: 0, reason: 'mokro listje' };
    var htr = hoursToNextRain(hourly, idx);
    var comps = { veter: windComponent(wind), temperatura: tempComponent(temp), vlaga: rhComponent(rh), brez_dezja: rainfreeComponent(htr) };
    var score = Math.min(comps.veter, comps.temperatura, comps.vlaga, comps.brez_dezja);
    return { score: score, components: comps };
  }
  function spraySeries(hourly, fromIdx, hours) {
    hours = hours || 168;
    var n = Math.min(hours, (hourly.time || []).length - fromIdx);
    var out = [];
    for (var i = 0; i < n; i++) {
      var idx = fromIdx + i;
      var r = sprayScoreHour(hourly, idx);
      out.push({ time: hourly.time[idx], score: Math.round(r.score), components: r.components || { reason: r.reason } });
    }
    return out;
  }
  function tier(score) { return score >= 70 ? 'green' : score >= 40 ? 'yellow' : 'red'; }
  function sprayWindows(series) {
    var runs = [], cur = null;
    series.forEach(function (pt, i) {
      var t = tier(pt.score);
      if (cur && cur.tier === t) { cur.end = pt.time; cur.endIdx = i; cur.hours.push(pt); }
      else { if (cur) runs.push(cur); cur = { tier: t, start: pt.time, startIdx: i, end: pt.time, endIdx: i, hours: [pt] }; }
    });
    if (cur) runs.push(cur);
    return runs;
  }
  function bestWindow(runs, withinHours, minHours) {
    withinHours = withinHours || 24; minHours = minHours || 3;
    var cands = runs.filter(function (r) { return r.tier === 'green' && r.startIdx < withinHours && r.hours.length >= minHours; });
    if (!cands.length) return null;
    cands.sort(function (a, b) { return b.hours.length !== a.hours.length ? b.hours.length - a.hours.length : a.startIdx - b.startIdx; });
    return cands[0];
  }
  function windowCloseReason(series, run) {
    var nxt = run.endIdx + 1;
    if (nxt >= series.length) return null;
    var comps = series[nxt].components;
    if (comps.reason) return comps.reason;
    var worst = null, worstV = 101;
    Object.keys(comps).forEach(function (k) { if (comps[k] < worstV) { worstV = comps[k]; worst = k; } });
    return worst;
  }

  // ── PeronosporaRisk / PepelovkaRisk ──────────────────────────────────────
  // Pragi so prvi približek iz literature (APS Journals / Oregon State), ne
  // validirani na slovenskih podatkih — meteorološka ugodnost, ni diagnoza.
  function wetHoursStats(hourly, start, end) {
    var temps = hourly.temperature_2m || [], rh = hourly.relative_humidity_2m || [],
      precip = hourly.precipitation || [], isDay = hourly.is_day || [];
    var urRh80 = 0, wetDegreeHours = 0, nightTemps = [];
    for (var i = start; i < end; i++) {
      var t = temps[i], h = rh[i], p = precip[i], d = isDay[i];
      if (h != null && h >= 80) urRh80++;
      var wet = (h != null && h >= 90) || (p != null && p > 0);
      if (wet && t != null && t >= 10 && t <= 25) wetDegreeHours += t;
      if (d === 0 && t != null) nightTemps.push(t);
    }
    var nightAvg = nightTemps.length ? nightTemps.reduce(function (a, b) { return a + b; }, 0) / nightTemps.length : null;
    return { urRh80: urRh80, wetDegreeHours: wetDegreeHours, nightAvg: nightAvg };
  }
  function nightTempScore(nightAvg) {
    if (nightAvg == null) return 50;
    if (nightAvg >= 12 && nightAvg <= 20) return 100;
    if (nightAvg < 12) return lerpUp(nightAvg, 5, 12);
    return lerpDown(nightAvg, 20, 27);
  }
  function peronosporaPeriodScore(hourly, start, end) {
    var s = wetHoursStats(hourly, start, end);
    var rh80 = Math.min(100, s.urRh80 / 16 * 100);
    var wet = Math.min(100, s.wetDegreeHours / 150 * 100); // KALIBRACIJA — placeholder
    var night = nightTempScore(s.nightAvg);
    return 0.4 * rh80 + 0.4 * wet + 0.2 * night;
  }
  function peronosporaRisk(hourlyTrailing, hourlyForward) {
    var trailing = peronosporaPeriodScore(hourlyTrailing, 0, (hourlyTrailing.time || []).length);
    var fwdN = Math.min(48, (hourlyForward.time || []).length);
    var forward = peronosporaPeriodScore(hourlyForward, 0, fwdN);
    return Math.round(0.6 * trailing + 0.4 * forward);
  }
  function pepelovkaPeriodScore(hourly, start, end) {
    var temps = hourly.temperature_2m || [], rh = hourly.relative_humidity_2m || [], precip = hourly.precipitation || [];
    var consec = 0, maxConsec = 0, rainMm = 0;
    for (var i = start; i < end; i++) {
      var t = temps[i], h = rh[i], p = precip[i];
      var fav = t != null && t >= 16 && t <= 27 && (h == null || h < 90);
      consec = fav ? consec + 1 : 0;
      maxConsec = Math.max(maxConsec, consec);
      if (p) rainMm += p;
    }
    var score = Math.min(100, maxConsec / 6 * 100);
    if (rainMm >= 5) score *= 0.5;
    return score;
  }
  function pepelovkaRisk(hourlyTrailing, hourlyForward) {
    var trailing = pepelovkaPeriodScore(hourlyTrailing, 0, (hourlyTrailing.time || []).length);
    var fwdN = Math.min(48, (hourlyForward.time || []).length);
    var forward = pepelovkaPeriodScore(hourlyForward, 0, fwdN);
    return Math.round(0.6 * trailing + 0.4 * forward);
  }
  function riskLabel(pct) { return pct < 30 ? 'Nizko' : pct < 60 ? 'Zmerno' : 'Visoko'; }

  // ── WaterBalance (brez dnevnika — glej opombo na vrhu datoteke) ─────────
  function dailyBalance(precip, et0) { if (precip == null || et0 == null) return null; return precip - et0; }
  function waterBalanceFromDaily(daily, todayIso) {
    var dates = daily.time || [], precip = daily.precipitation_sum || [], et0 = daily.et0_fao_evapotranspiration || [];
    var idx = dates.indexOf(todayIso);
    if (idx < 0) return null;
    var cd = 0;
    for (var i = 0; i <= idx; i++) {
      var b = dailyBalance(precip[i], et0[i]);
      var rain = precip[i];
      if (rain != null && rain >= 15) cd = 0;
      else if (b != null) cd = Math.min(0, cd + b);
    }
    var lo7 = Math.max(0, idx - 6), b7 = 0;
    for (var j = lo7; j <= idx; j++) b7 += dailyBalance(precip[j], et0[j]) || 0;
    var hi3 = Math.min(dates.length, idx + 4), b3 = 0;
    for (var k = idx + 1; k < hi3; k++) b3 += dailyBalance(precip[k], et0[k]) || 0;
    return { cumulativeDeficit: Math.round(cd * 10) / 10, balance7d: Math.round(b7 * 10) / 10, balance3dFwd: Math.round(b3 * 10) / 10 };
  }

  // ── StormRisk ─────────────────────────────────────────────────────────
  function gustRisk(g) { return g == null ? 0 : lerpUp(g, 40, 90); } // PRVI PRIBLIŽEK za trelis, potrebna lokalna kalibracija
  function precipIntensityRisk(p) { return p == null ? 0 : lerpUp(p, 2, 20); }
  function thunderRisk(cape, prob, precip) {
    if (cape != null) return lerpUp(cape, 500, 2500);
    if (prob != null && precip != null && prob > 60 && precip > 5) return 100;
    return 0;
  }
  var STORM_LABELS = { veter: 'veter', naliv: 'obilne padavine', nevihta: 'nevihte' };
  function stormRiskHour(hourly, idx) {
    var gust = hourly.wind_gusts_10m[idx], precip = hourly.precipitation[idx],
      prob = hourly.precipitation_probability[idx], cape = hourly.cape ? hourly.cape[idx] : null;
    var comps = { veter: gustRisk(gust), naliv: precipIntensityRisk(precip), nevihta: thunderRisk(cape, prob, precip) };
    var score = Math.max(comps.veter, comps.naliv, comps.nevihta);
    return { score: score, comps: comps };
  }
  function stormSummary(hourlyNext12, officialActive) {
    var n = (hourlyNext12.time || []).length;
    var bestScore = 0, bestDriver = null, firstEvent = null;
    for (var i = 0; i < n; i++) {
      var r = stormRiskHour(hourlyNext12, i);
      var score = r.score;
      if (officialActive) score = Math.max(score, 80);
      if (firstEvent == null && score >= 50) firstEvent = i;
      if (score > bestScore) {
        bestScore = score;
        bestDriver = Object.keys(r.comps).reduce(function (a, b) { return r.comps[a] >= r.comps[b] ? a : b; });
      }
    }
    return { maxScore: Math.round(bestScore), timeToEventH: firstEvent, driver: bestDriver ? STORM_LABELS[bestDriver] : null };
  }

  // ── Decision Engine — deterministično, brez LLM klica ────────────────────
  function fmtHm(iso) { return iso.slice(11, 16); }
  function decide(o) {
    var items = [];
    if (o.storm.maxScore >= 70) {
      var cas = o.storm.timeToEventH != null ? ('čez ~' + o.storm.timeToEventH + 'h') : 'danes';
      items.push({ type: 'storm', text: '⛈️ Nevarnost neurja ' + cas + ' — glavno tveganje: ' + o.storm.driver + '.' });
    }
    if (o.bestWin && o.bestWin.hours.length >= 3) {
      var reason = windowCloseReason(o.spraySeries, o.bestWin);
      items.push({
        type: 'spray',
        text: '🧪 Dobro škropilno okno: ' + fmtHm(o.bestWin.start) + '–' + fmtHm(o.bestWin.end) + '.' +
          (reason ? ' Zapira se zaradi: ' + reason + '.' : '')
      });
    }
    if (o.cumulativeDeficit != null && o.cumulativeDeficit <= o.deficitThreshold) {
      items.push({ type: 'water', text: '💧 Vodni primanjkljaj (' + Math.round(o.cumulativeDeficit) + ' mm) presega prag (' + Math.round(o.deficitThreshold) + ' mm).' });
    }
    return items.slice(0, 3);
  }

  // ── viri ─────────────────────────────────────────────────────────────
  function fetchHourly(lat, lon) {
    var params = new URLSearchParams({
      latitude: lat, longitude: lon,
      hourly: 'temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,wind_speed_10m,wind_gusts_10m,is_day,cape',
      past_days: 2, forecast_days: 7, timezone: 'Europe/Ljubljana'
    });
    return fetch('https://api.open-meteo.com/v1/forecast?' + params).then(function (r) { return r.json(); });
  }
  function fetchDaily(lat, lon) {
    var params = new URLSearchParams({
      latitude: lat, longitude: lon,
      daily: 'et0_fao_evapotranspiration,precipitation_sum',
      past_days: 60, forecast_days: 7, timezone: 'Europe/Ljubljana'
    });
    return fetch('https://api.open-meteo.com/v1/forecast?' + params).then(function (r) { return r.json(); });
  }
  function fetchArsoAlerts() {
    return fetch(WORKER + '/arso-warning?region=SLOVENIA_NORTH-EAST')
      .then(function (r) { return r.json(); })
      .catch(function () { return { alerts: [] }; });
  }
  var STORM_ARSO_TYPES = ['WarningTS', 'WarningWind', 'WarningRA'];
  function officialStormWarningActive(alerts) {
    return (alerts || []).some(function (a) { return STORM_ARSO_TYPES.indexOf(a.type) >= 0 && (a.level === 'orange' || a.level === 'red'); });
  }
  function nowIndex(times) {
    var now = new Date();
    var pad = function (n) { return n < 10 ? '0' + n : '' + n; };
    var key = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate()) + 'T' + pad(now.getHours()) + ':00';
    for (var i = 0; i < times.length; i++) if (times[i] >= key) return i;
    return Math.max(0, times.length - 1);
  }
  function sliceHourly(h, s, e) {
    var keys = ['time', 'temperature_2m', 'relative_humidity_2m', 'precipitation', 'precipitation_probability', 'wind_speed_10m', 'wind_gusts_10m', 'is_day', 'cape'];
    var out = {};
    keys.forEach(function (k) { out[k] = (h[k] || []).slice(Math.max(0, s), e); });
    return out;
  }

  // ── izris ────────────────────────────────────────────────────────────
  function renderBar(points) {
    var colors = { green: '#22c55e', yellow: '#f59e0b', red: '#ef4444' };
    var w = 100 / points.length;
    var html = '<div style="display:flex;height:14px;border-radius:4px;overflow:hidden;margin:.4rem 0">';
    points.forEach(function (p) {
      html += '<span title="' + p.time.slice(11, 16) + ' — ' + p.score + '" style="display:inline-block;width:' + w.toFixed(3) + '%;height:100%;background:' + colors[tier(p.score)] + '"></span>';
    });
    return html + '</div>';
  }
  function numSl(x, d) { return x == null ? '—' : x.toFixed(d == null ? 1 : d).replace('.', ','); }

  function renderDashboard(naziv, areaHa, spraySeriesArr, bestWin, peronospora, pepelovka, water, storm, decision) {
    var dec = decision.length
      ? decision.map(function (d) { return '<p style="margin:.3rem 0">' + d.text + '</p>'; }).join('')
      : '<p class="archive-intro" style="margin:0">Brez posebnosti — pogoji so v mejah, nič ne izstopa.</p>';
    var todayDate = spraySeriesArr.length ? spraySeriesArr[0].time.slice(0, 10) : null;
    var todayPts = spraySeriesArr.filter(function (p) { return p.time.slice(0, 10) === todayDate; });
    var bar = todayPts.length ? renderBar(todayPts) : '';
    var oknoTxt = bestWin
      ? 'Najboljše okno: <strong>' + fmtHm(bestWin.start) + '–' + fmtHm(bestWin.end) + '</strong>'
      : 'V naslednjih 24 h ni dobrega škropilnega okna (vsaj 3 ure zapored).';
    var waterHtml = water
      ? ('<table class="stats">'
        + '<tr><th>7-dnevna bilanca</th><td>' + (water.balance7d >= 0 ? '+' : '') + numSl(water.balance7d) + ' mm</td></tr>'
        + '<tr><th>Naslednji 3 dnevi (napoved)</th><td>' + (water.balance3dFwd >= 0 ? '+' : '') + numSl(water.balance3dFwd) + ' mm</td></tr>'
        + '<tr><th>Kumulativni primanjkljaj (60 dni)</th><td>' + numSl(water.cumulativeDeficit) + ' mm</td></tr>'
        + '</table>')
      : '<p class="muted-note">Vodna bilanca trenutno ni na voljo.</p>';
    var stormCas = storm.timeToEventH != null
      ? ('čez ~' + storm.timeToEventH + 'h' + (storm.driver ? ', glavno tveganje: ' + storm.driver : ''))
      : 'ni pričakovana v naslednjih 12h';

    document.getElementById('hm-dashboard').innerHTML =
      '<h2>' + naziv + (areaHa ? ' · ' + numSl(areaHa, 2) + ' ha' : '') + '</h2>'
      + '<div class="card" style="margin-bottom:1rem"><div class="clabel">📋 Kaj je pomembno</div>' + dec + '</div>'
      + '<div class="card" style="margin-bottom:1rem"><div class="clabel">🧪 Škropljenje</div>' + bar
      + '<p class="archive-intro" style="margin:.4rem 0 0">' + oknoTxt + '</p>'
      + '<p class="muted-note">Meteorološko okno — nikoli ne preglasi registracije, etikete ali navodil konkretnega FFS.</p></div>'
      + '<div class="card" style="margin-bottom:1rem"><div class="clabel">🍃 Bolezni</div><table class="stats">'
      + '<tr><th>Peronospora</th><td>' + peronospora + ' % — ' + riskLabel(peronospora) + '</td></tr>'
      + '<tr><th>Pepelovka</th><td>' + pepelovka + ' % — ' + riskLabel(pepelovka) + '</td></tr></table>'
      + '<p class="muted-note">Meteorološka ugodnost za okužbo, ni diagnoza — pragi so prvi približek iz tuje literature, še ne umerjeni na slovenskih podatkih.</p></div>'
      + '<div class="card" style="margin-bottom:1rem"><div class="clabel">💧 Voda</div>' + waterHtml
      + '<p class="muted-note">Samo meteorološka bilanca (padavine − ET₀) — brez tal ali koeficienta rastline (Kc).</p></div>'
      + '<div class="card" style="margin-bottom:1rem"><div class="clabel">⛈️ Nevarnosti</div>'
      + '<p class="archive-intro" style="margin:0">Ocena za naslednjih 12h: <strong>' + storm.maxScore + '/100</strong> (' + stormCas + ').</p></div>';
  }

  function loadParcel(lat, lon, naziv, areaHa) {
    document.getElementById('hm-dashboard').innerHTML = '<p class="archive-intro">Nalagam …</p>';
    Promise.all([fetchHourly(lat, lon), fetchDaily(lat, lon), fetchArsoAlerts()]).then(function (results) {
      var hourlyRaw = results[0].hourly || {};
      var dailyRaw = results[1].daily || {};
      var alerts = results[2].alerts || [];
      var idx = nowIndex(hourlyRaw.time || []);

      var trailing = sliceHourly(hourlyRaw, idx - 24, idx);
      var forward48 = sliceHourly(hourlyRaw, idx, idx + 48);
      var forwardAll = sliceHourly(hourlyRaw, idx, (hourlyRaw.time || []).length);
      var next12 = sliceHourly(hourlyRaw, idx, idx + 12);

      var series = spraySeries(forwardAll, 0);
      var runs = sprayWindows(series);
      var best = bestWindow(runs);

      var peronospora = peronosporaRisk(trailing, forward48);
      var pepelovka = pepelovkaRisk(trailing, forward48);

      var todayIso = new Date().toISOString().slice(0, 10);
      var water = waterBalanceFromDaily(dailyRaw, todayIso);

      var storm = stormSummary(next12, officialStormWarningActive(alerts));

      var decision = decide({ storm: storm, bestWin: best, spraySeries: series, cumulativeDeficit: water ? water.cumulativeDeficit : null, deficitThreshold: -30 });

      renderDashboard(naziv, areaHa, series, best, peronospora, pepelovka, water, storm, decision);
    }).catch(function (e) {
      document.getElementById('hm-dashboard').innerHTML = '<p class="muted-note">Podatkov ni bilo mogoče naložiti (' + e + '). Poskusi znova.</p>';
    });
  }

  // ── karta ────────────────────────────────────────────────────────────
  var map = L.map('hm-map').setView([DEFAULT_LAT, DEFAULT_LON], 12);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);

  fetch(WORKER + '/hmeljar-raba')
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (geo) {
      if (noteEl) noteEl.textContent = '';
      var layer = L.geoJSON(geo, {
        style: { color: '#16a34a', weight: 2, fillColor: '#22c55e', fillOpacity: 0.25 },
        onEachFeature: function (feature, lyr) {
          var props = feature.properties || {};
          var areaHa = props.POVRSINA ? props.POVRSINA / 10000 : null;
          lyr.bindTooltip(areaHa ? (numSl(areaHa, 2) + ' ha') : 'hmeljišče', { sticky: true });
          lyr.on('click', function () {
            var b = lyr.getBounds();
            var center = b.getCenter();
            var naziv = 'Hmeljišče' + (props.RABA_PID ? ' (RABA ' + props.RABA_PID + ')' : '');
            map.fitBounds(b, { maxZoom: 16 });
            loadParcel(center.lat, center.lng, naziv, areaHa);
          });
        }
      }).addTo(map);
      if (layer.getBounds().isValid()) map.fitBounds(layer.getBounds(), { maxZoom: 13 });
    })
    .catch(function (e) {
      if (noteEl) noteEl.textContent = 'Hmeljišč trenutno ni mogoče naložiti (' + e + '). Poskusi znova čez nekaj minut.';
    });
})();
