/* Prototip nove domače strani (lab). Uporablja iste vire kot produkcija (worker: /, /napoved-om, /nowcast, /crnivec-drsi,
   /varpolje-current; datoteki napoved-modela-live.json in blog.json). Zunanjih meritev samo; notranjih ni. */
(function () {
  'use strict';
  var PROXY = 'https://weatherireica1.filip-eremita.workers.dev';
  // Središčna konfiguracija pragov svežine (minute), po viru (specifikacija 10.2/10.4).
  var FRESH = { station: { fresh: 20, stale: 90 }, drsi: 40, varpolje: 30, radar: 20 };
  var TZ = 'Europe/Ljubljana';
  var $ = function (id) { return document.getElementById(id); };
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  // ── zapis ───────────────────────────────────────────────
  function num(v, d) {                       // ničla je veljavna vrednost, manjkajoče ni nič
    if (v == null || v === '' || isNaN(Number(v))) return null;
    return Number(v).toLocaleString('sl-SI', { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function txt(v, d, unit) { var n = num(v, d); return n == null ? 'Ni podatka' : n + (unit ? (unit === '°' ? '' : '\u00a0') + unit : ''); }
  function hhmm(ms) { return new Date(ms).toLocaleTimeString('sl-SI', { hour: '2-digit', minute: '2-digit', timeZone: TZ }); }
  function ageMin(ms) { return Math.max(0, Math.round((Date.now() - ms) / 60000)); }
  function ageTxt(m) { return m < 60 ? m + ' min' : Math.floor(m / 60) + ' h ' + (m % 60) + ' min'; }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function jget(url, ms) {
    var c = new AbortController(), t = setTimeout(function () { c.abort(); }, ms || 10000);
    return fetch(url, { signal: c.signal }).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .finally(function () { clearTimeout(t); });
  }

  // ── preprosto / napredno (v labu lasten ključ; produkcijskega wx-mode ne dotika) ──
  function setMode(m) {
    document.body.setAttribute('data-mode', m);
    document.querySelectorAll('[data-dv-mode]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-dv-mode') === m)); });
    set('wx-lab-mode', m);
  }
  document.addEventListener('DOMContentLoaded', function () {
    var saved = get('wx-lab-mode'); setMode(saved === 'advanced' ? 'advanced' : 'simple');
    document.querySelectorAll('[data-dv-mode]').forEach(function (b) { b.addEventListener('click', function () { setMode(b.getAttribute('data-dv-mode')); }); });
    loadObs(); loadToday(); loadForecast(); loadNowcast(); loadValley(); loadBlog();
    setInterval(loadObs, 5 * 60000); setInterval(loadToday, 15 * 60000); setInterval(loadNowcast, 5 * 60000); setInterval(tickAge, 30000);
  });

  // ── aktivna točka navigacije glede na vidni razdelek (4.2); poleg barve ima tudi podčrtaj/indikator ──
  document.addEventListener('DOMContentLoaded', function () {
    if (!('IntersectionObserver' in window)) return;
    var ids = ['vreme', 'napoved', 'radar'], vis = {};
    function mark() {
      var cur = ids.filter(function (i) { return vis[i]; }).pop() || 'vreme';
      document.querySelectorAll('.dv-nav a[href^="#"],.dv-bottom a[href^="#"]').forEach(function (a) {
        if (a.getAttribute('href') === '#' + cur) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
      });
    }
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { vis[e.target.id] = e.isIntersecting; }); mark(); }, { rootMargin: '-30% 0px -50% 0px' });
    ids.forEach(function (i) { var n = $(i); if (n) io.observe(n); });
  });

  // ── vremenske kode (WMO) → ikona + besedilo ─────────────
  function wmo(code, isDay) {
    if (code === 0) return isDay === 0 ? ['w-moon', 'Jasno'] : ['w-sun', 'Jasno'];
    if (code === 1) return isDay === 0 ? ['w-moon', 'Pretežno jasno'] : ['w-sun', 'Pretežno jasno'];
    if (code === 2) return ['w-part', 'Delno oblačno'];
    if (code === 3) return ['w-cloud', 'Oblačno'];
    if (code === 45 || code === 48) return ['w-fog', 'Megla'];
    if (code >= 51 && code <= 57) return ['w-rain', 'Rahlo rosenje'];
    if (code >= 61 && code <= 67) return ['w-rain', 'Dež'];
    if ((code >= 71 && code <= 77) || code === 85 || code === 86) return ['w-snow', 'Sneg'];
    if (code >= 80 && code <= 82) return ['w-rain', 'Plohe'];
    if (code >= 95) return ['w-storm', 'Nevihta'];
    return ['w-cloud', 'Razmere niso znane'];
  }
  function icon(id) { var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('class', 'dv-wic'); s.setAttribute('aria-hidden', 'true');
    var u = document.createElementNS('http://www.w3.org/2000/svg', 'use'); u.setAttribute('href', '#' + id); s.appendChild(u); return s; }

  // ── meritev postaje ─────────────────────────────────────
  var obsMs = null;
  function setStatus(state, label) {
    var p = $('st-pill'); p.setAttribute('data-s', state);
    p.querySelector('use').setAttribute('href', state === 'fresh' ? '#i-ok' : state === 'unavailable' ? '#i-off' : '#i-clock');
    $('st-txt').textContent = label;
  }
  function tickAge() {
    if (obsMs == null) return;
    var a = ageMin(obsMs), th = FRESH.station;
    if (a <= th.fresh) { setStatus('fresh', 'Svež podatek'); $('st-time').textContent = 'Merjeno ob ' + hhmm(obsMs) + ' · star ' + ageTxt(a); }
    else if (a <= th.stale) { setStatus('stale', 'Zakasnjeno'); $('st-time').textContent = 'Zadnja znana meritev ob ' + hhmm(obsMs) + ' · star ' + ageTxt(a); }
    else { setStatus('unavailable', 'Meritev je zastarela'); $('st-time').textContent = 'Zadnja znana meritev ob ' + hhmm(obsMs) + ' · star ' + ageTxt(a); }
  }
  var lastTemp = null;
  function loadObs() {
    jget(PROXY + '/').then(function (d) {
      var o = d && d.observations && d.observations[0]; if (!o || !o.metric) throw new Error('Ni podatkov');
      var m = o.metric;
      obsMs = o.epoch ? o.epoch * 1000 : Date.parse(o.obsTimeUtc);
      lastTemp = m.temp;
      $('t-now').textContent = num(m.temp, 1) || '–';
      var feel = (m.temp != null && m.temp <= 10 && m.windChill != null) ? m.windChill : (m.temp != null && m.temp >= 27 && m.heatIndex != null) ? m.heatIndex : m.temp;
      $('t-feel').textContent = txt(feel, 1, '°C'); $('t-dew').textContent = txt(m.dewpt, 1, '°C');
      $('m-hum').textContent = num(o.humidity, 0) || '–';
      $('m-wind').textContent = num(m.windSpeed, 0) || '–';
      $('m-gust').textContent = 'sunki ' + txt(m.windGust, 0, 'km/h');
      $('m-rain').textContent = num(m.precipTotal, 1) || '–';
      $('m-rate').textContent = 'intenziteta ' + txt(m.precipRate, 1, 'mm/h');
      $('m-pres').textContent = num(m.pressure, 0) || '–';
      $('a-uv').textContent = txt(o.uv, 0); $('a-ws').textContent = txt(m.windSpeed, 0, 'km/h');
      $('a-dir').textContent = o.winddir == null ? 'Ni podatka' : dirName(o.winddir) + ' (' + Math.round(o.winddir) + '°)';
      tickAge(); renderValley();
    }).catch(function () {
      if (obsMs == null) { setStatus('unavailable', 'Podatek trenutno ni na voljo'); $('st-time').textContent = 'Meritve postaje ni bilo mogoče prebrati.'; }
      else tickAge();       // ohrani zadnjo znano vrednost, starost se samo povečuje
    });
  }
  function dirName(deg) { return ['S', 'SV', 'V', 'JV', 'J', 'JZ', 'Z', 'SZ'][Math.round(deg / 45) % 8]; }

  // ── današnji razpon: izmerjeno do zdaj (ločeno od napovedi) ──
  var measuredRange = false, modelRange = null;
  function setRange() {
    if (!measuredRange && modelRange) { $('t-range-l').textContent = 'Danes (napoved)'; $('t-range').textContent = modelRange; }
  }
  function loadToday() {
    jget(PROXY + '/hourly', 15000).then(function (d) {
      var today = new Intl.DateTimeFormat('sv-SE', { timeZone: TZ }).format(new Date()), hi = null, lo = null;
      (d.observations || []).forEach(function (o) {
        if (!o.obsTimeLocal || o.obsTimeLocal.slice(0, 10) !== today || !o.metric) return;
        var h = o.metric.tempHigh != null ? o.metric.tempHigh : o.metric.tempAvg, l = o.metric.tempLow != null ? o.metric.tempLow : o.metric.tempAvg;
        if (h != null && (hi == null || h > hi)) hi = h; if (l != null && (lo == null || l < lo)) lo = l;
      });
      if (lastTemp != null) { hi = hi == null ? lastTemp : Math.max(hi, lastTemp); lo = lo == null ? lastTemp : Math.min(lo, lastTemp); }
      if (hi == null || lo == null) throw new Error('prazno');
      measuredRange = true; $('t-range-l').textContent = 'Danes, izmerjeno do zdaj'; $('t-range').textContent = txt(lo, 1, '°') + ' do ' + txt(hi, 1, '°');
    }).catch(function () { setRange(); });
  }

  // ── napoved (Open-Meteo prek workerja) + MTR ────────────
  function localHourKey() {
    var p = new Intl.DateTimeFormat('sv-SE', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23' }).format(new Date());
    return p.replace(' ', 'T').slice(0, 13) + ':00';   // npr. 2026-11-03T15:00
  }
  function loadForecast() {
    Promise.all([jget(PROXY + '/napoved-om'), jget('/napoved-modela-live.json').catch(function () { return null; })]).then(function (r) {
      var j = r[0], mtr = r[1]; if (!j || !j.hourly || !j.daily) throw new Error('oblika');
      var H = j.hourly, D = j.daily, i0 = H.time.indexOf(localHourKey()); if (i0 < 0) i0 = 0;
      var ic = wmo(H.weather_code[i0], H.is_day[i0]);
      $('c-ic').setAttribute('href', '#' + ic[0]); $('c-txt').textContent = ic[1];
      modelRange = txt(D.temperature_2m_min[0], 0, '°') + ' do ' + txt(D.temperature_2m_max[0], 0, '°'); setRange();
      renderHourly(H, i0); renderDaily(D, mtr);
    }).catch(function () {
      $('c-txt').textContent = 'Razmere niso na voljo'; if (!measuredRange) $('t-range').textContent = 'Ni podatka';
      $('h-list').textContent = ''; $('h-list').appendChild(el('p', 'dv-muted', 'Podatek trenutno ni na voljo.'));
      $('d-list').textContent = ''; $('d-list').appendChild(el('p', 'dv-muted', 'Podatek trenutno ni na voljo.'));
    });
  }
  function renderHourly(H, i0) {
    var box = $('h-list'); box.textContent = '';
    for (var k = 0; k < 24 && i0 + k < H.time.length; k++) (function (i, k) {
      var b = el('button', 'dv-hr'); b.type = 'button'; b.setAttribute('aria-pressed', 'false');
      var ic = wmo(H.weather_code[i], H.is_day[i]);
      b.appendChild(el('span', null, k === 0 ? 'Zdaj' : H.time[i].slice(11, 16)));
      b.appendChild(icon(ic[0]));
      b.appendChild(el('b', null, txt(H.temperature_2m[i], 0, '°')));
      b.appendChild(el('span', null, H.precipitation_probability[i] == null ? '' : Math.round(H.precipitation_probability[i]) + ' %'));
      b.addEventListener('click', function () {
        box.querySelectorAll('.dv-hr').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
        b.setAttribute('aria-pressed', 'true');
        $('h-detail').textContent = 'Ob ' + H.time[i].slice(11, 16) + ': ' + ic[1] + ', ' + txt(H.temperature_2m[i], 1, '°C') + ', verjetnost padavin ' +
          txt(H.precipitation_probability[i], 0, '%') + ', količina ' + txt(H.precipitation[i], 1, 'mm') + ' (model Open-Meteo, ura velja za prejšnjo uro).';
      });
      box.appendChild(b);
    })(i0 + k, k);
  }
  function renderDaily(D, mtr) {
    var box = $('d-list'); box.textContent = '';
    var mtrBy = {}; if (mtr && mtr.days) mtr.days.forEach(function (d) { mtrBy[d.date] = d; });
    for (var i = 0; i < 7 && i < D.time.length; i++) (function (i) {
      var date = D.time[i], dt = new Date(date + 'T12:00:00');
      var b = el('button', 'dv-day'); b.type = 'button'; b.setAttribute('aria-pressed', 'false');
      var ic = wmo(D.weather_code[i], 1);
      b.appendChild(el('b', null, i === 0 ? 'Danes' : dt.toLocaleDateString('sl-SI', { weekday: 'short', timeZone: TZ }) + ' ' + dt.getDate() + '.'));
      b.appendChild(icon(ic[0]));
      b.appendChild(el('div', 'mx', txt(D.temperature_2m_max[i], 0, '°')));
      b.appendChild(el('div', 'mn', txt(D.temperature_2m_min[i], 0, '°')));
      b.appendChild(el('small', null, txt(D.precipitation_sum[i], 1, 'mm') + ' · ' + txt(D.precipitation_probability_max[i], 0, '%')));
      var mt = mtrBy[date];
      if (mt) b.appendChild(el('small', null, 'MTR ' + txt(mt.tmax, 0, '°') + ' / ' + txt(mt.tmin, 0, '°')));
      b.addEventListener('click', function () {
        box.querySelectorAll('.dv-day').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
        b.setAttribute('aria-pressed', 'true');
        var s = dt.toLocaleDateString('sl-SI', { weekday: 'long', day: 'numeric', month: 'long', timeZone: TZ }) + ': ' + ic[1] +
          '. Open-Meteo: ' + txt(D.temperature_2m_max[i], 1, '°C') + ' / ' + txt(D.temperature_2m_min[i], 1, '°C') + ', padavine ' + txt(D.precipitation_sum[i], 1, 'mm') +
          ', največ ' + txt(D.wind_speed_10m_max[i], 0, 'km/h') + ' vetra, UV do ' + txt(D.uv_index_max[i], 0) + '.';
        if (mt) {
          s += ' MTR (lastni model Meteorec): ' + txt(mt.tmax, 1, '°C') + ' / ' + txt(mt.tmin, 1, '°C') + '.';
          // Veter: MTR je umerjen na zavetrno dno doline, surov model je tam ~2× previsok (zato ju vedno označimo).
          if (mt.wind != null) s += ' Veter v dolini (MTR, umerjen na postajo): povprečje ' + txt(mt.wind, 0, 'km/h') + (mt.gust != null ? ', sunki do ' + txt(mt.gust, 0, 'km/h') : '') +
            (mt.om_wind != null ? '; surov Open-Meteo: ' + txt(mt.om_wind, 0, 'km/h') + (mt.om_gust != null ? ', sunki ' + txt(mt.om_gust, 0, 'km/h') : '') : '') + '.';
        }
        else s += ' MTR za ta dan ni na voljo.';
        $('d-detail').textContent = s;
      });
      box.appendChild(b);
    })(i);
  }

  // ── nowcast (radar ARSO prek workerja) ──────────────────
  function loadNowcast() {
    jget(PROXY + '/nowcast?vas=recica').then(function (d) {
      var v = d && d.vasi && d.vasi[0]; if (!v) throw new Error('prazno');
      var n = function (x) { return num(x, 1); };
      var zeDez = v.zdaj >= 6, zeNev = v.zdaj >= 10, main, sub = '';
      if (v.toca && !(v.zdaj >= 12)) { main = 'Možnost toče čez ~' + v.jedro + ' min'; sub = 'Radar kaže močno jedro na poti proti vasi.'; }
      else if (v.nevihta != null && !zeNev) { main = 'Nevihta čez ~' + v.nevihta + ' min'; sub = 'Radar kaže nevihtno celico na poti proti vasi.'; }
      else if (zeNev) { main = 'Nevihta nad vasjo'; sub = 'Približno ' + n(v.zdajMmh) + ' mm/h.'; }
      else if (v.dez != null && !zeDez) { main = 'Dež čez ~' + v.dez + ' min'; sub = 'Padavine se približujejo z radarske slike.'; }
      else if (zeDez) { main = 'Nad vasjo dežuje'; sub = 'Približno ' + n(v.zdajMmh) + ' mm/h.'; }
      else { main = 'V naslednjih 45 minutah ni zaznanih padavin na poti.'; }
      $('nc-main').textContent = main; $('nc-sub').textContent = sub;
      var st = d.starost_min, old = st != null && st > FRESH.radar;
      $('nc-foot').textContent = 'Radar ARSO, star ' + (st == null ? '?' : st) + ' min' + (old ? ' (zakasnjeno)' : '') + '. Nowcast iz radarske slike, ne napoved; po ~30 minutah zanesljivost pade.';
    }).catch(function () {
      $('nc-main').textContent = 'Podatek trenutno ni na voljo'; $('nc-sub').textContent = 'Radarskega pregleda ni bilo mogoče prebrati. To ne pomeni, da ne bo padavin.'; $('nc-foot').textContent = '';
    });
  }

  // ── dolina ──────────────────────────────────────────────
  var drsi = null, varpolje = null, valleyLoaded = 0;
  function loadValley() {
    Promise.all([jget(PROXY + '/crnivec-drsi').catch(function () { return null; }), jget(PROXY + '/varpolje-current').catch(function () { return null; })]).then(function (r) {
      drsi = r[0]; varpolje = r[1]; valleyLoaded = 1; renderValley();
    });
  }
  function renderValley() {
    var ul = $('v-list'); if (!valleyLoaded) return; ul.textContent = '';
    function row(name, sub, t, ts, maxAge) {
      var li = el('li'); var a = el('span'); a.appendChild(el('strong', null, name));
      li.appendChild(a); li.appendChild(el('b', null, txt(t, 1, '°C')));
      var age = ts ? ageMin(ts) : null, stale = age != null && age > maxAge;
      li.appendChild(el('small', null, sub + (age == null ? '' : ' · ob ' + hhmm(ts) + (stale ? ' · podatek je star ' + ageTxt(age) : ''))));
      ul.appendChild(li);
    }
    if (lastTemp != null) row('Rečica ob Savinji', 'postaja IREICA1 · 366 m', lastTemp, obsMs, FRESH.station.fresh);
    if (varpolje && varpolje.current && varpolje.current.temp_c != null)
      row('Varpolje', 'postaja IREICA7 (sosed) · isto dno doline', varpolje.current.temp_c, varpolje.updated_utc ? Date.parse(varpolje.updated_utc) : null, FRESH.varpolje);
    var p = drsi && drsi.postaje;
    if (p && p.gornji_grad && p.gornji_grad.temp_c != null) row('Gornji Grad', 'postaja DRSI · 428 m', p.gornji_grad.temp_c, p.gornji_grad.ts ? Date.parse(p.gornji_grad.ts) : null, FRESH.drsi);
    if (p && p.crnivec && p.crnivec.temp_c != null) row('Črnivec', 'postaja DRSI · 903 m', p.crnivec.temp_c, p.crnivec.ts ? Date.parse(p.crnivec.ts) : null, FRESH.drsi);
    if (!ul.children.length) ul.appendChild(el('li', 'dv-muted', 'Podatek trenutno ni na voljo.'));
  }

  // ── blog ────────────────────────────────────────────────
  function loadBlog() {
    jget('/blog.json').then(function (arr) {
      arr.sort(function (a, b) { return a.date < b.date ? 1 : -1; });
      var box = $('b-list');
      arr.slice(0, 3).forEach(function (p) {
        var a = el('a', 'dv-card dv-post'); a.href = p.url;
        a.appendChild(el('small', null, new Date(p.date + 'T12:00:00').toLocaleDateString('sl-SI', { day: 'numeric', month: 'long', year: 'numeric' })));
        a.appendChild(el('h3', null, p.title)); a.appendChild(el('p', null, p.summary || ''));
        box.appendChild(a);
      });
    }).catch(function () { $('b-list').appendChild(el('p', 'dv-muted', 'Objav trenutno ni mogoče naložiti.')); });
  }
})();
