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

  /* ── kalkulator praga: katere noči bi sprožile opozorilo ─────────────── */
  var prag = $('#prag');
  if (prag) {
    var bars = $$('#noci i[data-t]'), total = bars.length, prvic = true, shown = null, tw = 0;
    var znak = function (th) { return (th > 0 ? '+' : th < 0 ? '\u2212' : '') + Math.abs(th) + '\u00a0°C'; };
    var HINT = function (th) {
      if (th >= 3) return 'Zgodnje opozorilo: ob jasni mirni noči je lahko pri tleh že slana, tudi ko zrak kaže nekaj stopinj nad ničlo.';
      if (th >= 1) return 'Meja tik nad ničlo: opozorilo, ko se zrak približuje zmrzali (okvirno, odvisno od vrste in faze rasti).';
      if (th === 0) return 'Ničla: zmrzal. Osnovna meja za pozebo pri cvetju in mladih poganjkih (okvirno, odvisno od vrste in faze rasti).';
      if (th >= -2) return 'Zmrzal pod ničlo: poškodbe cvetov in mladih poganjkov so že mogoče, odvisno od vrste in faze rasti.';
      return 'Huda zmrzal: meja, pri kateri nastane škoda tudi na odpornejših rastlinah (okvirno).';
    };
    var tween = function (to) {
      var el = $('#prag-n'), from = shown == null ? to : shown; shown = to;
      cancelAnimationFrame(tw);
      if (malo || from === to) { el.textContent = to; return; }
      var t0 = performance.now(), dur = 260;
      (function step(t) { var k = Math.min(1, (t - t0) / dur); el.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3))); if (k < 1) tw = requestAnimationFrame(step); })(t0);
    };
    var osvezi = function () {
      var th = +prag.value, c = 0;
      bars.forEach(function (b) { var on = +b.getAttribute('data-t') <= th; b.classList.toggle('on', on); if (on) c++; });
      $('#prag-v').textContent = znak(th); tween(c);
      $('#prag-t').textContent = (c % 100 === 1 ? 'dan' : c % 100 === 2 ? 'dneva' : 'dni') + ' od ' + total + ' dni z meritvijo, ko je postaja izmerila ' + znak(th) + ' ali manj.';
      $('#prag-hint').textContent = HINT(th);
    };
    prag.addEventListener('input', function () { osvezi(); if (prvic) { prvic = false; track('use_calculator', { threshold: +prag.value }); } });
    osvezi();
  }

  /* ── noč na polju: koraki se prižgejo zaporedno ─────────────────────── */
  var noc = $('#noc-list');
  if (noc) {
    if ('IntersectionObserver' in window && !malo) {
      var ion = new IntersectionObserver(function (es) { if (es[0].isIntersecting) { noc.classList.add('on'); ion.disconnect(); } }, { threshold: .3 });
      ion.observe(noc);
    } else noc.classList.add('on');
  }

  /* ── shema postaje: klik na oznako ali gumb ───────────────────────── */
  var delGumbi = $$('.part'), pini = $$('.pin');
  function izberiDel(id) {
    delGumbi.forEach(function (b) {
      var on = b.getAttribute('data-part') === id; b.setAttribute('aria-pressed', on);
      if (on) { $('#part-name').textContent = b.querySelector('span:last-child').textContent; $('#part-text').textContent = b.getAttribute('data-text'); }
    });
    pini.forEach(function (p) { p.classList.toggle('on', p.getAttribute('data-part') === id); });
  }
  delGumbi.forEach(function (b) { b.addEventListener('click', function () { izberiDel(b.getAttribute('data-part')); }); });
  pini.forEach(function (p) { p.addEventListener('click', function () { izberiDel(p.getAttribute('data-part')); }); });
  if (delGumbi.length) izberiDel(delGumbi[0].getAttribute('data-part'));

  /* ── povezava postaje ───────────────────────────────────── */
  var NOTES = {
    wifi: 'Postaja se poveže na vaš WiFi usmerjevalnik. Pred postavitvijo preverimo moč signala na mestu postaje.',
    sim: 'Postaja se poveže prek mobilnega interneta. Preverimo pokritost na lokaciji, naročnina za mobilni internet pa je dodaten strošek.'
  };
  var LABELS = { wifi: 'Povezava: WiFi', sim: 'Povezava: mobilni internet' };
  var BASIS = { wifi: 'Brez DDV · povezava WiFi', sim: 'Brez DDV · mobilni internet' };
  function eur(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.') + '\u00a0€'; }
  var conn = 'wifi';
  /* skupaj v prvem letu = enkratno + 12 mesečnih naročnin (+ pribitek za mobilni internet) */
  var yearEls = $$('.price[data-once]').map(function (pr) {
    var y = $('[data-year]', pr);
    return { pr: pr, y: y, od: /^od /.test(y.textContent), basis: $('[data-basis]', pr) };
  });
  function renderYear() {
    yearEls.forEach(function (o) {
      var t = +o.pr.getAttribute('data-once') + 12 * +o.pr.getAttribute('data-month');
      if (conn === 'sim' && CFG.sim) t += CFG.sim.once + 12 * CFG.sim.month;
      o.y.textContent = (o.od ? 'od ' : '') + eur(t);
      if (o.basis) o.basis.textContent = BASIS[conn];
    });
  }
  function setConn(v, fromUser) {
    conn = v;
    var note = NOTES[v];
    if (v === 'sim' && CFG.showPrices && CFG.sim) note += ' Pribitek: ' + eur(CFG.sim.once) + ' enkratno in ' + eur(CFG.sim.month) + ' na mesec.';
    $('#conn-note').textContent = note;
    $$('[data-conn]').forEach(function (el) { el.textContent = LABELS[v]; });
    $$('[data-sim-add]').forEach(function (el) { el.hidden = v !== 'sim'; });
    $('#h-povezava').value = v;
    renderYear();
    if (fromUser) { var r = $(v === 'sim' ? '#w2' : '#w1'); if (r) r.checked = true; }
    if (fromUser) { track('select_connection', { connection: v }); track('pricing_connection_change', { connection: v }); }
    renderChosen();
  }
  $$('input[name=conn]').forEach(function (r) { r.addEventListener('change', function (e) { setConn(e.target.value, true); }); });

  /* ── paket ──────────────────────────────────────────────── */
  var NAMES = { osnovni: 'Osnovni', pro: 'Pro', premium: 'Premium', 'po-meri': 'Po meri' };
  var paketId = '';
  /* izbira iz prejšnjih korakov (paket, povezava, dejavnost) je vidna nad obrazcem in jo je mogoče odstraniti */
  function renderChosen() {
    var c = $('#chosen'); if (!c) return;
    $('#h-paket').value = paketId;
    if (!paketId) { c.hidden = true; c.textContent = ''; return; }
    c.hidden = false; c.textContent = 'Izbrani paket: ' + NAMES[paketId] + ' · ' + LABELS[conn].toLowerCase();
    var x = document.createElement('button'); x.type = 'button'; x.textContent = 'Odstrani izbiro';
    x.addEventListener('click', function () { setPaket(''); }); c.appendChild(x);
  }
  function setPaket(id) { paketId = id || ''; renderChosen(); }
  $$('[data-paket]').forEach(function (a) {
    a.addEventListener('click', function () { var id = a.getAttribute('data-paket'); setPaket(id); track('select_package', { package: id, connection: conn }); track('package_select', { package: id, connection: conn }); });
  });
  setConn('wifi', false);

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
  $$('[data-segment]').forEach(function (a) { a.addEventListener('click', function () { var id = a.getAttribute('data-segment'); applySegment(id, false); track('industry_select', { industry: id }); }); });
  var qs = new URLSearchParams(location.search);
  var seg = qs.get('segment') || location.hash.replace('#', '');
  if (SEG[seg]) applySegment(seg, !!qs.get('segment'));

  /* ── poziv k dejanju: kje so ljudje kliknili ─────────────────── */
  $$('[data-cta]').forEach(function (a) {
    a.addEventListener('click', function () {
      var where = a.getAttribute('data-cta');
      track(where === 'hero' || where === 'hero-paketi' ? 'hero_cta_click' : 'cta_click', { location: where });
    });
  });

  /* ── UTM in fbclid v skrita polja ─────────────────────────── */
  ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'fbclid'].forEach(function (k) {
    var v = qs.get(k), el = document.querySelector('input[name=' + k + ']');
    if (v && el) el.value = v.slice(0, 300);
  });

  /* ── živa meritev z IREICA1 (samo zunanje vrednosti) ───────────
     Telefon v herou se začne z VZORČNIMI vrednostmi (označene kot primer), da nikoli ni prazen. Ob uspešnem
     branju se zamenjajo z meritvijo in oznaka postane »v živo«; ob napaki ostanejo vzorčne in tako označene. */
  (function live() {
    var tEl = $('#lw-temp'); if (!tEl) return;
    var ph = $('#phone');
    function put(id, v) { var el = document.getElementById(id); if (el) el.textContent = v; }
    function fail() {
      ['lw-temp', 'lw-wind', 'lw-rain'].forEach(function (i) { put(i, '–'); });
      put('lw-time', 'Meritve trenutno ni mogoče naložiti.');
      put('ph-time', 'Meritve trenutno ni, prikazane so vzorčne vrednosti');
    }
    function num(v, d) { return v == null || isNaN(v) ? '–' : Number(v).toFixed(d).replace('.', ',').replace('-', '\u2212'); }
    fetch(CFG.worker + '/').then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (d) {
      var o = d && d.observations && d.observations[0], m = o && o.metric; if (!m) throw 0;
      tEl.textContent = num(m.temp, 1) + ' °C';
      $('#lw-wind').textContent = num(m.windSpeed, 0) + ' km/h';
      $('#lw-rain').textContent = num(m.precipTotal, 1) + ' mm';
      put('ph-temp', num(m.temp, 1) + '\u00a0°C'); put('ph-hum', num(o.humidity, 0) + '\u00a0%');
      put('ph-pres', num(m.pressure, 0) + '\u00a0hPa'); put('ph-wind', num(m.windSpeed, 0) + '\u00a0km/h');
      put('ph-dew', num(m.dewpt, 1) + '\u00a0°C'); put('ph-gust', num(m.windGust, 0) + '\u00a0km/h');
      put('ph-rain', num(m.precipTotal, 1) + '\u00a0mm');
      var t = o.obsTimeLocal ? new Date(o.obsTimeLocal.replace(' ', 'T')) : null, el = $('#lw-time');
      if (ph) {
        ph.classList.remove('is-sample'); ph.classList.add('is-live');
        ph.setAttribute('aria-label', 'Prikaz na telefonu: živa meritev postaje IREICA1 in primer opozorila');
      }
      put('ph-stn', 'IREICA1 · Rečica'); put('chip-live-t', 'V živo z IREICA1');
      var dot = $('#chip-live .dot'); if (dot) dot.classList.add('live-dot');
      if (!t || isNaN(t)) { el.textContent = 'Čas meritve ni znan.'; put('ph-time', 'Čas meritve ni znan'); return; }
      var pad = function (n) { return (n < 10 ? '0' : '') + n; };
      put('ph-time', 'Zadnja meritev ob ' + t.getHours() + '.' + pad(t.getMinutes()));
      var age = (Date.now() - t.getTime()) / 60000;
      if (age > 40) { put('chip-live-t', 'Zadnja meritev IREICA1'); if (dot) dot.classList.remove('live-dot'); }
      el.textContent = 'Zadnje branje: ' + t.getDate() + '. ' + (t.getMonth() + 1) + '. ob ' + t.getHours() + '.' + pad(t.getMinutes()) +
        (age > 40 ? ' (podatek je star, postaja trenutno ne pošilja)' : '') + '.';
    }).catch(fail);
  })();

  /* ── spodnji CTA na telefonu: viden po hero-ju, skrit ob obrazcu, tipkanju in odprtem meniju/piškotkih ─── */
  (function sticky() {
    var bar = $('#sticky'), heroEl = $('.hero'), formEl = $('#povprasevanje'); if (!bar || !heroEl || !formEl || !('IntersectionObserver' in window)) return;
    var heroIn = true, formIn = false, typing = false;
    function upd() {
      var cookie = $('#cookie'), blocked = cookie && !cookie.hidden;
      var on = !heroIn && !formIn && !typing && !blocked && !document.body.classList.contains('meni-odprt');
      if (on) { bar.hidden = false; requestAnimationFrame(function () { bar.classList.add('on'); }); }
      else { bar.classList.remove('on'); }
    }
    new IntersectionObserver(function (es) { heroIn = es[0].isIntersecting; upd(); }).observe(heroEl);
    new IntersectionObserver(function (es) { formIn = es[0].isIntersecting; upd(); }, { rootMargin: '0px 0px -25% 0px' }).observe(formEl);
    document.addEventListener('focusin', function (e) { typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) && !!e.target.closest('#q'); upd(); });
    document.addEventListener('focusout', function () { typing = false; upd(); });
    $$('[data-consent]').forEach(function (b) { b.addEventListener('click', function () { setTimeout(upd, 0); }); });
    var mo = new MutationObserver(upd); mo.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    upd();
  })();

  /* ── obrazec ───────────────────────────────────────────── */
  var form = $('#q'), errEl = $('#form-err'), t0 = Date.now(), sending = false;
  function showErr(msg, el) { errEl.textContent = msg; errEl.hidden = false; if (el) { el.setAttribute('aria-invalid', 'true'); el.focus(); } else errEl.scrollIntoView({ block: 'center' }); }
  function clearErr() { errEl.hidden = true; $$('[aria-invalid]', form).forEach(function (x) { x.removeAttribute('aria-invalid'); }); }
  function validate() {
    var firma = $('#f-firma'), kraj = $('#f-kraj'), dej = $('#f-panoga'), kon = $('#f-kontakt'), soglasje = $('#f-soglasje');
    if (!firma.value.trim()) return ['Vpišite podjetje ali kmetijo.', firma];
    if (!kraj.value.trim()) return ['Vpišite kraj in lokacijo postaje.', kraj];
    if (!dej.value) return ['Izberite dejavnost.', dej];
    var k = kon.value.trim();
    var jeMail = /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]{2,}$/.test(k);
    var jeTel = /^[+()\d\s\/.-]{6,}$/.test(k) && (k.match(/\d/g) || []).length >= 6;
    if (!jeMail && !jeTel) return ['Vpišite veljaven e-naslov ali telefonsko številko.', kon];
    if (!soglasje.checked) return ['Za pošiljanje je potrebna privolitev v obdelavo podatkov.', soglasje];
    return null;
  }
  /* merjenje obrazca: začetek in prvi izpolnjen korak vsakega obveznega polja (vrednosti se ne pošiljajo) */
  var started = false, stepped = {};
  form.addEventListener('focusin', function () { if (!started) { started = true; track('lead_form_start', {}); } });
  ['#f-firma', '#f-kraj', '#f-panoga', '#f-kontakt', '#f-soglasje'].forEach(function (sel) {
    var el = $(sel); if (!el) return;
    el.addEventListener('change', function () {
      var ok = el.type === 'checkbox' ? el.checked : !!el.value.trim();
      if (ok && !stepped[sel]) { stepped[sel] = 1; track('lead_form_step', { field: el.name, step: Object.keys(stepped).length }); }
    });
  });
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
        var lp = { package: payload.paket || 'brez', segment: payload.segment || 'brez', connection: payload.povezava };
        track('Lead', lp); track('generate_lead', lp);
        setTimeout(function () { location.href = '/podjetja/hvala/'; }, 400);
      })
      .catch(function (err) {
        sending = false; btn.disabled = false; btn.textContent = 'Pripravite mi ponudbo';
        var m = err && err.message && err.message !== 'napaka' && err.message !== 'Failed to fetch' ? err.message : 'Povpraševanja ni bilo mogoče poslati.';
        showErr(m + ' Poskusite znova ali pišite na ' + (CFG.email || 'naš e-naslov') + '.');
      });
  });
})();
