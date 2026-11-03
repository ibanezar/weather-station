/* Radar padavin za prototip domače strani. Logika je prenos iz app.js (razdelek »Lasten radar padavin«; isti endpointi
   /radar-composite.json, /radar-composite, /icon-precip, /radar-cells.json) in se ob vgradnji v produkcijo NE podvaja:
   tam ostane app.js, tu se testira samo postavitev po specifikaciji (7.6). Razlike od produkcije:
   - Leaflet se naloži šele, ko radar pride blizu zaslona (13.1), z SRI;
   - kontrolniki so NAD zemljevidom, legenda pod njim (7.6);
   - RADAR (opazovano) in MODEL (ICON napoved) sta vizualno in tekstovno ločena (10.2);
   - brez samodejnega predvajanja ob prefers-reduced-motion (12.2); na telefonu en prst premika stran, ne karte. */
(function () {
  'use strict';
  var PROXY = 'https://weatherireica1.filip-eremita.workers.dev', LAT = 46.325779, LON = 14.921137, TZ = 'Europe/Ljubljana';
  var OPACITY = 0.82, RETRIES = 3, STALE_MIN = 20;
  var LEAF = 'https://unpkg.com/leaflet@1.9.4/dist/';
  var SRI_CSS = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=', SRI_JS = 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
  var $ = function (id) { return document.getElementById(id); };
  var map = null, frames = [], idx = -1, timer = null, poll = null, bounds = null, last = '', view = 'savinja', applied = '';
  var playing = !(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  var cellMk = new Map(), cellTr = new Map(), ptCache = new Map(), ptTok = 0;

  function num(v, d) { return (v == null || isNaN(v)) ? '–' : Number(v).toLocaleString('sl-SI', { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function hhmm(iso) { return new Date(iso).toLocaleTimeString('sl-SI', { hour: '2-digit', minute: '2-digit', timeZone: TZ }); }
  function jget(u) { return fetch(u).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }); }
  function windDir(d) { return ['S', 'SSV', 'SV', 'VSV', 'V', 'VJV', 'JV', 'JJV', 'J', 'JJZ', 'JZ', 'ZJZ', 'Z', 'ZSZ', 'SZ', 'SSZ'][Math.round(d / 22.5) % 16]; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function loadLeaflet() {
    if (window.L) return Promise.resolve();
    return new Promise(function (ok, fail) {
      var c = document.createElement('link'); c.rel = 'stylesheet'; c.href = LEAF + 'leaflet.css'; c.integrity = SRI_CSS; c.crossOrigin = ''; document.head.appendChild(c);
      var s = document.createElement('script'); s.src = LEAF + 'leaflet.js'; s.integrity = SRI_JS; s.crossOrigin = '';
      s.onload = ok; s.onerror = function () { fail(new Error('Leaflet se ni naložil')); }; document.head.appendChild(s);
    });
  }

  // ── inicializacija šele ob prihodu v vidno območje ──────
  // Samo IntersectionObserver ni dovolj: ko vsebina nad radarjem po pomiku na sidro še zraste, radar uide iz območja
  // in se ne bi naložil. Zato še preverjanje ob pomiku/spremembi velikosti in takojšen zagon ob kliku na povezavo #radar.
  var started = false;
  function start() { if (started) return; started = true; init(); }
  document.addEventListener('DOMContentLoaded', function () {
    var box = $('rd-map'); if (!box) return;
    $('rd-play').addEventListener('click', togglePlay);
    document.querySelectorAll('[data-rd-view]').forEach(function (b) { b.addEventListener('click', function () { switchView(b.getAttribute('data-rd-view')); }); });
    var trk = $('rd-track'); trk.addEventListener('pointerdown', scrubStart); trk.addEventListener('keydown', onKey);
    setPlayLabel();
    function near() { if (!started && box.getBoundingClientRect().top < window.innerHeight + 600) start(); }
    ['scroll', 'resize'].forEach(function (ev) { window.addEventListener(ev, near, { passive: true }); });
    document.querySelectorAll('a[href="#radar"]').forEach(function (a) { a.addEventListener('click', start); });
    if (location.hash === '#radar') start();
    if ('IntersectionObserver' in window) { var io = new IntersectionObserver(function (e) { if (e[0].isIntersecting) { io.disconnect(); start(); } }, { rootMargin: '600px' }); io.observe(box); }
    else start();
  });

  function init() {
    loadLeaflet().then(function () {
      var mobile = L.Browser.mobile;
      $('rd-map').setAttribute('data-drag', String(!mobile));   // na telefonu en prst premika stran, ne karte
      map = L.map('rd-map', { zoomControl: true, attributionControl: false, minZoom: 6, maxZoom: 10, dragging: !mobile, scrollWheelZoom: false }).setView([LAT, LON], 7);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 10, maxNativeZoom: 19, subdomains: 'abc', className: 'rd-tiles' }).addTo(map);
      L.circleMarker([LAT, LON], { radius: 6, color: '#fff', fillColor: '#2563eb', fillOpacity: 1, weight: 2 }).addTo(map)
        .bindTooltip('Rečica ob Savinji', { permanent: true, direction: 'right', offset: [8, 0], className: 'rd-label' });
      map.on('click', function (e) {
        var t = e.originalEvent && e.originalEvent.target;
        if (t && t.closest && t.closest('.leaflet-interactive,.leaflet-popup,.leaflet-control')) return;
        pointForecast(e.latlng);
      });
      refresh().then(refreshCells);
      poll = setInterval(function () { if (!document.hidden) { refresh(); refreshCells(); } }, 5 * 60000);
    }).catch(function () { setTime('Radar trenutno ni na voljo', ''); noteMode(null); retryBtn(init); });
  }

  // ── okvirji ─────────────────────────────────────────────
  function refresh() {
    return jget(PROXY + '/radar-composite.json?pogled=' + view).then(function (m) {
      var list = (m.okvirji || []).filter(function (f) { return f && f.zig; }).map(function (f) { return { zig: f.zig, cas: f.cas, kind: 'radar' }; });
      if (!list.length) throw new Error('ni okvirjev');
      var ic = (view === 'savinja' && m.napoved && m.napoved.okvirji || []).filter(function (f) { return f && f.zig; }).map(function (f) { return { zig: f.zig, cas: f.cas, kind: 'icon' }; });
      var full = list.concat(ic); bounds = m.meje; legend(m.legenda);
      if (applied !== view) { map.setMaxZoom(view === 'sirok' ? 10 : 11); map.setView([LAT, LON], view === 'sirok' ? 7 : 10); applied = view; }
      if (list[list.length - 1].zig === last && !frames.some(retry)) return;
      last = list[list.length - 1].zig;
      var live = new Set(full.map(function (f) { return f.zig; }));
      frames.filter(function (f) { return !live.has(f.zig) && f.layer; }).forEach(function (f) { map.removeLayer(f.layer); });
      var old = new Map(frames.map(function (f) { return [f.zig, f]; }));
      frames = full.map(function (f) { return old.get(f.zig) || { zig: f.zig, cas: f.cas, kind: f.kind, layer: null, ready: false }; });
      var si = frames.findIndex(function (f) { return f.kind === 'icon'; }), sp = $('rd-split');
      if (si > 0) { sp.style.left = (si / frames.length * 100) + '%'; sp.hidden = false; } else sp.hidden = true;
      ticks(); range(list, ic);
      var chain = loadFrame(frames.length - 1).then(function () { show(frames.length - 1); });
      frames.slice(0, -1).forEach(function (_, i) { chain = chain.then(function () { return loadFrame(i); }).then(function () { if (playing && !timer && ready().length > 2) anim(); }); });
      return chain.then(function () {
        var c2 = Promise.resolve(); frames.forEach(function (f, i) { if (retry(f)) c2 = c2.then(function () { return loadFrame(i); }); });
        return c2;
      }).then(function () { if (playing) anim(); });
    }).catch(function () { if (idx < 0) { setTime('Radar ni dosegljiv', ''); noteMode(null); retryBtn(function () { refresh().then(refreshCells); }); } });
  }
  function range(list, ic) {
    var a = list[0].cas, b = list[list.length - 1].cas, age = Math.round((Date.now() - new Date(b).getTime()) / 60000);
    $('rd-range').textContent = 'Prikazano: radar ' + hhmm(a) + '–' + hhmm(b) + (ic.length ? ', nato napoved ICON do ' + hhmm(ic[ic.length - 1].cas) : '') + '.';
    $('u-r').textContent = 'Zadnja radarska slika ob ' + hhmm(b) + ' (star ' + age + ' min)';
  }
  function retryBtn(fn) {      // nadomestno stanje z ponovnim poskusom (specifikacija 10.3)
    if ($('rd-retry')) return;
    var b = document.createElement('button'); b.id = 'rd-retry'; b.type = 'button'; b.className = 'dv-retry'; b.textContent = 'Poskusi znova';
    b.addEventListener('click', function () { b.remove(); fn(); }); $('rd-mode').insertAdjacentElement('afterend', b);
  }
  function retry(f) { return !!f && !f.ready && !f.layer && (f.napak || 0) < RETRIES; }
  function ready() { return frames.filter(function (f) { return f.ready; }); }
  function loadFrame(i) {
    var f = frames[i]; if (!f || f.layer || f.ready || (f.napak || 0) >= RETRIES) return Promise.resolve();
    return new Promise(function (res) {
      var src = f.kind === 'icon' ? PROXY + '/icon-precip?t=' + encodeURIComponent(f.zig) : PROXY + '/radar-composite?pogled=' + view + '&t=' + encodeURIComponent(f.zig);
      var layer = L.imageOverlay(src, bounds, { opacity: 0, interactive: false });
      layer.once('load', function () { f.ready = true; res(); });
      layer.once('error', function () { f.napak = (f.napak || 0) + 1; try { map.removeLayer(layer); } catch (e) {} f.layer = null; res(); });
      layer.addTo(map); f.layer = layer;
    });
  }
  function show(i) {
    var f = frames[i]; if (!f || !f.ready) return;
    frames.forEach(function (x) { if (x.layer) x.layer.setOpacity(x === f ? OPACITY : 0); });
    idx = i;
    var isLast = i === frames.length - 1 && f.kind !== 'icon', age = isLast ? Math.round((Date.now() - new Date(f.cas).getTime()) / 60000) : 0;
    var badge = f.kind === 'icon' ? 'Napoved' : isLast ? (age > STALE_MIN ? 'Pred ' + age + ' min' : 'Zdaj') : '';
    setTime(hhmm(f.cas), badge, isLast && age > STALE_MIN ? 'old' : f.kind === 'icon' ? 'fc' : 'now');
    noteMode(f.kind);
    var pos = ((i + 0.5) / frames.length * 100).toFixed(1) + '%', trk = $('rd-track');
    $('rd-fill').style.width = pos; $('rd-thumb').style.left = pos;
    trk.setAttribute('aria-valuenow', i); trk.setAttribute('aria-valuetext', hhmm(f.cas) + (f.kind === 'icon' ? ' (modelska napoved)' : ' (radar)'));
  }
  function setTime(t, badge, cls) {
    $('rd-time').textContent = t; var b = $('rd-badge'); b.textContent = badge || ''; b.hidden = !badge; b.className = 'dv-tag rd-b-' + (cls || '');
  }
  // Ločitev RADAR / MODEL: besedilo, oznaka in okvir zemljevida (ne samo barva).
  function noteMode(kind) {
    var w = $('rd-wrap'), m = $('rd-mode');
    if (kind === 'icon') { w.setAttribute('data-kind', 'model'); m.textContent = 'MODEL · napoved ICON za naslednjih 6 ur (ni meritev)'; }
    else if (kind === 'radar') { w.setAttribute('data-kind', 'radar'); m.textContent = 'RADAR · izmerjeno, zadnja ura'; }
    else { w.removeAttribute('data-kind'); m.textContent = 'Radarske slike trenutno ni mogoče prebrati. To ne pomeni, da ne dežuje.'; }
  }
  function ticks() {
    var n = frames.length, box = $('rd-ticks'), trk = $('rd-track'); trk.setAttribute('aria-valuemax', Math.max(0, n - 1)); box.textContent = '';
    if (!n) return;
    Array.from(new Set([0, Math.round((n - 1) / 2), n - 1])).forEach(function (k) {
      var s = document.createElement('span'); s.textContent = hhmm(frames[k].cas);
      s.style.left = ((k + 0.5) / n * 100).toFixed(1) + '%'; s.style.transform = 'translateX(' + (k === 0 ? '0%' : k === n - 1 ? '-100%' : '-50%') + ')'; box.appendChild(s);
    });
  }

  // ── animacija in kontrolniki ────────────────────────────
  function anim() {
    clearInterval(timer); var hold = 0;
    timer = setInterval(function () {
      if (hold > 0) { hold--; return; }
      if (ready().length < 2) return;
      var i = idx; for (var k = 0; k < frames.length; k++) { i = (i + 1) % frames.length; if (frames[i].ready) break; }
      show(i);
      var prev = frames[(i - 1 + frames.length) % frames.length];
      if (i === frames.length - 1 || (frames[i].kind === 'icon' && prev.kind !== 'icon')) hold = 3;
    }, 450);
  }
  function setPlayLabel() { var b = $('rd-play'); b.textContent = playing ? 'Pavza' : 'Predvajaj'; b.setAttribute('aria-pressed', String(playing)); }
  function togglePlay() { playing = !playing; if (playing) anim(); else { clearInterval(timer); timer = null; } setPlayLabel(); }
  function pause() { playing = false; clearInterval(timer); timer = null; setPlayLabel(); }
  function seekX(x) {
    var r = $('rd-track').getBoundingClientRect(); if (!frames.length) return;
    var i = Math.max(0, Math.min(frames.length - 1, Math.floor((x - r.left) / r.width * frames.length)));
    if (!frames[i].ready) { var best = -1, bd = 1e9; frames.forEach(function (f, k) { if (f.ready && Math.abs(k - i) < bd) { bd = Math.abs(k - i); best = k; } }); if (best < 0) return; i = best; }
    show(i); pause();
  }
  function scrubStart(e) {
    if (e.button > 0) return; var t = e.currentTarget; try { t.setPointerCapture(e.pointerId); } catch (x) {}
    var mv = function (ev) { seekX(ev.clientX); }, up = function () { t.removeEventListener('pointermove', mv); t.removeEventListener('pointerup', up); t.removeEventListener('pointercancel', up); };
    t.addEventListener('pointermove', mv); t.addEventListener('pointerup', up); t.addEventListener('pointercancel', up); seekX(e.clientX);
  }
  function onKey(e) {
    var k = e.key; if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].indexOf(k) < 0) return; e.preventDefault();
    var n = frames.length; if (!n) return; var dir = (k === 'ArrowLeft' || k === 'ArrowDown') ? -1 : 1;
    var i = k === 'Home' ? 0 : k === 'End' ? n - 1 : idx + dir; i = Math.max(0, Math.min(n - 1, i));
    var st = k === 'Home' ? 1 : k === 'End' ? -1 : dir; while (i >= 0 && i < n && !frames[i].ready) i += st;
    if (i < 0 || i >= n) return; show(i); pause();
  }
  function switchView(id) {
    if (id === view || !map) return; view = id;
    document.querySelectorAll('[data-rd-view]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-rd-view') === id)); });
    clearInterval(timer); timer = null; frames.forEach(function (f) { if (f.layer) map.removeLayer(f.layer); }); frames = []; idx = -1; last = '';
    setTime('–', ''); refresh();
  }
  function legend(leg) {
    var bar = $('rd-scale'), tk = $('rd-lticks'); if (!leg || !leg.length || bar.childElementCount) return;
    leg.forEach(function (l) { var i = document.createElement('i'); i.style.background = l.barva; bar.appendChild(i); });
    bar.style.gridTemplateColumns = 'repeat(' + leg.length + ',1fr)';
    var lab = leg.filter(function (_, i) { return i % 2 === 0; });
    lab.forEach(function (l) { var s = document.createElement('span'); s.textContent = String(l.mmh).replace('.', ','); tk.appendChild(s); });
    tk.style.gridTemplateColumns = 'repeat(' + lab.length + ',1fr)';
  }

  // ── nevihtne celice ─────────────────────────────────────
  function cellLabel(mk, label, perm) {
    if (mk.getTooltip()) mk.unbindTooltip();
    mk.bindTooltip(label, { permanent: perm, direction: 'top', offset: [0, -4], className: 'rd-label rd-cell' + (perm ? ' rd-eta' : '') }); mk._perm = perm;
  }
  function refreshCells() {
    if (!map) return Promise.resolve();
    return jget(PROXY + '/radar-cells.json').then(function (d) {
      var cells = d.celice || [], live = new Set(cells.map(function (c) { return c.id; }));
      cellMk.forEach(function (mk, id) { if (!live.has(id)) { map.removeLayer(mk); cellMk.delete(id); } });
      cellTr.forEach(function (ln, id) { if (!live.has(id)) { map.removeLayer(ln); cellTr.delete(id); } });
      var urgent = d.prihaja ? d.prihaja.id : null;
      cells.forEach(function (c) {
        var label = (c.kmh != null && c.smer != null) ? Math.round(c.kmh) + ' km/h → ' + windDir(c.smer) : (c.toca ? 'nevihta (toča?)' : 'nevihta');
        var col = c.toca ? '#c0143c' : '#ff6a00', perm = c.id === urgent, mk = cellMk.get(c.id);
        if (!mk) { mk = L.circleMarker([c.lat, c.lon], { radius: 5, color: '#fff', weight: 2, fillColor: col, fillOpacity: 0.95 }).addTo(map); cellLabel(mk, label, perm); cellMk.set(c.id, mk); }
        else { mk.setLatLng([c.lat, c.lon]); mk.setStyle({ fillColor: col }); if (mk._perm === perm) mk.setTooltipContent(label); else cellLabel(mk, label, perm); }
        if (c.sled && c.sled.length >= 2) {
          var ln = cellTr.get(c.id);
          if (!ln) { ln = L.polyline(c.sled, { color: col, weight: 2, opacity: 0.55, dashArray: '1,6', lineCap: 'round' }).addTo(map); cellTr.set(c.id, ln); } else { ln.setLatLngs(c.sled); ln.setStyle({ color: col }); }
        }
      });
      var p = d.prihaja, b = $('rd-eta');
      if (!p) { b.hidden = true; return; }
      b.textContent = 'Nevihtna celica prihaja proti Rečici ob Savinji čez ~' + p.eta_min + ' min (zdaj ~' + p.zdaj_km + ' km stran, ' + Math.round(p.kmh) + ' km/h, ' + windDir(p.smer) + ').'; b.hidden = false;
    }).catch(function () {});
  }

  // ── klik na točko: modelska napoved, NI radar ───────────
  function pointSvg(P, now) {
    var W = 260, H = 84, base = 66, n = P.length, step = W / n, mx = Math.max.apply(null, [2].concat(P));
    var bars = P.map(function (v, i) { var h = Math.max(v > 0 ? 1.5 : 0, v / mx * (base - 6));
      return '<rect x="' + (i * step + 1).toFixed(1) + '" y="' + (base - h).toFixed(1) + '" width="' + (step - 2).toFixed(1) + '" height="' + h.toFixed(1) + '" rx="1.5" fill="currentColor" opacity="' + (i < now ? '.35' : '.9') + '"/>'; }).join('');
    var nx = (now * step).toFixed(1);
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" role="img" aria-label="Padavine po urah, 6 ur nazaj in 18 ur naprej, največ ' + num(Math.max.apply(null, P), 1) + ' mm na uro">' +
      '<line x1="0" y1="' + base + '" x2="' + W + '" y2="' + base + '" stroke="currentColor" opacity=".25"/>' + bars +
      '<line x1="' + nx + '" y1="2" x2="' + nx + '" y2="' + base + '" stroke="currentColor" stroke-dasharray="3 3" opacity=".6"/>' +
      '<text x="2" y="80" font-size="9" fill="currentColor">−6 h</text><text x="' + nx + '" y="80" font-size="9" text-anchor="middle" fill="currentColor">zdaj</text><text x="258" y="80" font-size="9" text-anchor="end" fill="currentColor">+18 h</text></svg>';
  }
  function pointForecast(ll) {
    var lat = Math.round(ll.lat * 100) / 100, lon = Math.round(ll.lng * 100) / 100, key = lat + ',' + lon, tok = ++ptTok;
    var pw = Math.max(170, Math.min(250, map.getSize().x - 110)), head = '<b>' + num(lat, 2) + '° S, ' + num(lon, 2) + '° V</b>';
    var pop = L.popup({ className: 'rd-pop', maxWidth: pw, minWidth: pw, keepInView: true }).setLatLng([lat, lon]).setContent('<div class="rd-pt">' + head + '<p>Berem napoved za točko …</p></div>').openOn(map);
    var d = ptCache.get(key), p = (d && Date.now() - d.ts < 600000) ? Promise.resolve(d) :
      jget('https://api.open-meteo.com/v1/forecast?latitude=' + lat + '&longitude=' + lon + '&hourly=temperature_2m,precipitation&past_hours=6&forecast_hours=19&timezone=Europe%2FLjubljana').then(function (j) {
        var P = ((j.hourly || {}).precipitation || []).map(function (v) { return v == null ? 0 : v; }), T = (j.hourly || {}).temperature_2m || [];
        if (P.length < 20) throw new Error('premalo'); var o = { ts: Date.now(), P: P, T: T }; ptCache.set(key, o); return o; });
    p.then(function (o) {
      if (tok !== ptTok) return; var sum = function (a) { return a.reduce(function (x, y) { return x + y; }, 0); };
      pop.setContent('<div class="rd-pt">' + head + '<div class="rd-row"><span>Zdaj (model)</span><b>' + (o.T[6] != null ? num(o.T[6], 1) + ' °C' : '–') + '</b></div>' +
        '<div class="rd-row"><span>Padavine čez 6 h</span><b>' + num(sum(o.P.slice(7, 13)), 1) + ' mm</b></div><div class="rd-row"><span>Padavine čez 18 h</span><b>' + num(sum(o.P.slice(7)), 1) + ' mm</b></div>' +
        pointSvg(o.P, 6) + '<small>Modelska napoved Open-Meteo za to točko: ni radar in ni meritev.</small></div>');
    }).catch(function () { if (tok === ptTok) pop.setContent('<div class="rd-pt">' + head + '<p>Napovedi za to točko ni bilo mogoče prebrati.</p></div>'); });
  }
})();
