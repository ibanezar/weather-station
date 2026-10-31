/* Meteorec za podjetja: izbirnik povezave, segmenti, živa meritev, obrazec in sledenje.
   Sledilniki (Google tag, Meta Pixel) se naložijo šele po soglasju (wx-cookie-consent = accepted,
   isti ključ kot na glavni strani). Brez soglasja se noben dogodek ne pošlje. */
(function () {
  'use strict';
  var CFG = window.PODJETJA_CFG || {};
  var CKEY = 'wx-cookie-consent';
  var GTM = 'GTM-N2B38HHG', GA = 'G-LE8PJ1HR8B';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };

  /* ── sledenje ───────────────────────────────────────────── */
  var tagsLoaded = false, queue = [];
  function consent() { try { return localStorage.getItem(CKEY); } catch (e) { return null; } }
  function addScript(src) { var s = document.createElement('script'); s.async = true; s.src = src; document.head.appendChild(s); }
  function loadTags() {
    if (tagsLoaded) return; tagsLoaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag('js', new Date()); window.gtag('config', GA);
    window.dataLayer.push({ 'gtm.start': Date.now(), event: 'gtm.js' });
    addScript('https://www.googletagmanager.com/gtm.js?id=' + GTM);
    addScript('https://www.googletagmanager.com/gtag/js?id=' + GA);
    if (CFG.pixel) {
      /* standardna Meta Pixel zanka; naloži se samo, če je ID vpisan v generator */
      (function (f, b, e, v, n, t, s) {
        if (f.fbq) return; n = f.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments); };
        if (!f._fbq) f._fbq = n; n.push = n; n.loaded = true; n.version = '2.0'; n.queue = [];
        t = b.createElement(e); t.async = true; t.src = v; s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
      })(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');
      window.fbq('init', CFG.pixel);
      window.fbq('track', 'PageView');
    }
  }
  function send(name, params) {
    params = params || {};
    var o = { event: name }; for (var k in params) o[k] = params[k];
    (window.dataLayer = window.dataLayer || []).push(o);
    if (window.fbq) {
      if (name === 'ViewContent' || name === 'Lead') window.fbq('track', name, params);
      else window.fbq('trackCustom', name, params);
    }
  }
  function track(name, params) {
    var c = consent();
    if (c === 'accepted') { loadTags(); send(name, params); }
    else if (c === null) queue.push([name, params]);
  }
  function setConsent(v) {
    try { localStorage.setItem(CKEY, v); } catch (e) {}
    var b = $('#cookie'); if (b) b.hidden = true;
    if (v === 'accepted') { loadTags(); queue.forEach(function (q) { send(q[0], q[1]); }); }
    queue = [];
  }
  var banner = $('#cookie');
  if (banner) {
    if (consent() === null) banner.hidden = false;
    $$('[data-consent]', banner).forEach(function (b) { b.addEventListener('click', function () { setConsent(b.getAttribute('data-consent')); }); });
  }
  if (consent() === 'accepted') loadTags();
  if (document.getElementById('q')) track('ViewContent', { content_name: document.title, content_category: 'podjetja' });

  /* ── hvala: konverzija je bila poslana na obrazcu ─────────── */
  if (!$('#q')) return;

  /* ── učinki: razkrivanje, nagib telefona, menjava opozoril, meni, FAQ ───── */
  var malo = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var rz = $$('.rz');
  if ('IntersectionObserver' in window && !malo) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('on'); io.unobserve(e.target); } }); }, { rootMargin: '0px 0px -6% 0px' });
    rz.forEach(function (el, i) { el.style.transitionDelay = (i % 4) * 70 + 'ms'; io.observe(el); });
  } else { rz.forEach(function (el) { el.classList.add('on'); }); }

  var art = $('.hero-art'), heroVisible = true;
  if (art && 'IntersectionObserver' in window) new IntersectionObserver(function (es) { heroVisible = es[0].isIntersecting; }).observe(art);
  if (art && !malo && window.matchMedia('(hover: hover)').matches) {
    var raf = 0, ev = null;
    addEventListener('pointermove', function (e) {
      ev = e; if (raf || !heroVisible) return;
      raf = requestAnimationFrame(function () {
        raf = 0; var nx = ev.clientX / innerWidth * 2 - 1, ny = ev.clientY / innerHeight * 2 - 1;
        art.style.setProperty('--ry', (-12 + nx * 10).toFixed(2) + 'deg'); art.style.setProperty('--rx', (5 - ny * 7).toFixed(2) + 'deg');
        art.style.setProperty('--px', nx.toFixed(3)); art.style.setProperty('--py', ny.toFixed(3));
        var ph = art.querySelector('.phone'); if (ph) { ph.style.setProperty('--ry', (-12 + nx * 10).toFixed(2) + 'deg'); ph.style.setProperty('--rx', (5 - ny * 7).toFixed(2) + 'deg'); }
      });
    }, { passive: true });
    var cards = $$('.card');
    addEventListener('pointermove', function (e) {
      cards.forEach(function (c) { var r = c.getBoundingClientRect(); if (r.bottom < 0 || r.top > innerHeight) return; c.style.setProperty('--mx', (e.clientX - r.left) + 'px'); c.style.setProperty('--my', (e.clientY - r.top) + 'px'); });
    }, { passive: true });
  }

  var ALERTS = [['Pozeba ponoči', 'Temperatura bo padla pod vašo mejo. Ukrepajte pravočasno.'],
    ['Veter nad mejo', 'Sunki presegajo vrednost, ki ste jo nastavili.'],
    ['Nevihta se bliža', 'Opozorilo pred strelami in točo na vaši lokaciji.']];
  var al = $('#ph-alert'), ai = 0;
  if (al && !malo) setInterval(function () {
    if (!heroVisible || document.hidden) return;
    ai = (ai + 1) % ALERTS.length; $('#ph-al-t').textContent = ALERTS[ai][0]; $('#ph-al-b').textContent = ALERTS[ai][1];
    al.classList.remove('in'); void al.offsetWidth; al.classList.add('in');
  }, 4200);

  var burger = $('#burger');
  function meni(odpri) { document.body.classList.toggle('meni-odprt', odpri); if (burger) { burger.setAttribute('aria-expanded', odpri); burger.setAttribute('aria-label', odpri ? 'Zapri meni' : 'Odpri meni'); } }
  if (burger) {
    burger.addEventListener('click', function () { meni(!document.body.classList.contains('meni-odprt')); });
    $$('#mob a').forEach(function (a) { a.addEventListener('click', function () { meni(false); }); });
    addEventListener('keydown', function (e) { if (e.key === 'Escape') meni(false); });
  }

  var det = $$('.faq details');
  det.forEach(function (d) { d.addEventListener('toggle', function () { if (d.open) det.forEach(function (o) { if (o !== d) o.open = false; }); }); });

  /* ── povezava postaje ───────────────────────────────────── */
  var NOTES = {
    wifi: 'Postaja se poveže na vaš WiFi usmerjevalnik. Pred postavitvijo preverimo moč signala na mestu postaje.',
    sim: 'Postaja se poveže prek mobilnega interneta. Preverimo pokritost na lokaciji, naročnina za mobilni internet pa je dodaten strošek.'
  };
  var LABELS = { wifi: 'Povezava: WiFi', sim: 'Povezava: mobilni internet' };
  function eur(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ' €'; }
  var conn = 'wifi';
  function setConn(v, fromUser) {
    conn = v;
    var note = NOTES[v];
    if (v === 'sim' && CFG.showPrices && CFG.sim) note += ' Pribitek: ' + eur(CFG.sim.once) + ' enkratno in ' + eur(CFG.sim.month) + ' na mesec.';
    $('#conn-note').textContent = note;
    $$('[data-conn]').forEach(function (el) { el.textContent = LABELS[v]; });
    $$('[data-sim-add]').forEach(function (el) { el.hidden = v !== 'sim'; });
    $('#h-povezava').value = v;
    var w = v === 'sim' ? '#w2' : null;
    if (fromUser && w) { var r = $(w); if (r) r.checked = true; }
    if (fromUser) track('select_connection', { connection: v });
  }
  $$('input[name=conn]').forEach(function (r) { r.addEventListener('change', function (e) { setConn(e.target.value, true); }); });
  setConn('wifi', false);

  /* ── paket ──────────────────────────────────────────────── */
  var NAMES = { osnovni: 'Osnovni', pro: 'Pro', premium: 'Premium', 'po-meri': 'Po meri' };
  function setPaket(id) {
    $('#h-paket').value = id || '';
    var c = $('#chosen');
    if (!id) { c.hidden = true; c.textContent = ''; return; }
    c.hidden = false; c.textContent = 'Izbrani paket: ' + NAMES[id];
    var x = document.createElement('button'); x.type = 'button'; x.textContent = 'Odstrani izbiro';
    x.addEventListener('click', function () { setPaket(''); }); c.appendChild(x);
  }
  $$('[data-paket]').forEach(function (a) {
    a.addEventListener('click', function () { var id = a.getAttribute('data-paket'); setPaket(id); track('select_package', { package: id, connection: conn }); });
  });

  /* ── segment (?segment=kmetija ali #kmetija) ──────────────── */
  var SEG = {};
  $$('.case').forEach(function (c) { SEG[c.id] = c; });
  function applySegment(id, scroll) {
    var c = SEG[id]; if (!c) return;
    $$('.case').forEach(function (x) { x.classList.toggle('is-active', x === c); var f = $('.case-flag', x); if (f) f.hidden = x !== c; });
    $('#h-segment').value = id;
    var sel = $('#f-panoga'); if (sel) sel.value = c.getAttribute('data-dej');
    if (scroll) { var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; c.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' }); }
  }
  $$('[data-segment]').forEach(function (a) { a.addEventListener('click', function () { applySegment(a.getAttribute('data-segment'), false); }); });
  var qs = new URLSearchParams(location.search);
  var seg = qs.get('segment') || location.hash.replace('#', '');
  if (SEG[seg]) applySegment(seg, !!qs.get('segment'));

  /* ── UTM in fbclid v skrita polja ─────────────────────────── */
  ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'fbclid'].forEach(function (k) {
    var v = qs.get(k), el = document.querySelector('input[name=' + k + ']');
    if (v && el) el.value = v.slice(0, 300);
  });

  /* ── živa meritev z IREICA1 (samo zunanje vrednosti) ─────────── */
  (function live() {
    var tEl = $('#lw-temp'); if (!tEl) return;
    function put(id, v) { var el = document.getElementById(id); if (el) el.textContent = v; }
    function fail() { ['lw-temp', 'lw-wind', 'lw-rain', 'ph-temp', 'ph-hum', 'ph-pres', 'ph-wind', 'ph-rain', 'ph-dew', 'ph-gust'].forEach(function (i) { put(i, '–'); });
      put('lw-time', 'Meritve trenutno ni mogoče naložiti.'); put('ph-time', 'Meritve trenutno ni'); }
    function num(v, d) { return v == null || isNaN(v) ? '–' : Number(v).toFixed(d).replace('.', ','); }
    fetch(CFG.worker + '/').then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (d) {
      var o = d && d.observations && d.observations[0], m = o && o.metric; if (!m) throw 0;
      tEl.textContent = num(m.temp, 1) + ' °C';
      $('#lw-wind').textContent = num(m.windSpeed, 0) + ' km/h';
      $('#lw-rain').textContent = num(m.precipTotal, 1) + ' mm';
      put('ph-temp', num(m.temp, 1) + '\u00a0°C'); put('ph-hum', num(o.humidity, 0) + '\u00a0%');
      put('ph-pres', num(m.pressure, 0) + '\u00a0hPa'); put('ph-wind', num(m.windSpeed, 0) + '\u00a0km/h');
      put('ph-dew', num(m.dewpt, 1) + '\u00a0°C'); put('ph-gust', num(m.windGust, 0) + '\u00a0km/h');
      put('ph-rain', num(m.precipTotal, 1) + '\u00a0mm');
      var t = o.obsTimeLocal ? new Date(o.obsTimeLocal.replace(' ', 'T')) : null, el = $('#lw-time');
      if (!t || isNaN(t)) { el.textContent = 'Čas meritve ni znan.'; put('ph-time', 'Čas meritve ni znan'); return; }
      var pad = function (n) { return (n < 10 ? '0' : '') + n; };
      put('ph-time', 'Zadnja meritev ob ' + t.getHours() + '.' + pad(t.getMinutes()));
      var age = (Date.now() - t.getTime()) / 60000;
      el.textContent = 'Zadnje branje: ' + t.getDate() + '. ' + (t.getMonth() + 1) + '. ob ' + t.getHours() + '.' + pad(t.getMinutes()) +
        (age > 40 ? ' (podatek je star, postaja trenutno ne pošilja)' : '') + '.';
    }).catch(fail);
  })();

  /* ── obrazec ───────────────────────────────────────────── */
  var form = $('#q'), errEl = $('#form-err'), t0 = Date.now(), sending = false;
  function showErr(msg, el) { errEl.textContent = msg; errEl.hidden = false; if (el) { el.setAttribute('aria-invalid', 'true'); el.focus(); } else errEl.scrollIntoView({ block: 'center' }); }
  function clearErr() { errEl.hidden = true; $$('[aria-invalid]', form).forEach(function (x) { x.removeAttribute('aria-invalid'); }); }
  function validate() {
    var firma = $('#f-firma'), kraj = $('#f-kraj'), kon = $('#f-kontakt'), soglasje = $('#f-soglasje');
    if (!firma.value.trim()) return ['Vpišite podjetje ali kmetijo.', firma];
    if (!kraj.value.trim()) return ['Vpišite kraj in lokacijo postaje.', kraj];
    var k = kon.value.trim();
    var jeMail = /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]{2,}$/.test(k);
    var jeTel = /^[+()\d\s\/.-]{6,}$/.test(k) && (k.match(/\d/g) || []).length >= 6;
    if (!jeMail && !jeTel) return ['Vpišite veljaven e-naslov ali telefonsko številko.', kon];
    if (!soglasje.checked) return ['Za pošiljanje je potrebna privolitev v obdelavo podatkov.', soglasje];
    return null;
  }
  form.addEventListener('submit', function (ev) {
    ev.preventDefault(); if (sending) return; clearErr();
    var bad = validate(); if (bad) { showErr(bad[0], bad[1]); return; }
    var w = $('input[name=w]:checked');
    var payload = {
      firma: $('#f-firma').value.trim(), kraj: $('#f-kraj').value.trim(), dejavnost: $('#f-panoga').value, postaj: $('#f-st').value,
      spremljati: $$('input[name=m]:checked').map(function (x) { return x.value; }), wifi: w ? w.value : '',
      opomba: $('#f-opomba').value.trim(), kontakt: $('#f-kontakt').value.trim(), soglasje: true,
      website: $('#f-web').value, t: Date.now() - t0,
      paket: $('#h-paket').value, povezava: $('#h-povezava').value, segment: $('#h-segment').value
    };
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'fbclid'].forEach(function (k) { payload[k] = document.querySelector('input[name=' + k + ']').value; });
    var btn = $('#send'); sending = true; btn.disabled = true; btn.textContent = 'Pošiljam …';
    fetch(CFG.worker + '/api/povprasevanje', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok || !res.j.ok) throw new Error(res.j.error || 'napaka');
        track('Lead', { package: payload.paket || 'brez', segment: payload.segment || 'brez', connection: payload.povezava });
        setTimeout(function () { location.href = '/podjetja/hvala/'; }, 400);
      })
      .catch(function (err) {
        sending = false; btn.disabled = false; btn.textContent = 'Pošljite povpraševanje';
        var m = err && err.message && err.message !== 'napaka' && err.message !== 'Failed to fetch' ? err.message : 'Povpraševanja ni bilo mogoče poslati.';
        showErr(m + ' Poskusite znova ali pišite na ' + (CFG.email || 'naš e-naslov') + '.');
      });
  });
})();
