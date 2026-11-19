/* /snegofili/ — drsnik skozi čas, karta, prerez, kartice, delci, pas »Kjer zdaj sneži«, kamerni zid z lightboxom,
   podrobnost točke (grafi 96 ur), toplotna karta, »Kam peljem?«, priljubljene točke.
   Model (step/phase/radius/windows/snowing/hstep/plan) je brez DOM-a in izvožen za Node: usklajenost s Pythonom
   (tools/generate_snegofili_page.py) preverja tools/test_snegofili.py. Če spremeniš eno, spremeni drugo. */
(function (root) {
  'use strict';
  var NOW = 71, MIN_I = 23, MAX_I = 119; // −48 h … +48 h okoli »zdaj«, polna 24-urna okna na obeh straneh
  var SNOWING_MIN = 1;                   // desetinke cm na uro: ≥ 0,1 cm/h šteje kot »sneži«

  function step(cm) { return cm < 1 ? -1 : cm < 5 ? 0 : cm < 15 ? 1 : cm < 30 ? 2 : cm < 60 ? 3 : 4; }
  function phase(elev, slM) { if (slM == null) return 'rain'; var d = elev - slM; return d >= 100 ? 'snow' : d > -100 ? 'mix' : 'rain'; }
  function radius(cm) { return cm < 1 ? 6 : Math.min(34, 8 + 4.2 * Math.sqrt(cm)); }
  function barPct(cm) { return Math.min(100, Math.sqrt(Math.max(cm, 0)) / Math.sqrt(40) * 100); }
  function sum(a, from, to) { var s = 0; for (var i = Math.max(0, from); i <= Math.min(a.length - 1, to); i++) s += a[i] || 0; return Math.round(s) / 10; }
  function windows(sn, i) { return { past: sum(sn, i - 23, i), next: sum(sn, i + 1, i + 24) }; }
  function fmt(x, d) { return (Math.round(x * Math.pow(10, d)) / Math.pow(10, d)).toFixed(d).replace('.', ','); }
  function cmText(cm) { return cm < 1 ? '<1 cm' : fmt(cm, cm >= 10 ? 0 : 1) + ' cm'; }
  var PHASE_TXT = { snow: 'Sneg', mix: 'Moker sneg', rain: 'Dež ali suho' };

  /* Ali ob uri i sneži (vsaj 0,1 cm/h po modelu). */
  function snowing(h, i) { return !!h && (h.sn[i] || 0) >= SNOWING_MIN; }
  /* Stopnja toplotne karte po urni količini (desetinke cm/h): −1 ni snega, 0…4 pragovi 0,1 / 0,5 / 1 / 2 / 4 cm/h. */
  function hstep(v) { var c = (v || 0) / 10; return c < 0.1 ? -1 : c < 0.5 ? 0 : c < 1 ? 1 : c < 2 ? 2 : c < 4 ? 3 : 4; }
  /* »Kam peljem?«: tri točke z največ snega v oknu (n24 = naslednjih 24 h, n48 = 24–48 h od zdaj, p24 = zadnjih 24 h). */
  var PLAN_WIN = { n24: [NOW + 1, NOW + 24], n48: [NOW + 25, NOW + 48], p24: [NOW - 23, NOW] };
  function plan(pts, hours, o) {
    var w = PLAN_WIN[o.win] || PLAN_WIN.n24, out = [];
    pts.forEach(function (p) {
      var h = hours[p.id]; if (!h) return;
      if (o.km && p.k > o.km) return;
      if (o.minE && p.e < o.minE) return;
      var cm = sum(h.sn, w[0], w[1]);
      if (cm <= 0 || cm < (o.minCm || 0)) return;
      out.push({ p: p, cm: cm });
    });
    out.sort(function (a, b) { return b.cm - a.cm || a.p.k - b.p.k; });
    return out.slice(0, o.top || 3);
  }

  var model = {
    NOW: NOW, MIN_I: MIN_I, MAX_I: MAX_I, SNOWING_MIN: SNOWING_MIN, step: step, phase: phase, radius: radius, barPct: barPct,
    windows: windows, cmText: cmText, PHASE_TXT: PHASE_TXT, snowing: snowing, hstep: hstep, plan: plan
  };
  if (typeof module !== 'undefined' && module.exports) { module.exports = model; }
  root.SgModel = model;
  if (typeof document === 'undefined') return;

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  var pts, hours, nowLocal, cur = NOW, timer = null, mapMode = 'past';
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var API = 'https://weatherireica1.filip-eremita.workers.dev';

  document.documentElement.classList.add('sg-js');
  try { pts = JSON.parse($('#sg-pts').textContent); } catch (e) { return; }
  var byId = {}; pts.forEach(function (p) { byId[p.id] = p; });
  var cards = $$('.sg-card'), sortKey = 'past', country = '*', onlyFresh = false, onlyFav = false;

  /* ── priljubljene točke (samo v brskalniku) ── */
  var FAVK = 'wx-sg-fav', favs = [];
  try { var f0 = JSON.parse(localStorage.getItem(FAVK) || '[]'); if (Array.isArray(f0)) favs = f0.filter(function (id) { return byId[id]; }); } catch (e) { }
  function isFav(id) { return favs.indexOf(id) >= 0; }
  function toggleFav(id) {
    var i = favs.indexOf(id); if (i >= 0) favs.splice(i, 1); else favs.push(id);
    try { localStorage.setItem(FAVK, JSON.stringify(favs)); } catch (e) { }
    paintFavs(); layout(); if (hours) render(cur);
  }
  function paintFavs() {
    $$('.sg-star').forEach(function (b) {
      var on = isFav(b.dataset.id); b.setAttribute('aria-pressed', on); b.textContent = on ? '★' : '☆';
      b.setAttribute('aria-label', (on ? 'Odstrani iz mojih točk: ' : 'Dodaj med moje točke: ') + byId[b.dataset.id].n);
    });
    var fb = $('#sg-filter [data-f="fav"]'); if (fb) fb.textContent = '★ Moje točke' + (favs.length ? ' (' + favs.length + ')' : '');
  }

  /* ── filtri in razvrščanje (delujejo tudi brez urnih podatkov) ── */
  var bar = $('#sg-filter');
  if (bar) {
    bar.hidden = false;
    bar.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      if (b.dataset.f === 'fresh') { onlyFresh = !onlyFresh; b.setAttribute('aria-pressed', onlyFresh); }
      else if (b.dataset.f === 'fav') { onlyFav = !onlyFav; b.setAttribute('aria-pressed', onlyFav); }
      else if (b.dataset.c) { country = b.dataset.c; $$('[data-c]', bar).forEach(function (x) { x.setAttribute('aria-pressed', x === b); }); }
      else if (b.dataset.s) { sortKey = b.dataset.s; $$('[data-s]', bar).forEach(function (x) { x.setAttribute('aria-pressed', x === b); }); }
      layout();
    });
  }
  var query = '';
  function norm(t) { return String(t).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
  var qi = $('#sg-q'); if (qi) qi.addEventListener('input', function () { query = norm(qi.value.trim()); layout(); });
  function layout() {
    var grid = $('#sg-cards'); if (!grid) return;
    var vis = cards.filter(function (c) {
      var id = c.id.slice(2);
      var ok = (country === '*' || c.dataset.c === country) && (!query || norm(c.dataset.n || '').indexOf(query) >= 0) && (!onlyFresh || parseFloat(c.dataset.fresh) >= 1) && (!onlyFav || isFav(id));
      c.hidden = !ok; return ok;
    });
    vis.sort(function (a, b) {
      if (sortKey === 'elev') return b.dataset.elev - a.dataset.elev;
      if (sortKey === 'km') return a.dataset.km - b.dataset.km;
      return parseFloat(b.dataset[sortKey]) - parseFloat(a.dataset[sortKey]);
    }).forEach(function (c) { grid.appendChild(c); });
    var emp = $('#sg-fav-empty');
    if (onlyFav && !favs.length) { if (!emp) { emp = el('p', 'muted-note', 'Še nimate mojih točk: na kartici ali v podrobnosti točke pritisnite zvezdico.'); emp.id = 'sg-fav-empty'; grid.parentNode.insertBefore(emp, grid); } }
    else if (emp) emp.remove();
  }

  /* ── čas ── */
  function localDate(i) {
    if (!nowLocal) return null;
    var m = /^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)/.exec(nowLocal); if (!m) return null;
    return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) + (i - NOW) * 36e5);
  }
  function timeLabel(i) {
    var d = localDate(i); if (!d) return '';
    return new Intl.DateTimeFormat('sl', { weekday: 'short', day: 'numeric', month: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'UTC' }).format(d).replace(/(\d)[:](\d\d)/, '$1.$2');
  }
  function slText(sl, e) { return sl == null ? 'ni podatka' : (Math.round(sl / 10) * 10) + ' m · točka ' + Math.abs(Math.round((e - sl) / 10) * 10) + ' m ' + (e - sl >= 0 ? 'nad' : 'pod') + ' njo'; }
  function offText(i) { var o = i - NOW; return o === 0 ? 'trenutna ura' : o < 0 ? 'pred ' + (-o) + ' h' : 'čez ' + o + ' h'; }
  function slAt(h, i) { return h.sl[i] == null ? null : h.sl[i] * 10; }

  /* ── prikaz ob izbrani uri ── */
  var intensity = 0;
  function render(i) {
    cur = i;
    var best = null, bestN = null, active = 0, tot = 0, fresh = 0, list = [];
    pts.forEach(function (p) {
      var h = hours[p.id]; if (!h) return;
      var w = windows(h.sn, i), sl = slAt(h, i), ph = phase(p.e, sl), st = step(w.past);
      var snowingNow = snowing(h, i); if (snowingNow) { active++; list.push({ p: p, rate: h.sn[i] / 10, ph: ph }); } tot++;
      if (w.past >= 1) fresh++;
      if (!best || w.past > best.w.past) best = { p: p, w: w };
      if (!bestN || w.next > bestN.w.next) bestN = { p: p, w: w };
      /* karta */
      var c = $('#sg-map [data-id="' + p.id + '"]');
      if (c) {
        var val = mapMode === 'next' ? w.next : w.past, sv = step(val);
        var show = sv >= 0 && ph !== 'rain';
        c.setAttribute('r', radius(show ? val : 0).toFixed(1));
        c.setAttribute('class', 'sg-c ' + (show ? 's' + sv + ' ' : 'ring ') + 'ph-' + ph + (isFav(p.id) ? ' fav' : ''));
        c.setAttribute('aria-label', p.n + ', ' + p.e + ' m: ' + PHASE_TXT[ph] + ', zadnjih 24 ur ' + cmText(w.past) + ', naslednjih 24 ur ' + cmText(w.next));
      }
      /* prerez */
      var tk = $('#sg-prof .sg-sl[data-id="' + p.id + '"]');
      if (tk && sl != null) tk.setAttribute('y', (+tk.dataset.y0 - Math.max(0, Math.min(sl, 4000)) * +tk.dataset.k - 1.25).toFixed(1));
      var r = $('#sg-prof .sg-snow[data-id="' + p.id + '"]');
      if (r && sl != null) {
        var top = Math.min(p.e, 4000), y0 = +r.dataset.y0, k = +r.dataset.k, sy = Math.max(0, Math.min(sl, top));
        r.setAttribute('y', (y0 - top * k).toFixed(1));
        r.setAttribute('height', Math.max(0, (top - sy) * k).toFixed(1));
        r.style.opacity = p.e > sl ? 1 : 0;
      }
      /* kartica */
      var k2 = $('#t-' + p.id);
      if (k2) {
        k2.dataset.past = w.past; k2.dataset.next = w.next; k2.dataset.fresh = Math.max(w.past, w.next);
        var l = $('.sg-bl', k2), rr = $('.sg-br', k2);
        l.style.width = barPct(w.past) / 2 + '%'; rr.style.width = barPct(w.next) / 2 + '%';
        $('.sg-np', k2).textContent = cmText(w.past); $('.sg-nn', k2).textContent = cmText(w.next);
        var pill = $('.sg-pill', k2); pill.textContent = PHASE_TXT[ph]; pill.className = 'sg-pill ph-' + ph;
        var t = h.t[i]; $('.sg-tt', k2).textContent = t == null ? '—' : fmt(t / 10, 1) + ' °C';
        $('.sg-sl', k2).textContent = slText(sl, p.e);
        k2.setAttribute('aria-label', p.n + ': ' + PHASE_TXT[ph] + ', zadnjih 24 ur ' + cmText(w.past) + ', naslednjih 24 ur ' + cmText(w.next));
        var cu = $('.sg-spark .sg-sc', k2); if (cu) { var xx = (i - MIN_I + 0.5).toFixed(2); cu.setAttribute('x1', xx); cu.setAttribute('x2', xx); }
      }
    });
    var lab = $('#sg-time'); if (lab) lab.textContent = offText(i) + (timeLabel(i) ? ' · ' + timeLabel(i) : '');
    var sl2 = $('#sg-range'); if (sl2) { sl2.value = i; sl2.setAttribute('aria-valuetext', offText(i) + ', ' + timeLabel(i)); }
    var ro = $('#sg-readout');
    if (ro && best) ro.textContent = best.w.past < 1 ? 'V 24 urah do te ure po modelu nikjer ni zapadlo več kot centimeter snega.'
      : 'Najbolj zasnežilo je na točki ' + best.p.n + ' (' + cmText(best.w.past) + ' v 24 urah do te ure). Na ' + active + ' od ' + tot + ' točk po modelu sneži.';
    intensity = tot ? active / tot : 0;
    stats(active, tot, best, bestN, fresh);
    nowStrip(list, i);
    camBadges(i);
    heatCursor(i);
    panelPaint();
    layout();
  }

  function stats(active, tot, best, bestN, fresh) {
    var set = function (id, v) { var e = document.getElementById(id); if (e && e.textContent !== v) e.textContent = v; };
    var nl = document.getElementById('sg-nowline');
    if (nl) {
      nl.className = 'sg-nowline' + (active ? ' on' : '');
      var t = active ? 'Po modelu sneži na ' + active + ' od ' + tot + ' točk (≥ 0,1 cm na uro).' : 'Trenutno ne sneži: po modelu na nobeni točki ni vsaj 0,1 cm na uro.';
      if (nl.textContent !== t) nl.textContent = t;
    }
    var near = function (key) {
      var b = null; pts.forEach(function (p) { var h = hours[p.id]; if (!h || p.k > 200) return; var v = windows(h.sn, cur)[key]; if (!b || v > b.v) b = { p: p, v: v }; });
      return b ? (b.v >= 1 ? 'Do 200 km od Rečice: ' + cmText(b.v) + ' · ' + b.p.n : 'Do 200 km od Rečice: nikjer ≥ 1 cm') : null;
    };
    if (best) { set('sg-st-past', cmText(best.w.past)); set('sg-st-past-n', best.w.past >= 1 ? best.p.n : 'nikjer'); var a = near('past'); if (a) set('sg-st-past-c', a); }
    if (bestN) { set('sg-st-next', cmText(bestN.w.next)); set('sg-st-next-n', bestN.w.next >= 1 ? bestN.p.n : 'nikjer'); var b2 = near('next'); if (b2) set('sg-st-next-c', b2); }
    set('sg-st-fresh', String(fresh)); set('sg-st-fresh-n', 'od ' + tot + ' lokacij · ≥ 1 cm v zadnjih 24 urah');
  }

  function bindControls() {
    var sl = $('#sg-range'), play = $('#sg-play'), nowb = $('#sg-now');
    if (!sl) return;
    sl.min = MIN_I; sl.max = MAX_I; sl.step = 1; sl.value = NOW;
    $('#sg-ctl').hidden = false;
    sl.addEventListener('input', function () { stop(); render(+sl.value); });
    nowb.addEventListener('click', function () { stop(); render(NOW); });
    function stop() { if (timer) { clearInterval(timer); timer = null; play.setAttribute('aria-pressed', 'false'); play.textContent = 'Predvajaj'; } }
    play.addEventListener('click', function () {
      if (timer) { stop(); return; }
      play.setAttribute('aria-pressed', 'true'); play.textContent = 'Ustavi';
      if (cur >= MAX_I) cur = MIN_I;
      timer = setInterval(function () { cur += 2; if (cur > MAX_I) { cur = MIN_I; } render(cur); }, 420);
    });
    $$('.sg-seg button').forEach(function (b) {
      b.addEventListener('click', function () {
        mapMode = b.dataset.m; $$('.sg-seg button').forEach(function (x) { x.setAttribute('aria-pressed', x === b); }); render(cur);
      });
    });
  }

  /* ── opis ob točki na karti ── */
  var tip = $('#sg-tip'), map = $('#sg-map');
  function showTip(c) {
    if (!tip || !map) return;
    var p = byId[c.dataset.id]; if (!p) return;
    tip.textContent = c.getAttribute('aria-label') || p.n;
    var q = map.getAttribute('viewBox').split(' ').map(Number);
    tip.style.left = ((p.x - q[0]) / q[2] * 100) + '%'; tip.style.top = ((p.y - q[1]) / q[3] * 100) + '%'; tip.hidden = false;
  }
  if (map) {
    $$('.sg-c', map).forEach(function (c) {
      c.addEventListener('pointerenter', function () { showTip(c); });
      c.addEventListener('focus', function () { showTip(c); });
      c.addEventListener('pointerleave', function () { tip && (tip.hidden = true); });
      c.addEventListener('blur', function () { tip && (tip.hidden = true); });
      c.addEventListener('click', go.bind(null, c));
      c.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(c); } });
    });
  }
  /* ── plošča izbrane točke: kompaktni povzetek ob karti (na telefonu spodnji list), podrobnosti šele po kliku ── */
  var panel = $('#sg-panel'), selId = null;
  function panelPaint() {
    if (!panel || !selId) return;
    var p = byId[selId], h = hours && hours[selId]; if (!p) return;
    panel.textContent = '';
    var hd = el('div', 'sg-pn-h'), tt = el('div'); tt.appendChild(el('h3', null, p.n));
    tt.appendChild(el('p', 'sg-sub', (p.c === 'SI' ? 'Slovenija' : p.c) + ' · ' + p.e + ' m n. m. · ' + p.k + ' km od Rečice'));
    hd.appendChild(tt);
    var x = el('button', 'sg-pn-x', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Zapri povzetek točke');
    x.addEventListener('click', function () { closePanel(true); }); hd.appendChild(x); panel.appendChild(hd);
    if (h) {
      var w = windows(h.sn, cur), sl = slAt(h, cur), t = h.t[cur];
      var kv = el('div', 'sg-pn-kv');
      [['Zadnjih 24 ur', cmText(w.past)], ['Naslednjih 24 ur', cmText(w.next)]].forEach(function (a) { var d = el('div'); d.appendChild(el('small', null, a[0])); d.appendChild(el('b', null, a[1])); kv.appendChild(d); });
      panel.appendChild(kv);
      panel.appendChild(el('p', 'sg-pn-l', PHASE_TXT[phase(p.e, sl)] + ' · ' + (t == null ? 'temperatura: ni podatka' : fmt(t / 10, 1) + ' °C') + ' · meja sneženja: ' + (sl == null ? 'ni podatka' : Math.round(sl / 10) * 10 + ' m')));
    }
    var src = el('p', 'sg-pn-l'); var b1 = el('span', 'sg-bdg m', 'Model'); src.appendChild(b1); src.appendChild(document.createTextNode(' Open-Meteo, ura: ' + offText(cur)));
    panel.appendChild(src);
    if (p.m) { var m = el('p', 'sg-pn-l'); m.appendChild(el('span', 'sg-bdg r', 'Meritev')); m.appendChild(document.createTextNode(' ARSO: snežna odeja ' + p.m.d + ' cm' + (p.m.d === 0 ? ' (izmerjena ničla)' : '') + ', pred ' + Math.round(p.m.a) + ' h')); panel.appendChild(m); }
    var act = el('div', 'sg-pn-a');
    if (h) { var db = el('button', 'sg-btn', 'Odpri podrobnosti lokacije'); db.type = 'button'; db.addEventListener('click', function () { openDetail(selId, db); }); act.appendChild(db); }
    if (hasCam(p)) { var cb = el('button', 'sg-btn s', camLabel(p)); cb.type = 'button'; cb.addEventListener('click', function () { openCam(selId, cb); }); act.appendChild(cb); }
    panel.appendChild(act);
  }
  function closePanel(focusBack) {
    if (!panel) return;
    var id = selId; selId = null; panel.hidden = true; document.documentElement.classList.remove('sg-sheet-open');
    $$('.sg-c.sel', map).forEach(function (c) { c.classList.remove('sel'); });
    if (focusBack && id) { var c = $('#sg-map [data-id="' + id + '"]'); if (c && c.focus) c.focus(); }
  }
  function go(c) {
    var id = c.dataset.id;
    if (panel && hours && hours[id]) {
      selId = id; $$('.sg-c.sel', map).forEach(function (q) { q.classList.remove('sel'); }); c.classList.add('sel');
      panelPaint(); panel.hidden = false; document.documentElement.classList.add('sg-sheet-open'); if (tip) tip.hidden = true;
      return;
    }
    showTip(c);
    var k = document.getElementById('t-' + id); if (!k) return;
    k.hidden = false; k.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
    k.classList.remove('sg-flash'); void k.offsetWidth; k.classList.add('sg-flash');
  }
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && selId && !modal.isOpen()) closePanel(true); });

  /* ── delci: gostota sledi deležu točk, kjer ob izbrani uri sneži ── */
  function particles() {
    var cv = $('#sg-snow'); if (!cv || reduce) return;
    var ctx = cv.getContext('2d'), W = 0, H = 0, fl = [], vis = true, last = 0;
    var MAXF = innerWidth < 640 ? 90 : 190;
    function size() { var r = cv.parentNode.getBoundingClientRect(); W = cv.width = Math.round(r.width); H = cv.height = Math.round(r.height); }
    function mk(top) { return { x: Math.random() * W, y: top ? -5 : Math.random() * H, r: .8 + Math.random() * 2, v: 14 + Math.random() * 26, s: Math.random() * 6.28, a: .25 + Math.random() * .5 }; }
    size(); addEventListener('resize', size);
    for (var i = 0; i < MAXF; i++) fl.push(mk(false));
    if ('IntersectionObserver' in window) new IntersectionObserver(function (e) { vis = e[0].isIntersecting; }).observe(cv);
    var col = '255,255,255';
    function tick(ts) {
      requestAnimationFrame(tick);
      if (!vis || document.hidden || ts - last < 50) return; var dt = Math.min(.1, (ts - last) / 1000); last = ts;
      ctx.clearRect(0, 0, W, H);
      var n = Math.round(24 + (MAXF - 24) * Math.min(1, .15 + intensity * 1.4));
      for (var i = 0; i < n; i++) {
        var f = fl[i]; f.y += f.v * dt * (1 + intensity); f.s += dt; f.x += Math.sin(f.s) * 10 * dt;
        if (f.y > H + 5) { f.y = -5; f.x = Math.random() * W; }
        ctx.fillStyle = 'rgba(' + col + ',' + f.a + ')'; ctx.beginPath(); ctx.arc(f.x, f.y, f.r, 0, 6.2832); ctx.fill();
      }
    }
    setTimeout(function () { requestAnimationFrame(tick); }, 1500); // okrasje šele po nalaganju
  }

  var zb = $('#sg-zoom');
  if (zb && map) {
    zb.hidden = false;
    var b = $('button', zb);
    b.addEventListener('click', function () {
      var zoomed = b.getAttribute('aria-pressed') === 'true';   /* kliknemo: preklop v nasprotni pogled */
      var on = !zoomed;
      b.setAttribute('aria-pressed', on);
      b.textContent = on ? 'Pokaži ves alpski lok' : 'Približaj: Slovenija in sosedje';
      var v = on ? b.dataset.zoom : b.dataset.full, q = v.split(' ');
      map.setAttribute('viewBox', v); map.style.aspectRatio = q[2] + ' / ' + q[3];
      map.classList.toggle('zoom', on);
      if (tip) tip.hidden = true;
    });
  }

  /* ══ modalno okno (podrobnost točke, kamera): fokus ostane v oknu, Esc zapre, fokus se vrne ══ */
  var modal = (function () {
    var root = el('div', 'sg-modal'); root.hidden = true;
    var back = el('div', 'sg-mb');
    var panel = el('div', 'sg-mp'); panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true'); panel.tabIndex = -1;
    var x = el('button', 'sg-mx', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Zapri');
    var body = el('div', 'sg-mc');
    panel.appendChild(x); panel.appendChild(body); root.appendChild(back); root.appendChild(panel); document.body.appendChild(root);
    var opener = null, onClose = null, isOpen = false;
    function focusables() { return $$('button,a[href],input,select,[tabindex]:not([tabindex="-1"])', panel).filter(function (e) { return !e.disabled && e.offsetParent !== null; }); }
    function close() {
      if (!isOpen) return; isOpen = false; root.hidden = true; document.documentElement.classList.remove('sg-lock');
      var cb = onClose; onClose = null; body.textContent = '';
      if (cb) cb();
      if (opener && opener.focus && document.contains(opener)) opener.focus(); opener = null;
    }
    function open(node, label, trigger, closeCb) {
      if (!isOpen) opener = trigger || document.activeElement;
      else if (onClose) { var old = onClose; onClose = null; old(); }
      onClose = closeCb || null;
      body.textContent = ''; body.appendChild(node); panel.setAttribute('aria-label', label || 'Podrobnosti');
      root.hidden = false; isOpen = true; document.documentElement.classList.add('sg-lock'); panel.scrollTop = 0; panel.focus();
    }
    x.addEventListener('click', close); back.addEventListener('click', close);
    document.addEventListener('keydown', function (e) {
      if (!isOpen) return;
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      else if (e.key === 'Tab') {
        var f = focusables(); if (!f.length) { e.preventDefault(); return; }
        var a = f[0], z = f[f.length - 1];
        if (e.shiftKey && (document.activeElement === a || document.activeElement === panel)) { e.preventDefault(); z.focus(); }
        else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
      }
    });
    return { open: open, close: close, isOpen: function () { return isOpen; } };
  })();

  /* ══ kamere ══ */
  var camsEl = $('#sg-cams'), PROXY = (camsEl && camsEl.dataset.proxy) || API, DRSI = camsEl && camsEl.dataset.drsi;
  var camState = {}, camIds = [], camTiles = {}, camSeen = {}, CAM_TTL = 3e5;
  var EMBED_OK = { windy: ['webcams.windy.com', 'embed.windy.com'], youtube: ['www.youtube-nocookie.com'] };
  function camLabel(p) { return (p.ca || p.cd) ? 'Oglej si aktualno sliko' : 'Odpri kamero Windy'; }
  function hasCam(p) { return !!(p && (p.ca || p.cd || p.ce)); }
  function camKind(p) { return p.ca ? 'arso' : p.cd ? 'drsi' : p.ce ? 'embed' : null; }
  function embedUrl(ce) { if (!ce) return null; try { var u = new URL(ce.s); return u.protocol === 'https:' && (EMBED_OK[ce.k] || []).indexOf(u.hostname) >= 0 ? u.href : null; } catch (e) { return null; } }
  function loadCam(id, force) {
    var p = byId[id], st = camState[id] || (camState[id] = {});
    if (!p) return Promise.resolve(st);
    if (st.busy) return st.busy;
    if (!force && (st.src || st.embed) && Date.now() - st.ts < CAM_TTL) return Promise.resolve(st);
    var fin = function (ok) { st.ts = Date.now(); st.err = !ok; st.busy = null; paintCam(id); return st; };
    if (p.ce && !p.ca && !p.cd) { st.embed = true; st.cap = ''; return Promise.resolve(fin(true)); }
    if (p.cd && !p.ca) {
      st.src = DRSI + '?t=' + Math.floor(Date.now() / CAM_TTL); st.cap = 'Vir: DRSI · prelaz Črnivec'; st.time = '';
      return Promise.resolve(fin(true));
    }
    st.busy = fetch(PROXY + '/arso-cam?format=json&kamera=' + encodeURIComponent(p.ca)).then(function (r) { return r.ok ? r.json() : null; }).then(function (m) {
      if (!m) return fin(false);
      var d = m.posnet ? new Date(m.posnet) : null;
      st.time = d && !isNaN(d) ? d.toLocaleTimeString('sl', { hour: '2-digit', minute: '2-digit' }) : '';
      st.src = PROXY + m.slika + (m.posnet ? '&t=' + encodeURIComponent(m.posnet) : '');
      st.cap = 'Vir: ARSO · ' + m.kamera + (st.time ? ' · posneto ob ' + st.time : '');
      return fin(true);
    }).catch(function () { return fin(false); });
    return st.busy;
  }
  function camImg(st, p, cls) {
    var i = el('img', cls); i.loading = 'lazy'; i.decoding = 'async'; i.width = 1023; i.height = 520; i.alt = 'Spletna kamera: ' + p.n; i.src = st.src;
    i.addEventListener('error', function () { st.err = true; paintCam(p.id); }, { once: true });
    return i;
  }
  function paintCam(id) {
    var p = byId[id], st = camState[id], tile = camTiles[id];
    if (tile && st) {
      var box = $('.sg-cam-img', tile), t = $('.sg-cam-t', tile);
      if (st.err) { box.textContent = ''; box.appendChild(el('span', 'sg-cam-msg', 'Slika trenutno ni dosegljiva')); }
      else if (st.src) { var im = $('img', box); if (im) im.src = st.src; else { box.textContent = ''; box.appendChild(camImg(st, p, '')); } }
      else if (st.embed) { box.textContent = ''; box.appendChild(el('span', 'sg-cam-msg', 'Časovni zdrs dneva (Windy), po kliku')); }
      if (t) t.textContent = st.time ? '· ' + st.time : '';
    }
    if (hours) nowStripThumbs();
    if (lb.id === id && modal.isOpen()) lbPaint();
  }
  function camBadges(i) {
    camIds.forEach(function (id) {
      var tile = camTiles[id], h = hours && hours[id]; if (!tile || !h) return;
      var s = $('.sg-cam-st', tile), p = byId[id], on = snowing(h, i), ph = phase(p.e, slAt(h, i));
      s.textContent = on ? 'Po modelu sneži · ' + fmt(h.sn[i] / 10, h.sn[i] >= 10 ? 0 : 1) + ' cm/h' : ph === 'rain' ? 'Po modelu: dež ali suho' : 'Po modelu ne sneži';
      s.className = 'sg-cam-st' + (on ? ' on' : '');
    });
  }
  function camList() { return camIds.filter(function (id) { return camTiles[id]; }); }
  /* lightbox kamere */
  var lb = { id: null, ci: null, pick: 0 };
  function lbPaint() {
    var wrap = $('.sg-lb'); if (!wrap) return;
    var p = byId[lb.id], st = camState[lb.id] || {}, h = hours && hours[lb.id], ces = p.ce || [];
    var stage = $('.sg-lb-stage', wrap); stage.textContent = '';
    var credit = $('.sg-lb-credit', wrap); credit.textContent = '';
    var ext = $('.sg-lb-ext', wrap); ext.textContent = '';
    var shown = lb.ci != null ? ces[lb.ci] : null, u = shown ? embedUrl(shown) : null;
    if (u) {
      var f = document.createElement('iframe'); f.src = u; f.loading = 'lazy'; f.title = 'Spletna kamera: ' + p.n + (shown.t ? ' (' + shown.t + ')' : '');
      f.setAttribute('referrerpolicy', 'no-referrer'); f.setAttribute('allowfullscreen', ''); f.className = 'sg-lb-frame'; stage.appendChild(f);
      if (shown.k === 'windy') {
        credit.appendChild(document.createTextNode('Webcams provided by '));
        var a1 = el('a', null, 'windy.com'); a1.href = 'https://www.windy.com/'; a1.target = '_blank'; a1.rel = 'noopener'; credit.appendChild(a1);
        if (shown.u) { credit.appendChild(document.createTextNode(' · ')); var a2 = el('a', null, 'stran kamere'); a2.href = shown.u; a2.target = '_blank'; a2.rel = 'noopener'; credit.appendChild(a2); }
      }
    } else if (st.err && !ces.length) stage.appendChild(el('p', 'sg-cam-msg', 'Slika trenutno ni dosegljiva. Poskusite znova čez nekaj minut.'));
    else if (st.src && !st.err) stage.appendChild(camImg(st, p, 'sg-lb-img'));
    else if (ces.length && !p.ca && !p.cd) {
      var b0 = el('button', 'sg-live', 'Naloži časovni zdrs dneva (Windy)'); b0.type = 'button';
      b0.addEventListener('click', function () { lb.ci = lb.pick || 0; lbPaint(); });
      stage.appendChild(b0);
      stage.appendChild(el('p', 'sg-attr', 'Po kliku se naloži vsebina ponudnika (Windy), ki lahko nastavi svoje piškotke.'));
    } else stage.appendChild(el('p', 'sg-cam-msg', st.err ? 'Slika trenutno ni dosegljiva.' : 'Nalagam sličico …'));
    /* ostale kamere točke (Windy) in vrnitev na sličico */
    if (ces.length) {
      ces.forEach(function (c, i) {
        if (!embedUrl(c)) return;
        var b = el('button', 'sg-btn s', (c.t || ('Kamera ' + (i + 1))) + ' (časovni zdrs)'); b.type = 'button';
        b.setAttribute('aria-pressed', lb.ci === i);
        b.addEventListener('click', function () { lb.ci = i; lb.pick = i; lbPaint(); });
        ext.appendChild(b);
      });
      if (lb.ci != null && (p.ca || p.cd)) { var bk = el('button', 'sg-btn s', '← Sličica kamere'); bk.type = 'button'; bk.addEventListener('click', function () { lb.ci = null; lbPaint(); }); ext.appendChild(bk); }
    }
    $('.sg-lb-cap', wrap).textContent = u ? ('Vir: Windy · ' + (shown.t || '') + ' · časovni zdrs zadnjega dne, ne tok v živo') : (st.cap || '');
    var mod = $('.sg-lb-model', wrap);
    if (h) {
      var on = snowing(h, cur), ph = phase(p.e, slAt(h, cur));
      mod.textContent = 'Model ob izbrani uri (' + offText(cur) + '): ' + (on ? 'sneži, ' + fmt(h.sn[cur] / 10, 1) + ' cm/h' : ph === 'rain' ? 'dež ali suho' : 'brez novega snega') +
        ' · ' + (h.t[cur] == null ? '—' : fmt(h.t[cur] / 10, 1) + ' °C') + '. Kamera kaže stanje zdaj, ne izbrane ure.';
    } else mod.textContent = '';
  }
  function openCam(id, trigger) {
    var p = byId[id]; if (!p || !hasCam(p)) return;
    var wrap = el('div', 'sg-lb');
    var hd = el('div', 'sg-lb-hd'); var h2 = el('h2', null, p.n); h2.id = 'sg-lb-t';
    hd.appendChild(h2); hd.appendChild(el('p', 'sg-sub', p.e + ' m · ' + (p.c === 'SI' ? 'Slovenija' : p.c) + ' · ' + p.k + ' km od Rečice'));
    wrap.appendChild(hd); wrap.appendChild(el('div', 'sg-lb-stage')); wrap.appendChild(el('p', 'sg-attr sg-lb-credit')); wrap.appendChild(el('div', 'sg-lb-ext')); wrap.appendChild(el('p', 'sg-lb-cap')); wrap.appendChild(el('p', 'sg-lb-model'));
    var nav = el('div', 'sg-lb-nav');
    var prev = el('button', 'sg-btn', '← Prejšnja'), next = el('button', 'sg-btn', 'Naslednja →'), more = el('button', 'sg-btn', 'Podrobnosti točke'), ref = el('button', 'sg-btn s', 'Osveži');
    [prev, next, more, ref].forEach(function (b) { b.type = 'button'; nav.appendChild(b); });
    wrap.appendChild(nav);
    wrap.appendChild(el('p', 'sg-attr', 'Slike kamer so last navedenih virov. Modelska ocena in kamera se lahko razhajata.'));
    var step1 = function (d) { var l = camList(), k = l.indexOf(lb.id); openCam(l[(k + d + l.length) % l.length]); };
    prev.addEventListener('click', function () { step1(-1); }); next.addEventListener('click', function () { step1(1); });
    more.addEventListener('click', function () { if (hours && hours[id]) openDetail(id); });
    ref.addEventListener('click', function () { loadCam(lb.id, true); });
    modal.open(wrap, 'Kamera: ' + p.n, trigger, function () { lb.id = null; });
    lb.id = id; lb.ci = null; lb.pick = 0; // po modal.open: ta pokliče zapiralnik prejšnjega okna (pri menjavi kamere bi sicer pobrisal novo vrednost)
    lbPaint(); loadCam(id, true);
  }
  function bindCams() {
    $$('.sg-cam').forEach(function (f) {
      var id = f.dataset.id; camIds.push(id); camTiles[id] = f;
      $('.sg-cam-b', f).addEventListener('click', function () { openCam(id, this); });
    });
    if (!camIds.length) return;
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (e) { var id = e.target.dataset.id; camSeen[id] = e.isIntersecting; if (e.isIntersecting) loadCam(id); });
      }, { rootMargin: '300px' });
      camIds.forEach(function (id) { io.observe(camTiles[id]); });
    } else camIds.forEach(function (id) { loadCam(id); });
    /* sličice se osvežujejo največ na 5 minut in samo, ko so vidne */
    setInterval(function () {
      if (document.hidden) return;
      camIds.forEach(function (id) { if (camSeen[id] || lb.id === id) loadCam(id, true); });
    }, CAM_TTL);
    /* na kartici povezava »kamera« odpre lightbox namesto skoka na dno strani */
    $$('.sg-card .sg-foot a[href="#kamere"]').forEach(function (a) {
      var id = a.closest('.sg-card').id.slice(2);
      a.addEventListener('click', function (e) { if (hasCam(byId[id])) { e.preventDefault(); openCam(id, a); } });
    });
  }

  /* ══ pas »Kjer zdaj sneži« ══ */
  var nowKey = '';
  function nowStrip(list, i) {
    var sec = $('#zdaj-snezi'); if (!sec) return;
    sec.hidden = false;
    list.sort(function (a, b) { return b.rate - a.rate; });
    var key = i + '|' + list.map(function (x) { return x.p.id; }).join(',') + '|' + favs.join(',');
    var sub = $('#zs-sub');
    sub.textContent = list.length ? 'Po modelu ' + (i === NOW ? 'v trenutni uri' : 'ob izbrani uri (' + offText(i) + ', ' + timeLabel(i) + ')') + ' sneži na ' + list.length + ' točkah. Kamera pri točki kaže, kar je tam v resnici.' :
      'Ob tej uri po modelu nikjer v seznamu ne sneži (manj kot 0,1 cm na uro). Premaknite drsnik ali poglejte napoved v toplotni karti spodaj.';
    $('#zs-h').textContent = i === NOW ? 'Kjer zdaj sneži' : 'Kjer sneži ob izbrani uri';
    if (key === nowKey) return; nowKey = key;
    var row = $('#sg-now-row'); row.textContent = '';
    list.slice(0, 12).forEach(function (x) {
      var p = x.p, h = hours[p.id], c = el('article', 'sg-nowc'); c.setAttribute('role', 'listitem');
      var th = el('div', 'sg-nowc-th'); th.dataset.id = p.id; c.appendChild(th);
      var hd = el('div', 'sg-nowc-hd'); hd.appendChild(el('h3', null, p.n));
      hd.appendChild(el('span', 'sg-pill ph-' + x.ph, PHASE_TXT[x.ph])); c.appendChild(hd);
      var r = el('p', 'sg-nowc-r'); r.appendChild(el('b', null, fmt(x.rate, x.rate >= 10 ? 0 : 1))); r.appendChild(document.createTextNode(' cm/h')); c.appendChild(r);
      var t = h.t[i]; c.appendChild(el('p', 'sg-sub', p.e + ' m · ' + (t == null ? '—' : fmt(t / 10, 1) + ' °C') + ' · ' + p.k + ' km' + (p.m ? ' · izmerjeno ' + p.m.d + ' cm' : '')));
      var act = el('div', 'sg-nowc-act');
      if (hasCam(p)) { var cb = el('button', 'sg-btn', camLabel(p)); cb.type = 'button'; cb.addEventListener('click', function () { openCam(p.id, cb); }); act.appendChild(cb); }
      else if (p.cl && p.cl[0]) { var a = el('a', 'sg-btn s', 'Kamera pri ponudniku'); a.href = p.cl[0].u; a.target = '_blank'; a.rel = 'noopener'; act.appendChild(a); }
      var db = el('button', 'sg-btn s', 'Podrobnosti'); db.type = 'button'; db.addEventListener('click', function () { openDetail(p.id, db); }); act.appendChild(db);
      c.appendChild(act); row.appendChild(c);
    });
    nowStripThumbs();
    list.slice(0, 12).forEach(function (x) { if (hasCam(x.p) && !(camState[x.p.id] && (camState[x.p.id].src || camState[x.p.id].err))) loadCam(x.p.id); });
    /* podij: najbolj zasnežene točke nazaj in naprej 24 h (do izbrane ure) */
    var top = $('#sg-top'); top.textContent = '';
    [['past', 'Največ v zadnjih 24 urah'], ['next', 'Največ v naslednjih 24 urah']].forEach(function (cfg) {
      var rows = pts.map(function (p) { var h = hours[p.id]; return h ? { p: p, v: windows(h.sn, i)[cfg[0]] } : null; }).filter(function (x) { return x && x.v >= 1; })
        .sort(function (a, b) { return b.v - a.v; }).slice(0, 5);
      var box = el('div', 'sg-podium'); box.appendChild(el('h3', 'sg-h3', cfg[1]));
      var ol = el('ol'); if (!rows.length) { var li0 = el('li', 'sg-sub', 'Nikjer več kot 1 cm.'); ol.appendChild(li0); }
      rows.forEach(function (x) {
        var li = el('li'), b = el('button', 'sg-linkbtn', x.p.n); b.type = 'button'; b.addEventListener('click', function () { openDetail(x.p.id, b); });
        li.appendChild(b); li.appendChild(el('span', null, cmText(x.v))); ol.appendChild(li);
      });
      box.appendChild(ol); top.appendChild(box);
    });
  }
  function nowStripThumbs() {
    $$('.sg-nowc-th').forEach(function (th) {
      var st = camState[th.dataset.id]; if (!st || !st.src || st.err || th.firstChild) return;
      var i = el('img'); i.alt = ''; i.loading = 'lazy'; i.decoding = 'async'; i.width = 280; i.height = 142; i.src = st.src;
      i.addEventListener('error', function () { i.remove(); th.classList.remove('on'); }, { once: true });
      th.appendChild(i); th.classList.add('on');
    });
  }

  /* ══ sparkline na kartici ══ */
  function sparks() {
    cards.forEach(function (k) {
      var id = k.id.slice(2), h = hours[id], box = $('.sg-spark', k); if (!h || !box) return;
      var n = MAX_I - MIN_I + 1, hmax = 10, i;
      for (i = MIN_I; i <= MAX_I; i++) hmax = Math.max(hmax, h.sn[i] || 0);
      var past = '', fut = '';
      for (i = MIN_I; i <= MAX_I; i++) {
        var v = h.sn[i] || 0; if (v < SNOWING_MIN) continue;
        var seg = 'M' + (i - MIN_I + 0.5) + ' 34V' + (34 - Math.max(2, v / hmax * 32)).toFixed(1);
        if (i <= NOW) past += seg; else fut += seg;
      }
      var nx = (NOW - MIN_I + 0.5);
      box.innerHTML = '<svg viewBox="0 0 ' + n + ' 34" preserveAspectRatio="none" focusable="false"><line class="sg-sb" x1="0" x2="' + n + '" y1="33.5" y2="33.5"/>' +
        '<path class="sg-sp" d="' + past + '"/><path class="sg-sf" d="' + fut + '"/>' +
        '<line class="sg-sn" x1="' + nx + '" x2="' + nx + '" y1="0" y2="34"/><line class="sg-sc" x1="' + nx + '" x2="' + nx + '" y1="0" y2="34"/></svg>';
      box.setAttribute('title', '96 ur: levo prej, desno napoved');
      /* gumba »podrobnosti« in zvezdica */
      if (!$('.sg-star', k)) {
        var st = el('button', 'sg-star', '☆'); st.type = 'button'; st.dataset.id = id; st.addEventListener('click', function () { toggleFav(id); });
        $('.sg-head', k).appendChild(st);
        var mb = el('button', 'sg-more', 'Podrobnosti in grafi'); mb.type = 'button'; mb.addEventListener('click', function () { openDetail(id, mb); });
        k.appendChild(mb);
      }
    });
    paintFavs();
  }

  /* ══ podrobnost točke: grafi 96 ur ══ */
  var CW = 720, PL = 40, PR = 10, PWID = CW - PL - PR, PH = 92, GAP = 44, TOP = 20;
  function xOf(i) { return PL + (i - MIN_I) / (MAX_I - MIN_I) * PWID; }
  function niceMax(v, steps) { for (var k = 0; k < steps.length; k++) if (v <= steps[k]) return steps[k]; return Math.ceil(v / 10) * 10; }
  function line(vals, y, dash) {
    var d = '', pen = false;
    for (var i = MIN_I; i <= MAX_I; i++) { var v = vals[i]; if (v == null) { pen = false; continue; } d += (pen ? 'L' : 'M') + xOf(i).toFixed(1) + ' ' + y(v).toFixed(1); pen = true; }
    return d;
  }
  function xAxis(y0) {
    var out = '', i, d, lastDay = -1;
    for (i = MIN_I; i <= MAX_I; i++) {
      d = localDate(i); if (!d) continue;
      if (d.getUTCHours() === 0 || i === MIN_I) {
        var x = xOf(i), name = new Intl.DateTimeFormat('sl', { weekday: 'short', day: 'numeric', month: 'numeric', timeZone: 'UTC' }).format(d);
        if (d.getUTCHours() === 0) out += '<line class="gx" x1="' + x.toFixed(1) + '" x2="' + x.toFixed(1) + '" y1="' + TOP + '" y2="' + y0 + '"/>';
        if (d.getUTCDate() !== lastDay && x < CW - 60) { out += '<text class="ax" x="' + (x + 3).toFixed(1) + '" y="' + (y0 + 14) + '">' + name + '</text>'; lastDay = d.getUTCDate(); }
      }
    }
    return out;
  }
  function chartSvg(p, h, cmpP) {
    var h2 = cmpP && hours[cmpP.id], i, e;
    var H = TOP + PH * 3 + GAP * 2 + 6, svg = '<svg viewBox="0 0 ' + CW + ' ' + H + '" class="sg-ch" role="img" aria-label="Grafi za točko ' + p.n.replace(/[<>&"]/g, '') + ': novi sneg po urah, temperatura in meja sneženja od 48 ur nazaj do 48 ur naprej">';
    var yA = TOP, yB = TOP + PH + GAP, yC = TOP + (PH + GAP) * 2;
    /* A: sneg po urah */
    var mx = 0; for (i = MIN_I; i <= MAX_I; i++) { mx = Math.max(mx, (h.sn[i] || 0) / 10, h2 ? (h2.sn[i] || 0) / 10 : 0); }
    var top = niceMax(mx, [0.5, 1, 2, 5, 10, 20]), ay = function (v) { return yA + PH - v / top * PH; };
    svg += '<text class="tt" x="' + PL + '" y="' + (yA - 3) + '">Novi sneg po urah (cm/h)</text>';
    [0, top / 2, top].forEach(function (g) { svg += '<line class="gr" x1="' + PL + '" x2="' + (CW - PR) + '" y1="' + ay(g).toFixed(1) + '" y2="' + ay(g).toFixed(1) + '"/><text class="ax" x="' + (PL - 5) + '" y="' + (ay(g) + 4).toFixed(1) + '" text-anchor="end">' + fmt(g, top < 2 ? 1 : 0) + '</text>'; });
    var bw = Math.max(1.5, PWID / (MAX_I - MIN_I + 1) * 0.78);
    for (i = MIN_I; i <= MAX_I; i++) {
      var v = (h.sn[i] || 0) / 10; if (v <= 0) continue;
      svg += '<rect class="' + (i <= NOW ? 'bp' : 'bf') + '" x="' + (xOf(i) - bw / 2).toFixed(1) + '" y="' + ay(v).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + Math.max(1, yA + PH - ay(v)).toFixed(1) + '"/>';
    }
    if (h2) { var cv = []; for (i = 0; i <= 143; i++) cv[i] = h2.sn[i] == null ? null : h2.sn[i] / 10; svg += '<path class="cmp" d="' + line(cv, ay) + '"/>'; }
    svg += xAxis(yA + PH);
    /* B: temperatura */
    var tmin = 99, tmax = -99; for (i = MIN_I; i <= MAX_I; i++) { if (h.t[i] == null) continue; tmin = Math.min(tmin, h.t[i] / 10); tmax = Math.max(tmax, h.t[i] / 10); }
    if (tmin > tmax) { tmin = -1; tmax = 1; }
    var lo = Math.floor(Math.min(0, tmin) - 1), hi = Math.ceil(Math.max(0, tmax) + 1), by = function (v) { return yB + PH - (v - lo) / (hi - lo) * PH; };
    svg += '<text class="tt" x="' + PL + '" y="' + (yB - 3) + '">Temperatura na višini točke (°C)</text>';
    [lo, 0, hi].forEach(function (g) { svg += '<line class="' + (g === 0 ? 'z0' : 'gr') + '" x1="' + PL + '" x2="' + (CW - PR) + '" y1="' + by(g).toFixed(1) + '" y2="' + by(g).toFixed(1) + '"/><text class="ax" x="' + (PL - 5) + '" y="' + (by(g) + 4).toFixed(1) + '" text-anchor="end">' + g + '</text>'; });
    var tv = []; for (i = 0; i <= 143; i++) tv[i] = h.t[i] == null ? null : h.t[i] / 10;
    svg += '<path class="tl" d="' + line(tv, by) + '"/>' + xAxis(yB + PH);
    /* C: meja sneženja proti višini točke */
    var smin = 1e9, smax = -1e9; for (i = MIN_I; i <= MAX_I; i++) { var s = slAt(h, i); if (s == null) continue; smin = Math.min(smin, s); smax = Math.max(smax, s); }
    if (smin > smax) { smin = 0; smax = p.e; }
    var slo = Math.max(0, Math.floor((Math.min(smin, p.e) - 100) / 500) * 500), shi = Math.ceil((Math.max(smax, p.e) + 100) / 500) * 500, cy = function (v) { return yC + PH - (Math.max(slo, Math.min(shi, v)) - slo) / (shi - slo) * PH; };
    svg += '<text class="tt" x="' + PL + '" y="' + (yC - 3) + '">Meja sneženja in višina točke (m)</text>';
    for (i = MIN_I; i <= MAX_I; i++) {
      var s2 = slAt(h, i); if (s2 == null || phase(p.e, s2) !== 'snow') continue;
      svg += '<rect class="ph" x="' + (xOf(i) - PWID / 194).toFixed(1) + '" y="' + yC + '" width="' + (PWID / 97).toFixed(1) + '" height="' + PH + '"/>';
    }
    [slo, (slo + shi) / 2, shi].forEach(function (g) { svg += '<line class="gr" x1="' + PL + '" x2="' + (CW - PR) + '" y1="' + cy(g).toFixed(1) + '" y2="' + cy(g).toFixed(1) + '"/><text class="ax" x="' + (PL - 5) + '" y="' + (cy(g) + 4).toFixed(1) + '" text-anchor="end">' + Math.round(g) + '</text>'; });
    var sv = []; for (i = 0; i <= 143; i++) sv[i] = slAt(h, i);
    svg += '<path class="sll" d="' + line(sv, cy) + '"/><line class="el" x1="' + PL + '" x2="' + (CW - PR) + '" y1="' + cy(p.e).toFixed(1) + '" y2="' + cy(p.e).toFixed(1) + '"/>' +
      '<text class="ax" x="' + (CW - PR) + '" y="' + (cy(p.e) - 4).toFixed(1) + '" text-anchor="end">točka ' + p.e + ' m</text>' + xAxis(yC + PH);
    /* zdaj in kazalec */
    e = xOf(NOW).toFixed(1);
    svg += '<line class="now" x1="' + e + '" x2="' + e + '" y1="' + TOP + '" y2="' + (yC + PH) + '"/>';
    svg += '<line class="curl" id="sg-dc" x1="' + e + '" x2="' + e + '" y1="' + TOP + '" y2="' + (yC + PH) + '"/>';
    return svg + '</svg>';
  }
  function shareLink(p, msgEl) {
    var url = location.origin + location.pathname + '#t-' + p.id;
    var done = function (t) { msgEl.textContent = t; };
    if (navigator.share) navigator.share({ title: 'Snegofili: ' + p.n, url: url }).catch(function () { });
    else if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () { done('Povezava je kopirana.'); }, function () { done(url); });
    else done(url);
  }
  function openDetail(id, trigger) {
    var p = byId[id], h = hours && hours[id]; if (!p || !h) return;
    var cmpId = '', wrap = el('div', 'sg-dt');
    var hd = el('div', 'sg-dt-hd'), tt = el('div'); var h2 = el('h2', null, p.n); h2.id = 'sg-dt-t'; tt.appendChild(h2);
    tt.appendChild(el('p', 'sg-sub', (p.c === 'SI' ? 'Slovenija' : p.c) + ' · ' + p.e + ' m · ' + p.k + ' km od Rečice'));
    hd.appendChild(tt);
    var star = el('button', 'sg-star', '☆'); star.type = 'button'; star.dataset.id = id; star.addEventListener('click', function () { toggleFav(id); });
    hd.appendChild(star); wrap.appendChild(hd);
    var w = windows(h.sn, NOW), n48 = sum(h.sn, NOW + 1, NOW + 48);
    var kv = el('div', 'sg-dt-kv');
    [['Zadnjih 24 ur', cmText(w.past)], ['Naslednjih 24 ur', cmText(w.next)], ['Naslednjih 48 ur', cmText(n48)], ['Trenutna ura', (h.t[NOW] == null ? '—' : fmt(h.t[NOW] / 10, 1) + ' °C') + ' · ' + PHASE_TXT[phase(p.e, slAt(h, NOW))]]].forEach(function (a) {
      var d = el('div'); d.appendChild(el('small', null, a[0])); d.appendChild(el('b', null, a[1])); kv.appendChild(d);
    });
    wrap.appendChild(kv);
    if (p.m) wrap.appendChild(el('p', 'sg-sub', 'Izmerjena snežna odeja (ARSO): ' + p.m.d + ' cm, pred ' + Math.round(p.m.a) + ' h. To je meritev, ločena od modelske ocene novega snega.'));
    var chartBox = el('div', 'sg-dt-chart'); wrap.appendChild(chartBox);
    var rd = el('p', 'sg-dt-rd'); rd.setAttribute('aria-live', 'polite');
    var rg = el('input'); rg.type = 'range'; rg.min = MIN_I; rg.max = MAX_I; rg.step = 1; rg.value = cur; rg.className = 'sg-dt-rg'; rg.setAttribute('aria-label', 'Ura v grafih');
    wrap.appendChild(rg); wrap.appendChild(rd);
    wrap.appendChild(el('p', 'sg-leg', 'Stolpci: novi sneg (polni = prej, svetli = napoved). Črtkana vijolična črta: primerjana točka. Modro ozadje v spodnjem grafu: točka je nad mejo sneženja.'));
    function cursor(i) {
      var c = $('#sg-dc', chartBox); if (c) { var x = xOf(i).toFixed(1); c.setAttribute('x1', x); c.setAttribute('x2', x); }
      var t = h.t[i], s = slAt(h, i), ph = phase(p.e, s);
      rd.textContent = timeLabel(i) + ' (' + offText(i) + '): ' + (snowing(h, i) ? 'sneži ' + fmt(h.sn[i] / 10, 1) + ' cm/h' : 'brez novega snega') + ' · ' + (t == null ? '—' : fmt(t / 10, 1) + ' °C') +
        ' · meja sneženja ' + (s == null ? '—' : Math.round(s) + ' m') + ' (' + PHASE_TXT[ph].toLowerCase() + ')';
      rg.setAttribute('aria-valuetext', rd.textContent);
    }
    function draw() { CW = Math.max(320, Math.min(720, Math.round(chartBox.clientWidth || 720))); PWID = CW - PL - PR; chartBox.innerHTML = chartSvg(p, h, cmpId ? byId[cmpId] : null); cursor(+rg.value); }
    rg.addEventListener('input', function () { cursor(+rg.value); });
    var cmpRow = el('div', 'sg-dt-row'), cl = el('label', null, 'Primerjaj z '), sel = el('select');
    sel.appendChild(el('option', null, '— brez —')).value = '';
    pts.filter(function (q) { return q.id !== id && hours[q.id]; }).sort(function (a, b) { return a.n.localeCompare(b.n, 'sl'); }).forEach(function (q) { var o = el('option', null, q.n + ' (' + q.e + ' m)'); o.value = q.id; sel.appendChild(o); });
    sel.addEventListener('change', function () { cmpId = sel.value; draw(); });
    cl.appendChild(sel); cmpRow.appendChild(cl); wrap.appendChild(cmpRow);
    var act = el('div', 'sg-dt-act');
    if (hasCam(p)) { var cb = el('button', 'sg-btn', camLabel(p)); cb.type = 'button'; cb.addEventListener('click', function () { openCam(id); }); act.appendChild(cb); }
    (p.cl || []).forEach(function (c) { var a = el('a', 'sg-btn s', 'Kamera: ' + c.p); a.href = c.u; a.target = '_blank'; a.rel = 'noopener'; act.appendChild(a); });
    var sh = el('button', 'sg-btn s', 'Deli povezavo'); sh.type = 'button'; var shm = el('span', 'sg-sub'); sh.addEventListener('click', function () { shareLink(p, shm); });
    act.appendChild(sh); act.appendChild(shm); wrap.appendChild(act);
    wrap.appendChild(el('p', 'sg-attr', 'Modelska ocena (Open-Meteo): novi sneg iz padavin in meje sneženja, temperatura preračunana na višino točke. Ni meritev in ni plazovni bilten.'));
    draw();
    modal.open(wrap, 'Podrobnosti: ' + p.n, trigger, function () { if (/^#t-/.test(location.hash)) history.replaceState(null, '', location.pathname + location.search); });
    paintFavs();
    try { history.replaceState(null, '', '#t-' + id); } catch (e) { }
  }
  function hashOpen() {
    var m = /^#t-([\w-]+)$/.exec(location.hash); if (m && byId[m[1]] && hours && hours[m[1]] && !modal.isOpen()) openDetail(m[1]);
  }
  addEventListener('hashchange', hashOpen);

  /* ══ »Kam peljem po sneg?« ══ */
  function planUi() {
    var sec = $('#kam-peljem'); if (!sec) return;
    sec.hidden = false;
    var win = $('#sg-pl-win'), km = $('#sg-pl-km'), el2 = $('#sg-pl-el'), cm = $('#sg-pl-cm'), out = $('#sg-pl-out');
    function run() {
      var res = plan(pts, hours, { win: win.value, km: +km.value, minE: +el2.value, minCm: +cm.value, top: 3 });
      out.textContent = '';
      if (!res.length) { out.appendChild(el('li', 'sg-pl-none', 'Po modelu v izbranem oknu nobena točka ne doseže izbranih meril. Povečajte razdaljo ali znižajte prag.')); return; }
      res.forEach(function (x, k) {
        var p = x.p, li = el('li', 'sg-pl-i'), t = hours[p.id].t[NOW];
        li.appendChild(el('span', 'sg-pl-rank', String(k + 1)));
        var b = el('div', 'sg-pl-b'); b.appendChild(el('h3', null, p.n));
        b.appendChild(el('p', 'sg-sub', (p.c === 'SI' ? 'Slovenija' : p.c) + ' · ' + p.e + ' m · ' + p.k + ' km · zdaj ' + (t == null ? '—' : fmt(t / 10, 1) + ' °C')));
        var act = el('div', 'sg-dt-act');
        var d = el('button', 'sg-btn s', 'Podrobnosti'); d.type = 'button'; d.addEventListener('click', function () { openDetail(p.id, d); }); act.appendChild(d);
        if (hasCam(p)) { var c = el('button', 'sg-btn s', camLabel(p)); c.type = 'button'; c.addEventListener('click', function () { openCam(p.id, c); }); act.appendChild(c); }
        b.appendChild(act); li.appendChild(b);
        var v = el('div', 'sg-pl-v'); v.appendChild(el('b', null, cmText(x.cm))); v.appendChild(el('small', null, win.value === 'p24' ? 'v zadnjih 24 h' : win.value === 'n48' ? 'v 24–48 h' : 'v 24 h')); li.appendChild(v);
        out.appendChild(li);
      });
    }
    [win, km, el2, cm].forEach(function (s) { s.addEventListener('change', run); });
    run();
  }

  /* ══ toplotna karta: 40 točk × 97 ur ══ */
  var heat = { sort: 'snow', c: '*', rows: [], rh: 17 };
  var HM_COL = ['#3d73b5', '#5a97dd', '#85b9f3', '#b9d9ff', '#f4f9ff'];
  function heatOrder() {
    var base = pts.filter(function (p) { return hours[p.id] && (heat.c === '*' || p.c === heat.c); });
    var tot = {}; base.forEach(function (p) { tot[p.id] = sum(hours[p.id].sn, MIN_I, MAX_I); });
    base.sort(function (a, b) {
      if (heat.sort === 'elev') return b.e - a.e;
      if (heat.sort === 'km') return a.k - b.k;
      return tot[b.id] - tot[a.id] || b.e - a.e;
    });
    return base;
  }
  function heatDraw() {
    var cv = $('#sg-hm-cv'), lab = $('#sg-hm-lab'), ax = $('#sg-hm-ax'); if (!cv) return;
    heat.rows = heatOrder();
    var n = MAX_I - MIN_I + 1, rh = heat.rh, dpr = Math.min(2, window.devicePixelRatio || 1);
    var W = cv.parentNode.clientWidth || 600, H = heat.rows.length * rh;
    cv.style.height = H + 'px'; cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    var ctx = cv.getContext('2d'); ctx.scale(dpr, dpr); ctx.fillStyle = '#0b1730'; ctx.fillRect(0, 0, W, H);
    var cw = W / n;
    heat.rows.forEach(function (p, r) {
      var h = hours[p.id];
      for (var i = MIN_I; i <= MAX_I; i++) {
        var s = hstep(h.sn[i]); if (s < 0) { if ((i - MIN_I) % 2 === 0) { ctx.fillStyle = 'rgba(133,185,243,.05)'; ctx.fillRect((i - MIN_I) * cw + 0.5, r * rh + 1.5, cw - 1, rh - 3); } continue; }
        ctx.fillStyle = HM_COL[s]; ctx.fillRect((i - MIN_I) * cw + 0.5, r * rh + 1.5, Math.max(1, cw - 1), rh - 3);
      }
    });
    var nx = (NOW - MIN_I + 0.5) * cw; ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(nx, 0); ctx.lineTo(nx, H); ctx.stroke(); ctx.setLineDash([]);
    lab.textContent = '';
    heat.rows.forEach(function (p) { var b = el('span', 'sg-hm-l', p.n); b.title = p.n + ', ' + p.e + ' m'; b.addEventListener('click', function () { openDetail(p.id); }); lab.appendChild(b); }); /* oznake niso gumbi (17 px < 24 px cilj): tipkovnica ima kartice točk in pas zgoraj */
    ax.textContent = '';
    for (var i = MIN_I; i <= MAX_I; i++) {
      var d = localDate(i); if (!d || d.getUTCHours() !== 0) continue;
      var s2 = el('span', null, new Intl.DateTimeFormat('sl', { weekday: 'short', day: 'numeric', timeZone: 'UTC' }).format(d));
      s2.style.left = ((i - MIN_I) / n * 100) + '%'; ax.appendChild(s2);
    }
    var nz = el('span', 'now', 'trenutna ura'); nz.style.left = ((NOW - MIN_I + 0.5) / n * 100) + '%'; ax.appendChild(nz);
  }
  function heatCursor(i) { var c = $('#sg-hm-cur'); if (c) c.style.left = ((i - MIN_I + 0.5) / (MAX_I - MIN_I + 1) * 100) + '%'; }
  function heatUi() {
    var sec = $('#toplotna-karta'); if (!sec) return;
    sec.hidden = false; heatDraw();
    var leg = $('#sg-hm-leg');
    leg.innerHTML = 'Nov sneg na uro: ' + ['0,1', '0,5', '1', '2', '4+'].map(function (t, k) { return '<span><i style="background:' + HM_COL[k] + '"></i>' + t + ' cm</span>'; }).join('');
    $$('#sg-hbar button').forEach(function (b) {
      b.addEventListener('click', function () {
        var k = b.dataset.hs ? 'hs' : 'hc';
        if (k === 'hs') heat.sort = b.dataset.hs; else heat.c = b.dataset.hc;
        $$('#sg-hbar button[data-' + k + ']').forEach(function (x) { x.setAttribute('aria-pressed', x === b); }); heatDraw();
      });
    });
    var cv = $('#sg-hm-cv'), hmTip = el('div', 'sg-hm-tip'); hmTip.hidden = true; cv.parentNode.appendChild(hmTip);
    function at(e) {
      var r = cv.getBoundingClientRect(), n = MAX_I - MIN_I + 1;
      var i = MIN_I + Math.floor((e.clientX - r.left) / r.width * n), row = Math.floor((e.clientY - r.top) / heat.rh);
      if (i < MIN_I || i > MAX_I || row < 0 || row >= heat.rows.length) return null;
      return { i: i, p: heat.rows[row], x: e.clientX - r.left, y: (row + 1) * heat.rh };
    }
    cv.addEventListener('pointermove', function (e) {
      var a = at(e); if (!a) { hmTip.hidden = true; return; }
      var v = hours[a.p.id].sn[a.i] || 0;
      hmTip.textContent = a.p.n + ' · ' + timeLabel(a.i) + ' · ' + (v >= SNOWING_MIN ? fmt(v / 10, 1) + ' cm/h' : 'brez snega');
      hmTip.style.left = a.x + 'px'; hmTip.style.top = a.y + 'px'; hmTip.hidden = false;
    });
    cv.addEventListener('pointerleave', function () { hmTip.hidden = true; });
    cv.addEventListener('click', function (e) { var a = at(e); if (a) openDetail(a.p.id); });
    if (window.ResizeObserver) { var lw = 0; new ResizeObserver(function () { var w = cv.parentNode.clientWidth; if (w && Math.abs(w - lw) > 2) { lw = w; heatDraw(); } }).observe(cv.parentNode); }
  }

  /* ══ karta Windy: iframe šele po kliku, samo https://embed.windy.com ══ */
  (function () {
    var box = $('#sg-wy'); if (!box) return;
    var base = box.dataset.base, ov = 'snowAccu', frame = null;
    function url() { try { var u = new URL(base.replace('{overlay}', ov)); return u.protocol === 'https:' && u.hostname === 'embed.windy.com' ? u.href : null; } catch (e) { return null; } }
    $$('#windy .sg-heatbar button').forEach(function (b) {
      b.addEventListener('click', function () {
        ov = b.dataset.ov; $$('#windy .sg-heatbar button').forEach(function (x) { x.setAttribute('aria-pressed', x === b); });
        if (frame) { var u = url(); if (u) frame.src = u; }
      });
    });
    var btn = $('.sg-live', box); if (!btn) return;
    btn.addEventListener('click', function () {
      var u = url(); if (!u) return;
      frame = document.createElement('iframe'); frame.src = u; frame.loading = 'lazy'; frame.title = 'Windy: karta snega in vetra';
      frame.setAttribute('referrerpolicy', 'no-referrer'); frame.setAttribute('allowfullscreen', ''); frame.className = 'sg-wy-frame';
      btn.replaceWith(frame);
    });
  })();

  /* ══ ščit pred starimi podatki ══ */
  var g = document.getElementById('sg-gen');
  if (g) { var hh = (Date.now() - Date.parse(g.dataset.generated)) / 36e5; if (hh > 26) { g.textContent += ' · podatki niso sveži (' + Math.round(hh) + ' h)'; g.classList.add('sg-stale'); } }

  /* vdelava kamere na kartici točke (gumb »Kamera v živo«, iframe šele po kliku, samo dovoljeni gostitelji) */
  $$('.sg-live').forEach(function (b) {
    if (b.closest('.sg-lb')) return;
    b.addEventListener('click', function () {
      var w = b.parentNode, u; try { u = new URL(w.dataset.src); } catch (e) { return; }
      if (u.protocol !== 'https:' || (EMBED_OK[w.dataset.kind] || []).indexOf(u.hostname) < 0) return;
      var f = document.createElement('iframe'); f.src = u.href; f.loading = 'lazy'; f.title = w.dataset.title || 'Spletna kamera';
      f.setAttribute('referrerpolicy', 'no-referrer'); f.setAttribute('allowfullscreen', ''); f.className = 'sg-lb-frame'; b.replaceWith(f);
    });
  });

  layout();
  particles();
  bindCams();
  fetch('ure.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
    if (!j || !j.tocke) return;
    hours = j.tocke; nowLocal = j.now_local; bindControls(); sparks(); render(NOW); planUi(); heatUi(); hashOpen();
  }).catch(function () { });
  // Opozorilo na telefon (Web Push): pravila {id točke, prag cm}; strežnik shrani samo naslovnico naročnine in pravila.
  (function () {
    var box = document.getElementById('sg-alarm'); if (!box) return;
    var AK = 'wx-sg-alarm', MAX = +box.getAttribute('data-max') || 3;
    var selP = document.getElementById('sg-al-pt'), selC = document.getElementById('sg-al-cm'), addB = document.getElementById('sg-al-add'),
        list = document.getElementById('sg-al-list'), onB = document.getElementById('sg-al-on'), offB = document.getElementById('sg-al-off'),
        msg = document.getElementById('sg-al-msg'), ios = document.getElementById('sg-al-ios');
    var standalone = (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true;
    var isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    var rules = [], saved = false;
    try { var s0 = JSON.parse(localStorage.getItem(AK) || 'null'); if (s0 && Array.isArray(s0.rules)) { rules = s0.rules; saved = true; } } catch (e) { }
    function say(t) { msg.textContent = t || ''; }
    function nameOf(id) { for (var i = 0; i < selP.options.length; i++) if (selP.options[i].value === id) return selP.options[i].textContent; return id; }
    function draw() {
      list.textContent = '';
      rules.forEach(function (r, i) {
        var li = document.createElement('li'), t = document.createElement('span'), b = document.createElement('button');
        t.textContent = nameOf(r.id) + ': vsaj ' + r.cm + ' cm / 24 h'; b.type = 'button'; b.textContent = 'Odstrani'; b.setAttribute('aria-label', 'Odstrani pravilo: ' + t.textContent);
        b.addEventListener('click', function () { rules.splice(i, 1); draw(); say(''); });
        li.appendChild(t); li.appendChild(b); list.appendChild(li);
      });
      offB.hidden = !saved; onB.textContent = saved ? 'Shrani pravila' : 'Vklopi opozorilo';
    }
    if (isIOS && !standalone) { box.hidden = false; ios.hidden = false; onB.disabled = true; addB.disabled = true; return; }
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return;
    box.hidden = false; draw();
    function b64(s) { var p = '='.repeat((4 - s.length % 4) % 4), b = (s + p).replace(/-/g, '+').replace(/_/g, '/'), r = atob(b), o = new Uint8Array(r.length); for (var i = 0; i < r.length; i++) o[i] = r.charCodeAt(i); return o; }
    function post(path, body) { return fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status)); return j; }); }); }
    function getSub() { return navigator.serviceWorker.register('/sw.js').then(function () { return navigator.serviceWorker.ready; }).then(function (reg) { return reg.pushManager.getSubscription().then(function (sub) { return { reg: reg, sub: sub }; }); }); }
    addB.addEventListener('click', function () {
      var id = selP.value, cm = +selC.value;
      if (rules.length >= MAX) { say('Največ ' + MAX + ' pravila. Odstranite katero od obstoječih.'); return; }
      for (var i = 0; i < rules.length; i++) if (rules[i].id === id && rules[i].cm === cm) { say('To pravilo že imate.'); return; }
      rules.push({ id: id, cm: cm }); draw(); say('Pravilo je dodano. Pritisnite »' + onB.textContent + '«, da se shrani.');
    });
    onB.addEventListener('click', function () {
      if (!rules.length) { say('Dodajte vsaj eno pravilo.'); return; }
      if (Notification.permission === 'denied') { say('Obvestila so za to stran v brskalniku blokirana. Dovolite jih v nastavitvah strani.'); return; }
      Notification.requestPermission().then(function (p) {
        if (p !== 'granted') { say('Brez dovoljenja za obvestila opozorilo ne more delovati.'); return; }
        onB.disabled = true;
        return getSub().then(function (x) {
          if (x.sub) return x.sub;
          return fetch(API + '/push/vapid').then(function (r) { return r.json(); }).then(function (v) { return x.reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64(v.publicKey) }); });
        }).then(function (sub) { return post('/push/subscribe', { site: 'snegofili', subscription: sub.toJSON(), rules: rules }); })
          .then(function (r) { saved = true; try { localStorage.setItem(AK, JSON.stringify({ rules: rules })); } catch (e) { } draw(); say('Shranjeno: ' + r.rules + (r.rules === 1 ? ' pravilo.' : ' pravili.')); })
          .catch(function (e) { say('Ni uspelo: ' + (e && e.message ? e.message : 'poskusite znova čez nekaj minut') + '.'); })
          .then(function () { onB.disabled = false; });
      });
    });
    offB.addEventListener('click', function () {
      offB.disabled = true;
      getSub().then(function (x) { return x.sub ? post('/push/unsubscribe', { site: 'snegofili', endpoint: x.sub.endpoint }) : null; })
        .then(function () { saved = false; rules = []; try { localStorage.removeItem(AK); } catch (e) { } draw(); say('Opozorilo je izklopljeno, naslovnica in pravila so izbrisana s strežnika.'); })
        .catch(function (e) { say('Ni uspelo: ' + (e && e.message ? e.message : 'poskusite znova') + '.'); }).then(function () { offB.disabled = false; });
    });
  })();
  /* ══ navigacija po razdelkih, filter kamer, povezava do opozorila ══ */
  (function () {
    var nav = document.getElementById('sg-nav');
    function sync() {
      if (!nav) return;
      $$('a', nav).forEach(function (a) {
        var t = document.getElementById(a.getAttribute('href').slice(1));
        a.parentNode.hidden = !t || t.hidden;
      });
      var al = document.getElementById('sg-alarm'), cta = document.getElementById('sg-al-cta');
      if (cta) cta.hidden = !al || al.hidden;
    }
    window.addEventListener('load', function () { sync(); setTimeout(sync, 800); setTimeout(sync, 2500); });
    if (nav && 'IntersectionObserver' in window) {
      var links = {}; $$('a', nav).forEach(function (a) { links[a.getAttribute('href').slice(1)] = a; });
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting) { Object.keys(links).forEach(function (k) { links[k].removeAttribute('aria-current'); }); var a = links[e.target.id]; if (a) a.setAttribute('aria-current', 'true'); } });
      }, { rootMargin: '-30% 0px -60% 0px' });
      Object.keys(links).forEach(function (k) { var t = document.getElementById(k); if (t) io.observe(t); });
    }
    var cf = document.getElementById('sg-camf');
    if (cf) {
      cf.hidden = false;
      cf.addEventListener('click', function (e) {
        var b = e.target.closest('button'); if (!b) return;
        $$('button', cf).forEach(function (x) { x.setAttribute('aria-pressed', x === b); });
        $$('.sg-cam').forEach(function (f) { f.hidden = b.dataset.cf !== '*' && f.dataset.c !== b.dataset.cf; });
      });
    }
  })();
})(typeof window !== 'undefined' ? window : globalThis);
