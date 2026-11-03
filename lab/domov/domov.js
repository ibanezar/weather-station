/* Prototip nove domače strani (lab), iteracija 3. Isti viri kot produkcija (worker: /, /hourly, /napoved-om, /nowcast,
   /crnivec-drsi, /varpolje-current; datoteki napoved-modela-live.json in blog.json). Samo zunanje meritve.
   Preizkus stanj: ?nowcast=suho|priblizuje|nad|nevihta simulira nowcast (označeno na strani). */
(function () {
  'use strict';
  var PROXY = 'https://weatherireica1.filip-eremita.workers.dev';
  var OM = 'https://api.open-meteo.com/v1/forecast?latitude=46.325779&longitude=14.921137';
  // Središčna konfiguracija pragov svežine (minute) po viru (specifikacija 10.2/10.4).
  var FRESH = { station: { fresh: 20, stale: 90 }, drsi: 40, varpolje: 30, radar: 20 };
  var TZ = 'Europe/Ljubljana', NBSP = ' ';
  var $ = function (id) { return document.getElementById(id); };
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  // ── zapis ───────────────────────────────────────────────
  function num(v, d) {                       // ničla je veljavna vrednost, manjkajoče ni nič
    if (v == null || v === '' || isNaN(Number(v))) return null;
    return Number(v).toLocaleString('sl-SI', { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function txt(v, d, unit) { var n = num(v, d); return n == null ? 'Ni podatka' : n + (unit ? (unit === '°' ? '' : NBSP) + unit : ''); }
  function hhmm(ms) { return new Date(ms).toLocaleTimeString('sl-SI', { hour: '2-digit', minute: '2-digit', timeZone: TZ }); }
  function ageMin(ms) { return Math.max(0, Math.round((Date.now() - ms) / 60000)); }
  function ageTxt(m) { return m < 60 ? m + ' min' : Math.floor(m / 60) + ' h ' + (m % 60) + ' min'; }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function tag(src, label) { var e = el('em', 'dv-tag', label); e.setAttribute('data-src', src); return e; }
  function jget(url, ms) {
    var c = new AbortController(), t = setTimeout(function () { c.abort(); }, ms || 10000);
    return fetch(url, { signal: c.signal }).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .finally(function () { clearTimeout(t); });
  }
  function upd(id, text) { var e = $(id); if (e) e.textContent = text; }
  function dirName(deg) { return ['S', 'SV', 'V', 'JV', 'J', 'JZ', 'Z', 'SZ'][Math.round(deg / 45) % 8]; }
  function dirName16(deg) { return ['S', 'SSV', 'SV', 'VSV', 'V', 'VJV', 'JV', 'JJV', 'J', 'JJZ', 'JZ', 'ZJZ', 'Z', 'ZSZ', 'SZ', 'SSZ'][Math.round(deg / 22.5) % 16]; }
  // nadomestno stanje z možnostjo ponovnega poskusa (specifikacija 10.3)
  function fail(box, msg, again) {
    box.textContent = ''; var w = el('div', 'dv-fail'); w.appendChild(el('span', null, msg));
    if (again) { var b = el('button', 'dv-retry', 'Poskusi znova'); b.type = 'button'; b.addEventListener('click', function () { w.firstChild.textContent = 'Nalagam …'; again(); }); w.appendChild(b); }
    box.appendChild(w);
  }
  // vrednost + manjša enota v isti oznaki (mreža meritev)
  function tile(id, v, d, unit, sub) {
    var b = $(id); if (!b) return; var n = num(v, d); b.textContent = n == null ? 'Ni podatka' : n;
    if (n != null && unit) b.appendChild(el('em', null, unit));
    var s = $(id + '-s'); if (s) s.textContent = sub || '';
  }
  function uvLevel(u) { return u == null ? '' : u <= 2 ? 'nizek' : u <= 5 ? 'zmeren' : u <= 7 ? 'visok' : u <= 10 ? 'zelo visok' : 'ekstremen'; }

  // ── tema, način prikaza, meni Več, info ikone ───────────
  var MODE_TXT = {
    simple: 'Preprosto: osnovno vreme, napoved in najpomembnejše lokalne meritve.',
    advanced: 'Napredno: dodatne meritve, več podrobnosti pri urah in dnevih ter razlaga virov.'
  };
  function setMode(m) {
    document.body.setAttribute('data-mode', m);
    document.querySelectorAll('[data-dv-mode]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-dv-mode') === m)); });
    $('mode-desc').textContent = MODE_TXT[m]; set('wx-lab-mode', m);
  }
  function setupSheet() {
    var sh = $('sheet'), btn = $('more-btn'), panel = sh.querySelector('.dv-sheet-p'), opener = null;
    function focusables() { return Array.prototype.slice.call(panel.querySelectorAll('a[href],button')); }
    function open() { opener = document.activeElement; sh.hidden = false; document.body.classList.add('dv-lock'); btn.setAttribute('aria-expanded', 'true'); panel.focus(); }
    function close() { sh.hidden = true; document.body.classList.remove('dv-lock'); btn.setAttribute('aria-expanded', 'false'); if (opener) opener.focus(); }
    btn.addEventListener('click', open);
    sh.querySelectorAll('[data-close]').forEach(function (b) { b.addEventListener('click', close); });
    sh.addEventListener('click', function (e) { if (e.target.closest('.dv-sheet-p a')) close(); });
    document.addEventListener('keydown', function (e) {
      if (sh.hidden) return;
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Tab') return;
      var f = focusables(); if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === panel)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }
  document.addEventListener('DOMContentLoaded', function () {
    // laboratorijska orodna vrstica je samo na zahtevo (?lab=1); ob prenosu v produkcijo se ta veja odstrani
    if (/[?&]lab=1/.test(location.search)) $('lab-bar').hidden = false;
    $('theme-btn').addEventListener('click', function () {
      var t = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', t); set('lab-theme', t);
    });
    setMode(get('wx-lab-mode') === 'advanced' ? 'advanced' : 'simple');   // privzeto Preprosto
    document.querySelectorAll('[data-dv-mode]').forEach(function (b) { b.addEventListener('click', function () { setMode(b.getAttribute('data-dv-mode')); }); });
    document.addEventListener('click', function (e) {          // info ikone: odpri/zapri pojasnilo
      var b = e.target.closest('.dv-info'); if (!b) return;
      var t = $(b.getAttribute('aria-controls')), open = b.getAttribute('aria-expanded') !== 'true';
      b.setAttribute('aria-expanded', String(open)); if (t) t.hidden = !open;
    });
    setupSheet();
    loadObs(); loadToday(); loadForecast(); loadNowcast(); loadValley(); loadBlog(); spy();
    setInterval(loadObs, 5 * 60000); setInterval(loadToday, 15 * 60000); setInterval(loadNowcast, 5 * 60000); setInterval(tickAge, 30000);
  });
  function spy() {
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
  }

  // ── vremenske kode (WMO) ────────────────────────────────
  function wmo(code, isDay) {
    if (code === 0) return isDay === 0 ? ['w-moon', 'Jasno', 'night'] : ['w-sun', 'Jasno', 'clear'];
    if (code === 1) return isDay === 0 ? ['w-moon', 'Pretežno jasno', 'night'] : ['w-sun', 'Pretežno jasno', 'clear'];
    if (code === 2) return ['w-part', 'Delno oblačno', isDay === 0 ? 'night' : 'clear'];
    if (code === 3) return ['w-cloud', 'Oblačno', 'cloud'];
    if (code === 45 || code === 48) return ['w-fog', 'Megla', 'fog'];
    if (code >= 51 && code <= 57) return ['w-rain', 'Rahlo rosenje', 'rain'];
    if (code >= 61 && code <= 67) return ['w-rain', 'Dež', 'rain'];
    if ((code >= 71 && code <= 77) || code === 85 || code === 86) return ['w-snow', 'Sneg', 'snow'];
    if (code >= 80 && code <= 82) return ['w-rain', 'Plohe', 'rain'];
    if (code >= 95) return ['w-storm', 'Nevihta', 'storm'];
    return ['w-cloud', 'Razmere niso znane', 'cloud'];
  }
  function icon(id) { var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('class', 'dv-wic'); s.setAttribute('aria-hidden', 'true');
    var u = document.createElementNS('http://www.w3.org/2000/svg', 'use'); u.setAttribute('href', '#' + id); s.appendChild(u); return s; }

  // ── meritev postaje ─────────────────────────────────────
  var obsMs = null, lastObs = null, hourlyObs = [];
  function setStatus(state, label) {
    var p = $('st-pill'); p.setAttribute('data-s', state);
    p.querySelector('use').setAttribute('href', state === 'fresh' ? '#i-ok' : state === 'unavailable' ? '#i-off' : '#i-clock');
    $('st-txt').textContent = label;
    var f = $('hero-fresh'); f.setAttribute('data-s', state); f.textContent = state === 'fresh' ? 'Svež podatek' : state === 'stale' ? 'Zakasnjeno' : state === 'unavailable' ? 'Zastarela meritev' : label;
    $('hero-stale').hidden = !(state === 'stale' || state === 'unavailable');
  }
  function tickAge() {
    if (obsMs == null) return;
    var a = ageMin(obsMs), th = FRESH.station, when;
    if (a <= th.fresh) { setStatus('fresh', 'Svež podatek'); when = 'izmerjeno ob ' + hhmm(obsMs) + ' · star ' + ageTxt(a); }
    else if (a <= th.stale) { setStatus('stale', 'Zakasnjeno'); when = 'zadnja meritev ob ' + hhmm(obsMs) + ' · star ' + ageTxt(a); }
    else { setStatus('unavailable', 'Meritev je zastarela'); when = 'zadnja meritev ob ' + hhmm(obsMs) + ' · star ' + ageTxt(a); }
    $('st-time').textContent = when.charAt(0).toUpperCase() + when.slice(1); $('hero-when').textContent = when;
    renderValley();
  }
  function loadObs() {
    jget(PROXY + '/').then(function (d) {
      var o = d && d.observations && d.observations[0]; if (!o || !o.metric) throw new Error('Ni podatkov');
      var m = o.metric; lastObs = o;
      obsMs = o.epoch ? o.epoch * 1000 : Date.parse(o.obsTimeUtc);
      $('t-now').textContent = num(m.temp, 1) || '–';
      var feel = (m.temp != null && m.temp <= 10 && m.windChill != null) ? m.windChill : (m.temp != null && m.temp >= 27 && m.heatIndex != null) ? m.heatIndex : m.temp;
      $('t-feel').textContent = txt(feel, 1, '°C'); $('t-dew').textContent = txt(m.dewpt, 1, '°C');
      $('m-hum').textContent = num(o.humidity, 0) || '–';
      $('m-wind').textContent = num(m.windSpeed, 0) || '–';
      $('m-gust').textContent = (o.winddir != null ? dirName(o.winddir) + ' · ' : '') + 'sunki ' + txt(m.windGust, 0, 'km/h');
      $('m-rain').textContent = num(m.precipTotal, 1) || '–';
      $('m-rate').textContent = 'intenziteta ' + txt(m.precipRate, 1, 'mm/h');
      $('m-pres').textContent = num(m.pressure, 0) || '–';
      // več meritev, 1. raven (vizualna mreža)
      tile('a-uv', o.uv, 0, '', uvLevel(o.uv));
      tile('a-ws', m.windSpeed, 0, 'km/h', 'sunki ' + txt(m.windGust, 0, 'km/h'));
      var dn = o.winddir == null ? null : dirName16(o.winddir);
      $('a-dir').textContent = dn || 'Ni podatka'; $('a-dir-s').textContent = o.winddir == null ? '' : Math.round(o.winddir) + '° (od kod piha)';
      tile('a-dew', m.dewpt, 1, '°C', 'zrak je nasičen pri tej temperaturi');
      tile('a-sol', o.solarRadiation, 0, 'W/m²', '');
      // 2. raven
      tile('a-feel', feel, 1, '°C'); tile('a-chill', m.windChill, 1, '°C'); tile('a-heat', m.heatIndex, 1, '°C'); tile('a-rate', m.precipRate, 1, 'mm/h');
      tickAge(); renderTrends(); renderValley(); renderRange();
    }).catch(function () {
      if (obsMs == null) {
        setStatus('unavailable', 'Podatek trenutno ni na voljo'); $('st-time').textContent = 'Meritve postaje ni bilo mogoče prebrati.';
        $('hero-when').textContent = 'podatek trenutno ni na voljo';
        if (!$('hero-retry')) { var b = el('button', 'dv-retry', 'Poskusi znova'); b.id = 'hero-retry'; b.type = 'button'; b.addEventListener('click', function () { b.remove(); loadObs(); }); $('hero-stale').insertAdjacentElement('afterend', b); }
        $('hero-stale').hidden = true;
      } else tickAge();       // ohrani zadnjo znano vrednost, starost se samo povečuje
    });
  }

  // ── današnji razpon in trendi iz urnih meritev (samo kadar so podatki na voljo) ──
  var measuredRange = false, modelRange = null;
  function setRangeModel() { if (!measuredRange && modelRange) { $('t-range-l').textContent = 'Danes (napoved)'; $('t-range').textContent = modelRange; } }
  function renderRange() {
    if (!hourlyObs.length || !lastObs) return;
    var today = new Intl.DateTimeFormat('sv-SE', { timeZone: TZ }).format(new Date()), hi = null, lo = null, cur = lastObs.metric.temp;
    hourlyObs.forEach(function (o) {
      if (!o.obsTimeLocal || o.obsTimeLocal.slice(0, 10) !== today || !o.metric) return;
      var h = o.metric.tempHigh != null ? o.metric.tempHigh : o.metric.tempAvg, l = o.metric.tempLow != null ? o.metric.tempLow : o.metric.tempAvg;
      if (h != null && (hi == null || h > hi)) hi = h; if (l != null && (lo == null || l < lo)) lo = l;
    });
    if (cur != null) { hi = hi == null ? cur : Math.max(hi, cur); lo = lo == null ? cur : Math.min(lo, cur); }
    if (hi == null || lo == null) return;
    measuredRange = true; $('t-range-l').textContent = 'Danes, izmerjeno do zdaj'; $('t-range').textContent = txt(lo, 1, '°') + ' do ' + txt(hi, 1, '°');
  }
  function loadToday() {
    jget(PROXY + '/hourly', 15000).then(function (d) { hourlyObs = d.observations || []; renderRange(); renderTrends(); }).catch(function () { setRangeModel(); });
  }
  function ref3h() {
    if (!hourlyObs.length || obsMs == null) return null;
    var want = obsMs - 3 * 3600e3, best = null, bd = 1e12;
    hourlyObs.forEach(function (o) { var t = o.epoch * 1000, dd = Math.abs(t - want); if (dd < bd) { bd = dd; best = o; } });
    return best && bd <= 45 * 60000 ? best : null;
  }
  function renderTrends() {
    var r = ref3h(), o = lastObs; if (!o || !r) return;
    var rm = r.metric || {}, hNow = o.humidity, hThen = r.humidityAvg != null ? r.humidityAvg : r.humidity;
    var pNow = o.metric.pressure, pThen = (rm.pressureMax != null && rm.pressureMin != null) ? (rm.pressureMax + rm.pressureMin) / 2 : rm.pressure;
    if (hNow != null && hThen != null) { var dh = hNow - hThen; $('m-hum-s').textContent = Math.abs(dh) < 3 ? 'stabilna (3 h)' : (dh > 0 ? 'narašča' : 'pada') + ' (' + (dh > 0 ? '+' : '−') + num(Math.abs(dh), 0) + ' % v 3 h)'; }
    if (pNow != null && pThen != null) { var dp = pNow - pThen; $('m-pres-s').textContent = Math.abs(dp) < 1 ? 'stabilen (3 h)' : (dp > 0 ? 'raste' : 'pada') + ' (' + (dp > 0 ? '+' : '−') + num(Math.abs(dp), 1) + ' hPa v 3 h)'; }
  }

  // ── napoved (Open-Meteo prek workerja) + MTR + oblačnost ─
  function localHourKey() {
    var p = new Intl.DateTimeFormat('sv-SE', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23' }).format(new Date());
    return p.replace(' ', 'T').slice(0, 13) + ':00';
  }
  // povprečna dnevna oblačnost: worker je ne vrača, zato en klic Open-Meteo (predpomnilnik 1 h); brez nje se pove »ni na voljo«
  function loadCloud() {
    var k = 'wx-lab-cloud-v1', c = get(k);
    try { c = c && JSON.parse(c); } catch (e) { c = null; }
    if (c && Date.now() - c.ts < 3600e3) return Promise.resolve(c.d);
    return jget(OM + '&daily=cloud_cover_mean&timezone=Europe%2FLjubljana&forecast_days=8', 8000).then(function (j) {
      var m = {}; ((j.daily || {}).time || []).forEach(function (t, i) { m[t] = j.daily.cloud_cover_mean[i]; }); set(k, JSON.stringify({ ts: Date.now(), d: m })); return m;
    }).catch(function () { return c ? c.d : null; });
  }
  var cloudMap = null, selDay = 0, dayCtx = null;
  function loadForecast() {
    Promise.all([jget(PROXY + '/napoved-om'), jget('/napoved-modela-live.json').catch(function () { return null; })]).then(function (r) {
      var j = r[0], mtr = r[1]; if (!j || !j.hourly || !j.daily) throw new Error('oblika');
      var H = j.hourly, D = j.daily, i0 = H.time.indexOf(localHourKey()); if (i0 < 0) i0 = 0;
      var ic = wmo(H.weather_code[i0], H.is_day[i0]);
      $('c-ic').setAttribute('href', '#' + ic[0]); $('c-txt').textContent = ic[1]; $('hero').setAttribute('data-wx', ic[2]);
      $('hero-model').textContent = 'Vremenski opis: modelski podatek (Open-Meteo) · prenos ob ' + hhmm(Date.now());
      modelRange = txt(D.temperature_2m_min[0], 0, '°') + ' do ' + txt(D.temperature_2m_max[0], 0, '°'); setRangeModel();
      var got = 'Preneseno ob ' + hhmm(Date.now());
      upd('u-h', got + ' · model Open-Meteo');
      upd('u-d', got + (mtr && mtr.generated_at ? ' · MTR izračunan ob ' + hhmm(Date.parse(mtr.generated_at)) : ''));
      renderHourly(H, i0); renderDaily(D, mtr);
      // oblačnost je dodaten klic: ne sme blokirati prikaza, panel dneva se osveži, ko pride
      loadCloud().then(function (c) { cloudMap = c; if (dayCtx) showDay(dayCtx.D, dayCtx.mtrBy, selDay); });
    }).catch(function () {
      $('c-txt').textContent = 'Razmere niso na voljo'; $('hero-model').textContent = 'Vremenski opis: modelski podatek (Open-Meteo) trenutno ni na voljo';
      if (!measuredRange) $('t-range').textContent = 'Ni podatka';
      fail($('h-list'), 'Urne napovedi trenutno ni mogoče prebrati.', loadForecast);
      fail($('d-list'), 'Sedemdnevne napovedi trenutno ni mogoče prebrati.', loadForecast);
      $('d-detail').hidden = true;
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
      b.appendChild(el('span', 'dv-advonly', txt(H.precipitation[i], 1, 'mm')));
      b.addEventListener('click', function () {
        box.querySelectorAll('.dv-hr').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
        b.setAttribute('aria-pressed', 'true');
        $('h-detail').textContent = 'Ob ' + H.time[i].slice(11, 16) + ': ' + ic[1] + ', ' + txt(H.temperature_2m[i], 1, '°C') + ', verjetnost padavin ' +
          txt(H.precipitation_probability[i], 0, '%') + ', količina ' + txt(H.precipitation[i], 1, 'mm') + ' (model Open-Meteo, ura velja za prejšnjo uro).';
      });
      box.appendChild(b);
    })(i0 + k, k);
  }
  function cloudWord(c) { return c == null ? null : c < 20 ? 'jasno' : c < 50 ? 'delno oblačno' : c < 85 ? 'pretežno oblačno' : 'oblačno'; }
  function cmpBox(src, title, rows) {
    var d = el('div'); d.setAttribute('data-src', src); var h = el('h4'); h.appendChild(tag(src, title)); d.appendChild(h);
    rows.forEach(function (r) { var p = el('p', 'dv-muted'); p.appendChild(document.createTextNode(r[0] + ': ')); p.appendChild(el('b', null, r[1])); d.appendChild(p); }); return d;
  }
  function showDay(D, mtrBy, i) {
    selDay = i; var cloud = cloudMap;
    var date = D.time[i], dt = new Date(date + 'T12:00:00'), ic = wmo(D.weather_code[i], 1), mt = mtrBy[date], p = $('d-detail');
    p.hidden = false; p.textContent = '';
    p.appendChild(el('h3', null, dt.toLocaleDateString('sl-SI', { weekday: 'long', day: 'numeric', month: 'long', timeZone: TZ }) + ' · ' + ic[1]));
    var c = cloud ? cloud[date] : null;
    var l = el('div', 'dv-cmp');
    l.appendChild(cmpBox('model', 'Open-Meteo', [
      ['Najvišja / najnižja', txt(D.temperature_2m_max[i], 1, '°C') + ' / ' + txt(D.temperature_2m_min[i], 1, '°C')],
      ['Padavine', txt(D.precipitation_sum[i], 1, 'mm') + ', verjetnost do ' + txt(D.precipitation_probability_max[i], 0, '%')],
      ['Oblačnost', c == null ? 'ni na voljo' : Math.round(c) + ' % (' + cloudWord(c) + ')'],
      ['Veter, največ (surov model)', txt(D.wind_speed_10m_max[i], 0, 'km/h') + ', v dolini previsok'],
      ['UV, največ', txt(D.uv_index_max[i], 0)]
    ]));
    if (mt) {
      var rows = [['Najvišja / najnižja', txt(mt.tmax, 1, '°C') + ' / ' + txt(mt.tmin, 1, '°C')]];
      if (mt.pop != null) rows.push(['Verjetnost padavin', txt(mt.pop * 100, 0, '%')]);
      if (mt.mm != null) rows.push(['Padavine', txt(mt.mm, 1, 'mm')]);
      if (mt.wind != null) rows.push(['Veter v dolini (umerjen)', txt(mt.wind, 0, 'km/h') + (mt.gust != null ? ', sunki do ' + txt(mt.gust, 0, 'km/h') : '')]);
      l.appendChild(cmpBox('mtr', 'MTR', rows));
    } else {
      var n = el('div'); n.setAttribute('data-src', 'mtr'); var h = el('h4'); h.appendChild(tag('mtr', 'MTR')); n.appendChild(h); n.appendChild(el('p', 'dv-muted', 'MTR ni na voljo za ta dan (model napoveduje samo prve dni).')); l.appendChild(n);
    }
    p.appendChild(l);
    if (mt && D.temperature_2m_max[i] != null && mt.tmax != null && mt.tmin != null) {
      var dx = mt.tmax - D.temperature_2m_max[i], dn = mt.tmin - D.temperature_2m_min[i], sg = function (v) { return (v > 0 ? '+' : v < 0 ? '−' : '') + num(Math.abs(v), 1); };
      p.appendChild(el('p', 'dv-delta', 'MTR proti Open-Meteo: najvišja ' + sg(dx) + ' °C, najnižja ' + sg(dn) + ' °C.'));
    }
  }
  function renderDaily(D, mtr) {
    var box = $('d-list'); box.textContent = '';
    var mtrBy = {}; if (mtr && mtr.days) mtr.days.forEach(function (d) { mtrBy[d.date] = d; });
    for (var i = 0; i < 7 && i < D.time.length; i++) (function (i) {
      var date = D.time[i], dt = new Date(date + 'T12:00:00');
      var b = el('button', 'dv-day'); b.type = 'button'; b.setAttribute('aria-pressed', 'false');
      var ic = wmo(D.weather_code[i], 1), mt = mtrBy[date];
      b.setAttribute('aria-label', dt.toLocaleDateString('sl-SI', { weekday: 'long', day: 'numeric', month: 'long', timeZone: TZ }) + ', ' + ic[1] + ', najvišja ' + txt(D.temperature_2m_max[i], 0, '°C') + ', najnižja ' + txt(D.temperature_2m_min[i], 0, '°C'));
      b.appendChild(el('b', null, i === 0 ? 'Danes' : dt.toLocaleDateString('sl-SI', { weekday: 'short', timeZone: TZ }) + ' ' + dt.getDate() + '.'));
      b.appendChild(icon(ic[0]));
      b.appendChild(el('div', 'mx', txt(D.temperature_2m_max[i], 0, '°')));
      b.appendChild(el('div', 'mn', txt(D.temperature_2m_min[i], 0, '°')));
      b.appendChild(el('small', null, txt(D.precipitation_probability_max[i], 0, '%')));
      b.appendChild(el('small', null, txt(D.precipitation_sum[i], 1, 'mm')));
      if (mt) b.appendChild(el('small', 'mt', 'MTR\n' + txt(mt.tmax, 0, '°') + '/' + txt(mt.tmin, 0, '°')));
      else b.appendChild(el('small', 'none', 'MTR\nni na voljo'));       // brez praznine in brez izmišljene vrednosti
      b.appendChild(el('small', 'dv-advonly', 'UV ' + txt(D.uv_index_max[i], 0)));
      b.addEventListener('click', function () {
        box.querySelectorAll('.dv-day').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
        b.setAttribute('aria-pressed', 'true'); showDay(D, mtrBy, i);
      });
      box.appendChild(b);
    })(i);
    var first = box.querySelector('.dv-day'); dayCtx = { D: D, mtrBy: mtrBy };
    if (first) { first.setAttribute('aria-pressed', 'true'); showDay(D, mtrBy, 0); }   // podrobnosti danes so vidne takoj
  }

  // ── nowcast: tri stanja (brez padavin / se približujejo / nad območjem) ──
  function jakost(mmh) { return mmh < 2.5 ? 'šibke' : mmh < 7.6 ? 'zmerne' : 'močne'; }
  function simNowcast(kind) {
    var z = function (n) { var a = []; for (var t = 5; t <= 45; t += 5) a.push({ t: t, l: 0, mmh: n(t) }); return a; };
    var base = { ts: new Date().toISOString(), starost_min: 4, premik: { kmh: 32, smer: 225 } };
    if (kind === 'suho') return { ts: base.ts, starost_min: 4, premik: { kmh: 0, smer: 180 }, vasi: [{ zdaj: 0, zdajMmh: 0, dez: null, nevihta: null, jedro: null, toca: false, potek: z(function () { return 0; }) }] };
    if (kind === 'priblizuje') return Object.assign(base, { vasi: [{ zdaj: 0, zdajMmh: 0, dez: 20, nevihta: null, toca: false, potek: z(function (t) { return t < 20 ? 0 : 0.3 + (t - 20) / 25 * 0.5; }) }] });
    if (kind === 'nevihta') return Object.assign(base, { vasi: [{ zdaj: 0, zdajMmh: 0, dez: 15, nevihta: 25, toca: false, potek: z(function (t) { return t < 15 ? 0 : t < 35 ? 6 + (t - 15) / 4 : 9; }) }] });
    return Object.assign(base, { vasi: [{ zdaj: 8, zdajMmh: 2.4, dez: null, nevihta: null, toca: false, potek: z(function (t) { return t < 30 ? 2.4 - t / 30 * 1.4 : 0; }) }] });
  }
  function ncState(state, ic, label) { $('nc-card').setAttribute('data-state', state); $('nc-ic').setAttribute('href', '#' + ic); $('nc-st').textContent = label; }
  function loadNowcast() {
    var sim = (location.search.match(/[?&]nowcast=(suho|priblizuje|nad|nevihta)/) || [])[1];
    (sim ? Promise.resolve(simNowcast(sim)) : jget(PROXY + '/nowcast?vas=recica')).then(function (d) {
      var v = d && d.vasi && d.vasi[0]; if (!v) throw new Error('prazno');
      var n1 = function (x) { return num(x, 1); };
      var potek = v.potek || [], peak = 0, firstWet = null, endAt = null;
      potek.forEach(function (s) { var m = parseFloat(s.mmh) || 0; peak = Math.max(peak, m); if (m > 0 && firstWet == null) firstWet = s.t; });
      potek.forEach(function (s) { if (endAt == null && firstWet === 5 && (parseFloat(s.mmh) || 0) === 0) endAt = s.t; });
      var zeDez = v.zdaj >= 6, zeNev = v.zdaj >= 10, main, sub = '', state, ic, label;
      if (v.toca && !(v.zdaj >= 12)) { state = 'storm'; ic = 'w-storm'; label = 'Možnost toče'; main = 'Možnost toče čez ~' + v.jedro + ' min'; sub = 'Radar kaže močno jedro na poti proti Rečici.'; }
      else if (v.nevihta != null && !zeNev) { state = 'storm'; ic = 'w-storm'; label = 'Nevihta se približuje'; main = 'Možnost nevihte čez ~' + v.nevihta + ' min'; sub = 'Radar kaže nevihtno celico na poti proti Rečici.'; }
      else if (zeNev) { state = 'storm'; ic = 'w-storm'; label = 'Nevihta nad območjem'; main = 'Nevihta trenutno nad Rečico'; sub = 'Zaznana na radarskem prikazu, približno ' + n1(v.zdajMmh) + ' mm/h.'; }
      else if (zeDez) { state = 'over'; ic = 'w-rain'; label = 'Padavine nad območjem'; main = 'Padavine trenutno nad Rečico'; sub = 'Zaznane na radarskem prikazu, približno ' + n1(v.zdajMmh) + ' mm/h.'; }
      else if (v.dez != null || firstWet != null) {
        var at = v.dez != null ? v.dez : firstWet;
        state = 'near'; ic = 'i-clock'; label = 'Padavine se približujejo'; main = 'Možnost padavin čez ~' + at + ' min'; sub = 'Predvidena jakost: ' + (peak > 0 ? jakost(peak) + ' padavine' : 'rahle padavine') + '. To je ocena iz radarskega premika, ne gotovost.';
      } else { state = 'dry'; ic = 'i-ok'; label = 'Brez padavin na poti'; main = 'V naslednjih 45 minutah ni zaznanih padavin.'; sub = 'Radar trenutno ne kaže padavin na poti proti Rečici.'; }
      ncState(state, ic, label);
      $('nc-main').textContent = main; $('nc-sub').textContent = sub;
      var chart = $('nc-chart'), facts = $('nc-facts'); chart.textContent = ''; facts.textContent = '';
      var wet = state !== 'dry';
      if (wet && potek.length > 1) {
        chart.hidden = false; var mx = Math.max(peak, 1);
        potek.forEach(function (s) { var bar = el('i'); bar.style.height = Math.max(3, (parseFloat(s.mmh) || 0) / mx * 100) + '%'; bar.title = '+' + s.t + ' min: ' + num(parseFloat(s.mmh) || 0, 1) + ' mm/h'; chart.appendChild(bar); });
        chart.setAttribute('role', 'img'); chart.setAttribute('aria-label', 'Pričakovana jakost padavin v naslednjih 45 minutah, največ ' + n1(peak) + ' mm na uro');
        if (!$('nc-ax')) { var ax = el('div', 'dv-ncax'); ax.id = 'nc-ax'; ['Zdaj', '+15 min', '+30 min', '+45 min'].forEach(function (t) { ax.appendChild(el('span', null, t)); }); chart.insertAdjacentElement('afterend', ax); }
        $('nc-ax').hidden = false;
      } else { chart.hidden = true; if ($('nc-ax')) $('nc-ax').hidden = true; }
      var rows = [];
      if (state === 'near' || state === 'storm') rows.push(['Začetek', v.dez != null || firstWet != null ? 'čez ~' + (v.nevihta != null ? v.nevihta : v.dez != null ? v.dez : firstWet) + ' min' : 'že pada']);
      if (state === 'over') rows.push(['Po radarju', endAt ? 'ponehajo čez ~' + endAt + ' min' : 'ne ponehajo v 45 minutah']);
      if (wet && peak > 0) rows.push(['Jakost', 'do ~' + n1(peak) + ' mm/h (' + jakost(peak) + ')']);
      if (wet && d.premik && d.premik.kmh > 0) rows.push(['Smer gibanja', d.premik.kmh + ' km/h proti ' + dirName(d.premik.smer)]);
      var st = d.starost_min, atT = d.ts && st != null ? hhmm(Date.parse(d.ts) - st * 60000) : null;
      rows.push(['Radarska analiza', atT ? 'ob ' + atT + ' (star ' + st + ' min)' : 'čas ni znan']);
      rows.forEach(function (r) { var w = el('div'); w.appendChild(el('dt', null, r[0])); w.appendChild(el('dd', null, r[1])); facts.appendChild(w); });
      facts.hidden = false;
      $('nc-foot').textContent = (sim ? 'SIMULIRANO STANJE za preizkus oblike (?nowcast=' + sim + '). ' : '') + 'Radar ARSO' + (st != null && st > FRESH.radar ? ' (zakasnjeno)' : '') + '.';
    }).catch(function () {
      ncState('error', 'i-off', 'Podatek ni na voljo');
      $('nc-main').textContent = 'Podatek trenutno ni na voljo'; $('nc-sub').textContent = 'Radarskega pregleda ni bilo mogoče prebrati. To ne pomeni, da ne bo padavin.';
      $('nc-chart').hidden = true; $('nc-facts').hidden = true; if ($('nc-ax')) $('nc-ax').hidden = true; $('nc-foot').textContent = '';
      if (!$('nc-retry')) { var b = el('button', 'dv-retry', 'Poskusi znova'); b.id = 'nc-retry'; b.type = 'button'; b.addEventListener('click', function () { b.remove(); loadNowcast(); }); $('nc-sub').insertAdjacentElement('afterend', b); }
    });
  }

  // ── dolina: zgodba o mikroklimi (postaje po višini, razlika, profil) ──
  var drsi = null, varpolje = null, valleyLoaded = 0;
  var ELEV = { home: 366, gg: 428, crn: 903 };
  function loadValley() {
    Promise.all([jget(PROXY + '/crnivec-drsi').catch(function () { return null; }), jget(PROXY + '/varpolje-current').catch(function () { return null; })]).then(function (r) {
      drsi = r[0]; varpolje = r[1]; valleyLoaded = 1; renderValley();
    });
  }
  function stations() {      // vse znane postaje z izmerjeno vrednostjo, s starostjo
    var out = [], p = drsi && drsi.postaje;
    if (lastObs && lastObs.metric.temp != null && obsMs != null) out.push({ id: 'home', name: 'Rečica', long: 'Rečica ob Savinji', elev: ELEV.home, src: 'IREICA1', t: lastObs.metric.temp, ts: obsMs, max: FRESH.station.stale });
    if (varpolje && varpolje.current && varpolje.current.temp_c != null) out.push({ id: 'vp', name: 'Varpolje', long: 'Varpolje', elev: null, src: 'IREICA7 (sosed)', t: varpolje.current.temp_c, ts: varpolje.updated_utc ? Date.parse(varpolje.updated_utc) : null, max: FRESH.varpolje });
    if (p && p.gornji_grad && p.gornji_grad.temp_c != null) out.push({ id: 'gg', name: 'G. Grad', long: 'Gornji Grad', elev: ELEV.gg, src: 'DRSI', t: p.gornji_grad.temp_c, ts: p.gornji_grad.ts ? Date.parse(p.gornji_grad.ts) : null, max: FRESH.drsi });
    if (p && p.crnivec && p.crnivec.temp_c != null) out.push({ id: 'crn', name: 'Črnivec', long: 'Črnivec', elev: ELEV.crn, src: 'DRSI', t: p.crnivec.temp_c, ts: p.crnivec.ts ? Date.parse(p.crnivec.ts) : null, max: FRESH.drsi });
    out.forEach(function (s) { s.stale = s.ts == null || ageMin(s.ts) > s.max; });
    return out;
  }
  function verdict(pts, warmAll) {
    if (pts.length < 2) return { head: 'Profil ni na voljo', text: 'Višinske postaje trenutno niso dosegljive ali njihove meritve niso sveže; za profil ni dovolj podatkov.', lapse: null };
    var s = pts.slice().sort(function (a, b) { return a.elev - b.elev; }), lo = s[0], hi = s[s.length - 1];
    var lapse = (hi.t - lo.t) / (hi.elev - lo.elev) * 100, warm = warmAll || pts.reduce(function (a, b) { return b.t > a.t ? b : a; });
    var kind = lapse > 0 ? 'Inverzija' : lapse > -0.4 ? 'Šibek gradient' : lapse > -0.9 ? 'Običajen gradient' : 'Strm gradient';
    var why = lapse > 0 ? 'zgoraj je topleje kot na dnu doline, hladen zrak leži v dolini' : lapse > -0.4 ? 'temperatura z višino pada počasneje od običajnega' : lapse > -0.9 ? 'temperatura z višino pada običajno' : 'temperatura z višino pada hitreje od običajnega';
    return { head: kind, text: why.charAt(0).toUpperCase() + why.slice(1) + '. Najtopleje: ' + warm.long + ' (' + txt(warm.t, 1, '°C') + ').', lapse: lapse };
  }
  function chartSvg(pts) {
    var W = 320, H = 176, pl = 36, pr = 16, pt = 18, pb = 46, e0 = 300, e1 = 960;
    var ts = pts.map(function (p) { return p.t; }), t0 = Math.floor(Math.min.apply(null, ts) - 1.5), t1 = Math.ceil(Math.max.apply(null, ts) + 1.5);
    if (t1 - t0 < 5) { t1 = t0 + 5; }
    var x = function (e) { return pl + (e - e0) / (e1 - e0) * (W - pl - pr); }, y = function (t) { return pt + (t1 - t) / (t1 - t0) * (H - pt - pb); };
    var s = pts.slice().sort(function (a, b) { return a.elev - b.elev; }), g = '';
    for (var t = Math.ceil(t0); t <= t1; t++) if ((t - Math.ceil(t0)) % 2 === 0 || t1 - t0 < 7)
      g += '<line x1="' + pl + '" x2="' + (W - pr) + '" y1="' + y(t).toFixed(1) + '" y2="' + y(t).toFixed(1) + '" stroke="currentColor" opacity=".12"/><text x="' + (pl - 6) + '" y="' + (y(t) + 4).toFixed(1) + '" text-anchor="end" font-size="11" fill="currentColor" opacity=".7">' + t + '°</text>';
    [400, 600, 800].forEach(function (e) { g += '<text x="' + x(e).toFixed(1) + '" y="' + (H - 4) + '" text-anchor="middle" font-size="11" fill="currentColor" opacity=".7">' + e + ' m</text>'; });
    var ref = s[0], ref1 = ref.t - 0.0065 * (e1 - ref.elev);
    g += '<line x1="' + x(ref.elev).toFixed(1) + '" y1="' + y(ref.t).toFixed(1) + '" x2="' + x(e1).toFixed(1) + '" y2="' + y(ref1).toFixed(1) + '" stroke="currentColor" opacity=".45" stroke-dasharray="4 4"/>';
    g += '<polyline fill="none" stroke="var(--src-meas)" stroke-width="2.5" points="' + s.map(function (p) { return x(p.elev).toFixed(1) + ',' + y(p.t).toFixed(1); }).join(' ') + '"/>';
    s.forEach(function (p, i) {
      var cx = x(p.elev).toFixed(1), cy = y(p.t).toFixed(1);
      g += '<circle cx="' + cx + '" cy="' + cy + '" r="5.5" fill="var(--src-meas)" stroke="var(--c-surface)" stroke-width="2"/>' +
        '<text x="' + cx + '" y="' + (y(p.t) + (i % 2 ? 20 : -10)).toFixed(1) + '" text-anchor="middle" font-size="12" font-weight="700" fill="currentColor">' + txt(p.t, 1).replace(NBSP, '') + '°</text>' +
        '<text x="' + cx + '" y="' + (H - pb + 14 + (i % 2) * 12) + '" text-anchor="middle" font-size="11" fill="currentColor" opacity=".85">' + p.name + '</text>';
    });
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" aria-hidden="true">' + g + '</svg>';
  }
  function renderValley() {
    if (!valleyLoaded) return;
    var all = stations(), tiles = $('v-tiles'); tiles.textContent = '';
    if (!all.length) { fail(tiles, 'Meritev postaj trenutno ni mogoče prebrati.', function () { loadValley(); }); $('v-verdict').textContent = 'Podatek trenutno ni na voljo'; $('v-sub').textContent = ''; $('v-diff').textContent = ''; $('v-chart').textContent = ''; setLive('stale', 'Ni podatka'); return; }
    var freshPts = all.filter(function (s) { return !s.stale && s.elev != null; }), home = all.filter(function (s) { return s.id === 'home'; })[0];
    var warm = all.filter(function (s) { return !s.stale; }).reduce(function (a, b) { return !a || b.t > a.t ? b : a; }, null);
    // od najvišje postaje navzdol (Črnivec, Gornji Grad, Rečica), Varpolje brez višine na koncu
    all.slice().sort(function (a, b) { return (b.elev == null ? -1 : b.elev) - (a.elev == null ? -1 : a.elev); }).forEach(function (s) {
      var d = el('div', 'dv-vt' + (warm && warm.id === s.id ? ' warm' : '')), age = s.ts ? ageMin(s.ts) : null;
      d.appendChild(el('h3', null, s.long)); d.appendChild(el('span', 'el', (s.elev != null ? s.elev + ' m' : 'višina ni objavljena') + ' · ' + s.src));
      d.appendChild(el('b', null, txt(s.t, 1, '°C')));
      if (warm && warm.id === s.id) d.appendChild(el('small', 'wm', 'NAJTOPLEJE'));
      if (home && s.id !== 'home' && !s.stale && !home.stale) { var df = s.t - home.t; d.appendChild(el('small', null, (df > 0 ? '+' : df < 0 ? '−' : '') + num(Math.abs(df), 1) + ' °C glede na Rečico')); }
      d.appendChild(el('small', null, age == null ? 'čas ni znan' : 'ob ' + hhmm(s.ts) + (s.stale ? ' · podatek star ' + ageTxt(age) + ', ni vključen' : '')));
      tiles.appendChild(d);
    });
    var v = verdict(freshPts, warm), crn = all.filter(function (s) { return s.id === 'crn' && !s.stale; })[0];
    $('v-verdict').textContent = v.head + (v.lapse != null ? ' (' + (v.lapse > 0 ? '+' : '−') + num(Math.abs(v.lapse), 2) + NBSP + '°C/100' + NBSP + 'm)' : ''); $('v-sub').textContent = v.text;
    $('v-diff').textContent = home && !home.stale && crn ? 'Razlika med Rečico in Črnivcem: ' + num(Math.abs(home.t - crn.t), 1) + ' °C (' + (home.t > crn.t ? 'Rečica je toplejša' : home.t < crn.t ? 'Črnivec je toplejši' : 'enako') + ')' : '';
    var ch = $('v-chart'); ch.innerHTML = freshPts.length >= 2 ? chartSvg(freshPts) : '';
    ch.setAttribute('aria-label', freshPts.length >= 2 ? 'Temperatura po nadmorski višini: ' + freshPts.map(function (q) { return q.name + ' ' + q.elev + ' m, ' + txt(q.t, 1, '°C'); }).join('; ') : 'Profil ni na voljo');
    var anyStale = all.some(function (s) { return s.stale; });
    setLive(anyStale ? 'stale' : 'fresh', anyStale ? 'Del meritev je star' : 'V ŽIVO');
  }
  function setLive(state, label) { var l = $('v-live'); l.setAttribute('data-s', state); l.textContent = label; }

  // ── blog: en izpostavljen + dva najnovejša ──────────────
  function loadBlog() {
    jget('/blog.json').then(function (arr) {
      arr.sort(function (a, b) { return a.date < b.date ? 1 : -1; });
      var box = $('b-list'); box.textContent = '';
      arr.slice(0, 3).forEach(function (p, i) {
        var a = el('a', 'dv-card dv-post ' + (i === 0 ? 'feat' : 'sm')); a.href = p.url;
        // OG slike imajo vtisnjen naslov, zato se obrežejo samo ne: slika samo pri izpostavljenem članku, ostala dva sta besedilna
        if (i === 0) { var img = el('img'); img.src = '/og/' + p.slug + '.jpg'; img.alt = ''; img.loading = 'lazy'; img.width = 1200; img.height = 630; img.onerror = function () { img.remove(); }; a.appendChild(img); }
        else a.classList.remove('sm');
        var tx = el('div', 'tx'), meta = el('small'), cat = (p.tags || []).filter(function (t) { return !/^\d{4}$/.test(t); })[0];
        if (cat) meta.appendChild(el('span', 'cat', cat.replace(/-/g, ' ')));
        meta.appendChild(document.createTextNode(new Date(p.date + 'T12:00:00').toLocaleDateString('sl-SI', { day: 'numeric', month: 'long', year: 'numeric' })));
        tx.appendChild(meta); tx.appendChild(el('h3', null, p.title)); tx.appendChild(el('p', null, p.summary || '')); a.appendChild(tx);
        box.appendChild(a);
      });
    }).catch(function () { fail($('b-list'), 'Objav trenutno ni mogoče naložiti.', loadBlog); });
  }
})();
