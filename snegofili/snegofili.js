/* /snegofili/ — drsnik skozi čas, karta, prerez, kartice, delci.
   Model (step/phase/radius/windows) je brez DOM-a in izvožen za Node: usklajenost s Pythonom
   (tools/generate_snegofili_page.py) preverja tools/test_snegofili.py. Če spremeniš eno, spremeni drugo. */
(function (root) {
  'use strict';
  var NOW = 71, MIN_I = 23, MAX_I = 119; // −48 h … +48 h okoli »zdaj«, polna 24-urna okna na obeh straneh

  function step(cm) { return cm < 1 ? -1 : cm < 5 ? 0 : cm < 15 ? 1 : cm < 30 ? 2 : cm < 60 ? 3 : 4; }
  function phase(elev, slM) { if (slM == null) return 'rain'; var d = elev - slM; return d >= 100 ? 'snow' : d > -100 ? 'mix' : 'rain'; }
  function radius(cm) { return cm < 1 ? 6 : Math.min(34, 8 + 4.2 * Math.sqrt(cm)); }
  function barPct(cm) { return Math.min(100, Math.sqrt(Math.max(cm, 0)) / Math.sqrt(40) * 100); }
  function sum(a, from, to) { var s = 0; for (var i = Math.max(0, from); i <= Math.min(a.length - 1, to); i++) s += a[i] || 0; return Math.round(s) / 10; }
  function windows(sn, i) { return { past: sum(sn, i - 23, i), next: sum(sn, i + 1, i + 24) }; }
  function fmt(x, d) { return (Math.round(x * Math.pow(10, d)) / Math.pow(10, d)).toFixed(d).replace('.', ','); }
  function cmText(cm) { return cm < 1 ? '—' : fmt(cm, cm >= 10 ? 0 : 1) + ' cm'; }
  var PHASE_TXT = { snow: 'Sneg', mix: 'Moker sneg', rain: 'Dež ali suho' };

  var model = { NOW: NOW, MIN_I: MIN_I, MAX_I: MAX_I, step: step, phase: phase, radius: radius, barPct: barPct, windows: windows, cmText: cmText, PHASE_TXT: PHASE_TXT };
  if (typeof module !== 'undefined' && module.exports) { module.exports = model; }
  root.SgModel = model;
  if (typeof document === 'undefined') return;

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  var pts, hours, nowLocal, cur = NOW, timer = null;
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  try { pts = JSON.parse($('#sg-pts').textContent); } catch (e) { return; }
  var byId = {}; pts.forEach(function (p) { byId[p.id] = p; });
  var cards = $$('.sg-card'), sortKey = 'past', country = '*', onlyFresh = false;

  /* ── filtri in razvrščanje (delujejo tudi brez urnih podatkov) ── */
  var bar = $('#sg-filter');
  if (bar) {
    bar.hidden = false;
    bar.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      if (b.dataset.f === 'fresh') { onlyFresh = !onlyFresh; b.setAttribute('aria-pressed', onlyFresh); }
      else if (b.dataset.c) { country = b.dataset.c; $$('[data-c]', bar).forEach(function (x) { x.setAttribute('aria-pressed', x === b); }); }
      else if (b.dataset.s) { sortKey = b.dataset.s; $$('[data-s]', bar).forEach(function (x) { x.setAttribute('aria-pressed', x === b); }); }
      layout();
    });
  }
  function layout() {
    var grid = $('#sg-cards'); if (!grid) return;
    var vis = cards.filter(function (c) {
      var ok = (country === '*' || c.dataset.c === country) && (!onlyFresh || parseFloat(c.dataset.fresh) >= 1);
      c.hidden = !ok; return ok;
    });
    vis.sort(function (a, b) {
      if (sortKey === 'elev') return b.dataset.elev - a.dataset.elev;
      if (sortKey === 'km') return a.dataset.km - b.dataset.km;
      return parseFloat(b.dataset[sortKey]) - parseFloat(a.dataset[sortKey]);
    }).forEach(function (c) { grid.appendChild(c); });
  }

  /* ── prikaz ob izbrani uri ── */
  function timeLabel(i) {
    if (!nowLocal) return '';
    var m = /^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)/.exec(nowLocal); if (!m) return '';
    var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) + (i - NOW) * 36e5);
    return new Intl.DateTimeFormat('sl', { weekday: 'short', day: 'numeric', month: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'UTC' }).format(d).replace(/(\d)[:](\d\d)/, '$1.$2');
  }
  function offText(i) { var o = i - NOW; return o === 0 ? 'zdaj' : o < 0 ? 'pred ' + (-o) + ' h' : 'čez ' + o + ' h'; }

  function render(i) {
    cur = i;
    var best = null, active = 0, tot = 0;
    pts.forEach(function (p) {
      var h = hours[p.id]; if (!h) return;
      var w = windows(h.sn, i), sl = h.sl[i] == null ? null : h.sl[i] * 10, ph = phase(p.e, sl), st = step(w.past);
      var snowing = (h.sn[i] || 0) > 0.5; if (snowing) active++; tot++;
      if (!best || w.past > best.w.past) best = { p: p, w: w };
      /* karta */
      var c = $('#sg-map [data-id="' + p.id + '"]');
      if (c) {
        var show = st >= 0 && ph !== 'rain';
        c.setAttribute('r', radius(show ? w.past : 0).toFixed(1));
        c.setAttribute('class', 'sg-c ' + (show ? 's' + st + ' ' : 'ring ') + 'ph-' + ph);
        c.setAttribute('aria-label', p.n + ', ' + p.e + ' m: ' + PHASE_TXT[ph] + ', nazaj 24 h ' + cmText(w.past) + ', naprej 24 h ' + cmText(w.next));
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
        var t = h.t[i]; $('.sg-tt', k2).textContent = t == null ? '—' : fmt(t / 10, 1) + ' °C';
        $('.sg-sl', k2).textContent = sl == null ? '—' : (p.e - sl >= 0 ? 'nad mejo +' : 'pod mejo −') + Math.abs(Math.round((p.e - sl) / 10) * 10) + ' m';
        k2.setAttribute('aria-label', p.n + ': ' + PHASE_TXT[ph] + ', nazaj 24 h ' + cmText(w.past) + ', naprej 24 h ' + cmText(w.next));
      }
    });
    var lab = $('#sg-time'); if (lab) lab.textContent = offText(i) + (timeLabel(i) ? ' · ' + timeLabel(i) : '');
    var sl2 = $('#sg-range'); if (sl2) { sl2.value = i; sl2.setAttribute('aria-valuetext', offText(i) + ', ' + timeLabel(i)); }
    var ro = $('#sg-readout');
    if (ro && best) ro.textContent = best.w.past < 1 ? 'V 24 urah do te ure po modelu nikjer ni zapadlo več kot centimeter snega.'
      : 'Najbolj zasnežilo je na točki ' + best.p.n + ' (' + cmText(best.w.past) + ' v 24 h do te ure). Zdaj sneži na ' + active + ' od ' + tot + ' točk.';
    intensity = tot ? active / tot : 0;
    layout();
  }

  var intensity = 0;
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
  function go(c) {
    showTip(c); var k = document.getElementById('t-' + c.dataset.id); if (!k) return;
    k.hidden = false; k.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
    k.classList.remove('sg-flash'); void k.offsetWidth; k.classList.add('sg-flash');
  }

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
    var full = map.getAttribute('viewBox'), b = $('button', zb);
    b.addEventListener('click', function () {
      var on = b.getAttribute('aria-pressed') !== 'true';
      b.setAttribute('aria-pressed', on);
      b.textContent = on ? 'Pokaži ves alpski lok' : 'Približaj: Slovenija in sosedje';
      var v = on ? b.dataset.view : full, q = v.split(' ');
      map.setAttribute('viewBox', v); map.style.aspectRatio = q[2] + ' / ' + q[3];
      map.classList.toggle('zoom', on);
      if (tip) tip.hidden = true;
    });
  }
  layout();
  particles();
  fetch('ure.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
    if (!j || !j.tocke) return;
    hours = j.tocke; nowLocal = j.now_local; bindControls(); render(NOW);
  }).catch(function () { });
})(typeof window !== 'undefined' ? window : globalThis);
