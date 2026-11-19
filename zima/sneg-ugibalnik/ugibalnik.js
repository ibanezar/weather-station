/*
 * zima/sneg-ugibalnik/ugibalnik.js — »Kdaj bo prvi sneg v dolini?« in »Kdaj bo prva zmrzal?« (ROČNO pisana datoteka, ni generirana).
 * MODEL (brez DOM-a; izvožen za Node, tools/test_sneg.mjs in tools/test_zmrzal_ugibalnik.mjs): dayDiff, ljDate, validGuesses, ranking,
 * median, weekBins, cfgFrom. PRIKAZ: obrazec, lastni ugib, statistika, lestvica. Podatki: GET/POST <prefix>/ugibanja(e) (worker.js),
 * razrešitev iz data/<igra>-ugibalnik.json (pišeta tools/sneg_ugibalnik_resolve.py in tools/zmrzal_ugibalnik_resolve.py iz novosti.json).
 *
 * Isto datoteko nalaga tudi /ugibalnik-zmrzal/ (nastavitve so atributi data-* na #ug-app; brez njih veljajo snežne): ena kopija
 * pravil, da se igri ne razideta.
 * Pravilo: zmaga ugib, ki je najbližje datumu dogodka (sneg: prva snežna odeja ≥ 1 cm na ARSO postaji Gornji Grad; zmrzal: prva
 * najnižja temperatura ≤ 0 °C na IREICA1 od 1. 9.); pri izenačenju prej oddan ugib. Ugibi, oddani po dogodku (lokalni datum oddaje
 * ≥ datum dogodka), se ne štejejo.
 */
(function (root) {
  'use strict';
  var DAY = 86400000;

  function dayDiff(a, b) {                       // razlika v dneh med ISO datumoma (b − a), obe v UTC polnoči
    return Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / DAY);
  }
  function ljDate(iso) {                         // ISO časovni žig → lokalni datum Europe/Ljubljana (YYYY-MM-DD)
    return new Date(iso).toLocaleDateString('sv-SE', { timeZone: 'Europe/Ljubljana' });
  }
  function addDays(d, n) { return new Date(Date.parse(d + 'T00:00:00Z') + n * DAY).toISOString().slice(0, 10); }

  // ugibi: [[datum, ime, ts], ...]; resolved: 'YYYY-MM-DD' ali null
  function validGuesses(ugibi, resolved) {
    return ugibi.filter(function (g) {
      if (!resolved) return true;
      return ljDate(g[2]) < resolved;
    });
  }
  function ranking(ugibi, resolved) {
    if (!resolved) return [];
    return validGuesses(ugibi, resolved).map(function (g) {
      return { datum: g[0], ime: g[1] || '', ts: g[2], razlika: Math.abs(dayDiff(resolved, g[0])), pred: dayDiff(resolved, g[0]) };
    }).sort(function (a, b) { return a.razlika - b.razlika || (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0); });
  }
  function median(dates) {
    if (!dates.length) return null;
    var s = dates.slice().sort();
    return s.length % 2 ? s[(s.length - 1) / 2] : addDays(s[s.length / 2 - 1], Math.round(dayDiff(s[s.length / 2 - 1], s[s.length / 2]) / 2));
  }
  function mondayOf(d) {                         // ponedeljek tedna, v katerem je datum
    var wd = new Date(Date.parse(d + 'T00:00:00Z')).getUTCDay();   // 0 = nedelja
    return addDays(d, -((wd + 6) % 7));
  }
  function weekBins(dates) {                     // [{od, n}] po tednih, brez lukenj med prvim in zadnjim
    if (!dates.length) return [];
    var cnt = {};
    dates.forEach(function (d) { var m = mondayOf(d); cnt[m] = (cnt[m] || 0) + 1; });
    var keys = Object.keys(cnt).sort(), out = [];
    for (var m = keys[0]; m <= keys[keys.length - 1]; m = addDays(m, 7)) out.push({ od: m, n: cnt[m] || 0 });
    return out;
  }
  function fmt(d) { var p = d.split('-'); return parseInt(p[2], 10) + '. ' + parseInt(p[1], 10) + '.'; }
  function fmtLong(d) {
    var M = ['', 'januarja', 'februarja', 'marca', 'aprila', 'maja', 'junija', 'julija', 'avgusta', 'septembra', 'oktobra', 'novembra', 'decembra'];
    var p = d.split('-'); return parseInt(p[2], 10) + '. ' + M[parseInt(p[1], 10)] + ' ' + p[0];
  }
  function dnevi(n) {                            // slovnica: 1 dan, 2 dneva, 3–4 dni, 5+ dni
    var a = Math.abs(n);
    return a + (a % 100 === 1 ? ' dan' : a % 100 === 2 ? ' dneva' : ' dni');
  }

  // Besedila (privzeto: sneg). {d} = datum; {url} = naslov strani. Drugo igro prepiše JSON v data-txt na #ug-app.
  var TXT = {
    share: 'Moj ugib za prvi sneg v Gornjem Gradu: {d}. Kdaj bo po vašem? {url}',
    label: 'Datum, ko bo v Gornjem Gradu prvič ležal vsaj 1 cm snega',
    closed: 'Ugibanje je zaprto: prvi sneg je že padel.',
    closedEnd: 'Ugibanje je zaprto.',
    locked: ' Ugib je zaklenjen. Lestvica bo znana, ko ARSO v Gornjem Gradu izmeri 1 cm snega.',
    mine: 'Vaš ugib: {d}.',
    result: 'Prvi sneg je padel {d}.',
    winner: ' Zmagal je ugib z najmanjšo razliko v dneh.',
    late: 'Vaš ugib je bil oddan po prvem snegu in se ne šteje.',
    none: 'Prvega snega (≥ 1 cm) v Gornjem Gradu letos še ni zaznati.',
    state: 'Prvi sneg: {d}.',
    noEvent: 'Letos ni bilo snega do konca ugibanja.'
  };
  function fill(t, d, url) { return String(t).replace('{d}', d || '').replace('{url}', url || ''); }

  // Nastavitve igre iz atributov (get(ime) → niz ali null) in današnjega lokalnega datuma. Brez atributov: snežni ugibalnik.
  //   data-season-month: mesec začetka sezone (sneg 7 = julij, zmrzal 8 = avgust); data-sezona: fiksna sezona (sneg 2026); sicer iz datuma
  //   data-max-md / data-max-next: zadnji dan ugibanja (sneg 30. 4. NASLEDNJEGA leta, zmrzal 31. 12. istega); data-min-md: najzgodnejši datum
  function cfgFrom(get, today) {
    var sm = parseInt(get('data-season-month') || '7', 10) || 7;
    var y = parseInt(today.slice(0, 4), 10), m = parseInt(today.slice(5, 7), 10);
    var sez = parseInt(get('data-sezona'), 10); if (isNaN(sez)) sez = m >= sm ? y : y - 1;
    var cfg = {
      prefix: get('data-prefix') || '/sneg', key: get('data-key') || 'prvi_sneg', idKey: get('data-id-key') || 'wx-sneg-ugib-id',
      mojKey: get('data-moj-key') || 'wx-sneg-ugib-moj', sezona: sez,
      maxDate: (get('data-max-next') === '0' ? sez : sez + 1) + '-' + (get('data-max-md') || '04-30'), minDate: today, txt: {}
    };
    var minMd = get('data-min-md');
    if (minMd && (sez + '-' + minMd) > today) cfg.minDate = sez + '-' + minMd;
    cfg.open = today <= cfg.maxDate;             // okno ugibanja še ni mimo (ali je sezona že odprta)
    for (var k in TXT) cfg.txt[k] = TXT[k];
    try { var o = JSON.parse(get('data-txt') || '{}'); for (var k2 in o) cfg.txt[k2] = o[k2]; } catch (e) { /* privzeta besedila */ }
    return cfg;
  }

  var model = { dayDiff: dayDiff, ljDate: ljDate, addDays: addDays, validGuesses: validGuesses, ranking: ranking, median: median,
    mondayOf: mondayOf, weekBins: weekBins, fmt: fmt, fmtLong: fmtLong, dnevi: dnevi, cfgFrom: cfgFrom, fill: fill, TXT: TXT };
  if (typeof module !== 'undefined' && module.exports) { module.exports = model; }
  if (typeof document === 'undefined') return;

  // ───────────────────────── prikaz ─────────────────────────
  var app = document.getElementById('ug-app');
  if (!app) return;
  var API = app.getAttribute('data-api'), STATE = app.getAttribute('data-state');
  var $ = function (id) { return document.getElementById(id); };
  function ls(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } return null; }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  var today = ljDate(new Date().toISOString());
  var C = cfgFrom(function (n) { return app.getAttribute(n); }, today), T = C.txt, SEZONA = C.sezona;

  var pid = ls(C.idKey);
  if (!pid || !/^[A-Za-z0-9_-]{8,40}$/.test(pid)) {
    pid = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : ('p' + Math.random().toString(36).slice(2) + Date.now().toString(36));
    ls(C.idKey, pid);
  }

  function shareText(datum) { return fill(T.share, fmt(datum), location.href.split('#')[0]); }
  function share(datum) {
    var t = shareText(datum);
    if (navigator.share) { navigator.share({ text: t }).catch(function () {}); return; }
    if (navigator.clipboard) { navigator.clipboard.writeText(t).then(function () { $('ug-msg').textContent = 'Besedilo je kopirano.'; }); }
  }

  function renderStats(valid) {
    var box = $('ug-stat'); box.innerHTML = '';
    if (!valid.length) { box.appendChild(el('p', 'archive-intro', 'Ugibov še ni. Bodite prvi.')); return; }
    var dates = valid.map(function (g) { return g[0]; });
    var bins = weekBins(dates), mx = Math.max.apply(null, bins.map(function (b) { return b.n; }));
    box.appendChild(el('p', 'archive-intro', 'Ugibov: ' + valid.length + ' · srednji ugib (mediana): ' + fmt(median(dates))));
    var chart = el('div', 'ug-bars'); chart.setAttribute('role', 'img');
    chart.setAttribute('aria-label', 'Število ugibov po tednih: ' + bins.map(function (b) { return 'teden od ' + fmt(b.od) + ': ' + b.n; }).join(', '));
    bins.forEach(function (b) {
      var row = el('div', 'ug-bar');
      row.appendChild(el('span', 'ug-bar-l', fmt(b.od)));
      var track = el('span', 'ug-bar-t'), fill_ = el('i'); fill_.style.width = (mx ? Math.round(100 * b.n / mx) : 0) + '%'; track.appendChild(fill_);
      row.appendChild(track); row.appendChild(el('span', 'ug-bar-n', String(b.n)));
      chart.appendChild(row);
    });
    box.appendChild(chart);
    box.appendChild(el('p', 'vs-note', 'Stolpci so tedni (od ponedeljka), število je ugibov za ta teden.'));
  }

  function renderResult(all, resolved, moj) {
    var box = $('ug-rang'); box.innerHTML = '';
    var r = ranking(all, resolved);
    var h = el('p', 'archive-intro'); h.appendChild(el('b', null, fill(T.result, fmtLong(resolved))));
    h.appendChild(document.createTextNode(T.winner)); box.appendChild(h);
    if (!r.length) { box.appendChild(el('p', 'archive-intro', 'Pravočasnih ugibov ni bilo.')); return; }
    var ol = el('ol', 'ug-rank');
    r.slice(0, 10).forEach(function (g) {
      var li = el('li');
      li.appendChild(el('b', null, (g.ime || 'Anonimno')));
      li.appendChild(document.createTextNode(' · ugib ' + fmt(g.datum) + ' · ' + (g.razlika === 0 ? 'zadetek v dan natančno' : 'razlika ' + dnevi(g.razlika))));
      ol.appendChild(li);
    });
    box.appendChild(ol);
    if (moj) {
      var idx = r.findIndex(function (g) { return g.ts === moj.ts; });
      box.appendChild(el('p', 'archive-intro', idx >= 0 ? 'Vaše mesto: ' + (idx + 1) + '. od ' + r.length + ' (ugib ' + fmt(moj.datum) + ').' : T.late));
    }
  }

  function renderForm(moj, resolved) {
    var f = $('ug-form'); f.innerHTML = '';
    if (resolved) { f.appendChild(el('p', 'archive-intro', T.closed)); return; }
    if (moj) {
      var p = el('p', 'archive-intro'); p.appendChild(el('b', null, fill(T.mine, fmtLong(moj.datum))));
      p.appendChild(document.createTextNode(T.locked));
      f.appendChild(p);
      var b = el('button', 'mtn-avk-link', 'Povejte naprej'); b.type = 'button'; b.addEventListener('click', function () { share(moj.datum); }); f.appendChild(b);
      return;
    }
    if (!C.open) { f.appendChild(el('p', 'archive-intro', T.closedEnd)); return; }
    var form = el('form', 'ug-form');
    var l1 = el('label', null, T.label);
    var inp = el('input'); inp.type = 'date'; inp.id = 'ug-datum'; inp.min = C.minDate; inp.max = C.maxDate; inp.required = true; l1.appendChild(inp);
    var l2 = el('label', null, 'Vzdevek (neobvezno)'); var nm = el('input'); nm.type = 'text'; nm.maxLength = 20; nm.id = 'ug-ime'; nm.autocomplete = 'off'; l2.appendChild(nm);
    var hp = el('input'); hp.type = 'text'; hp.id = 'ug-website'; hp.tabIndex = -1; hp.autocomplete = 'off'; hp.setAttribute('aria-hidden', 'true'); hp.style.cssText = 'position:absolute;left:-9999px';
    var btn = el('button', 'mtn-avk-link', 'Oddaj ugib'); btn.type = 'submit';
    form.appendChild(l1); form.appendChild(l2); form.appendChild(hp); form.appendChild(btn);
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      if (!inp.value) { $('ug-msg').textContent = 'Izberite datum.'; return; }
      btn.disabled = true; $('ug-msg').textContent = 'Pošiljam …';
      fetch(API + C.prefix + '/ugibanje', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ igralec: pid, datum: inp.value, ime: nm.value.trim(), website: hp.value }) })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          btn.disabled = false;
          if (!res.ok) { $('ug-msg').textContent = (res.d && res.d.error) || 'Napaka pri pošiljanju.'; if (res.d && res.d.datum) load(); return; }
          ls(C.mojKey, res.d.datum); $('ug-msg').textContent = 'Hvala, ugib je zabeležen.'; load();
        })
        .catch(function () { btn.disabled = false; $('ug-msg').textContent = 'Napaka pri pošiljanju, poskusite znova.'; });
    });
    f.appendChild(form);
  }

  function load() {
    var st = fetch(STATE + '?t=' + Date.now(), { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    var gs = fetch(API + C.prefix + '/ugibanja?igralec=' + encodeURIComponent(pid)).then(function (r) { return r.json(); });
    Promise.all([st, gs]).then(function (v) {
      var state = v[0], d = v[1], resolved = state && state.sezona === SEZONA ? state[C.key] : null;
      var all = d.ugibi || [], moj = d.moj || null;
      renderForm(moj, resolved);
      renderStats(validGuesses(all, resolved));
      if (resolved) renderResult(all, resolved, moj); else $('ug-rang').innerHTML = '';
      $('ug-stanje').textContent = resolved ? fill(T.state, fmtLong(resolved)) : (C.open ? T.none : T.noEvent);
    }).catch(function () {
      // Napaka vira: nobenega večnega »Nalagam …«; sporočilo in ponoven poskus (19. 11. 2026)
      $('ug-stanje').textContent = 'Podatkov trenutno ni mogoče naložiti.';
      var s = $('ug-stat'); s.innerHTML = '';
      var b = el('button', 'mtn-avk-link', 'Poskusi znova'); b.type = 'button';
      b.addEventListener('click', function () { $('ug-stanje').textContent = 'Nalagam …'; s.innerHTML = ''; load(); });
      s.appendChild(el('p', 'archive-intro', 'Podatkov ni bilo mogoče naložiti.')); s.appendChild(b);
    });
  }
  load();
})(typeof window !== 'undefined' ? window : this);
