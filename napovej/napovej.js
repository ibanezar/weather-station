/*
 * napovej/napovej.js — »Prehiti model«: vsak dan napoveš jutrišnjo najvišjo in
 * najnižjo temperaturo ter dež za Rečico ob Savinji, naslednji dan pa te oceni
 * meritev postaje IREICA1 — po ISTEM pravilu kot ARSO, Open-Meteo, MTR in
 * ECMWF AIFS na semaforju /tocnost-napovedi/.
 *
 * Zakaj je to več kot kviz: nasprotniki niso izmišljeni. So iste napovedi, ki
 * jih tools/verify_forecasts.py vsak večer zabeleži kot čakajoče in jih naslednji
 * dan oceni. Igra jih samo pokaže še tebi in tvojo oceno zloži zraven, na isto
 * tabelo. Zato je »premagal sem Open-Meteo« tu preverljiva trditev in ne občutek.
 *
 * ROČNO pisana, samostojna datoteka (ni generirana). Stran /napovej/ ne nalaga
 * app.js — isto načelo kot igra/igra.js in meteogasilec/gasilec.js.
 *
 * TA DATOTEKA KROGA NE SESTAVLJA. Krog dneva (tarčni datum, napovedi modelov,
 * namigi, razrešeni dnevi) v celoti pripravi tools/generate_napovej_page.py in
 * ga zapiše vdelanega v HTML (#np-krog) ter v /napovej/krog.json. Razlog je isti
 * kot pri igri /igra/: modelski teki se čez dan menjajo, zato bi klic iz
 * brskalnika ob 7:00 in ob 20:00 dal drugačne nasprotnike, deljeni rezultati pa
 * ne bi bili primerljivi.
 *
 * NIČESAR NE SKRIVA. Napovedi modelov so v isti datoteki, ki jo naloži brskalnik,
 * in so tako ali tako objavljene drugod po strani. Igra jih pred oddajo samo ne
 * kaže — kdor jih prepiše, ne igra proti modelu, ampak je model. Enako velja za
 * rezultat: vse teče in se hrani v tvojem brskalniku (localStorage), zato ga je
 * mogoče prirediti. Lestvica je tvoja, ne javna; goljufija škodi samo meritvi
 * tvoje lastne veščine.
 *
 * ZGRADBA: spodaj je najprej ČIST MODEL (ocenjevanje, sezonska statistika) brez
 * vsake navezave na DOM, nato prikazni del. Model se izvozi tudi za Node, ker ga
 * preverja tools/test_napovej.mjs — isti pristop kot pri igri /igra/ in pri Horn
 * naklonu v gasilec.js. Novo pravilo ocenjevanja naj gre v model, ne v prikaz.
 */
(function (global) {
  'use strict';

  // ═══════════════════════════════════════════════════════════════════════
  //  MODEL — čisto ocenjevanje, brez DOM.
  // ═══════════════════════════════════════════════════════════════════════

  // Prag mokrega dneva. ISTI kot pri učenju MTR (train_recica_mos.py) in pri
  // Brierjevi oceni v verify_forecasts.py — če ga spremeniš, spremeni tam.
  var MOKER_MM = 0.2;

  // Toleranca za točke: pri tolikšni napaki je kategorija vredna 0 točk.
  // 5 °C ni izbrano na pamet — toliko je bila avgusta 2026 največja dnevna
  // napaka ARSO na semaforju. Napoved, ki se zmoti za več, ni več napoved.
  var TOL_T = 5;
  var TOL_DEZ = 10;   // mm; nad tem je napoved dežja brez vrednosti

  // Tekmovalci. Vrstni red je vrstni red na tabeli; `dez` pove, ali vir sploh
  // napoveduje milimetre — ARSO objavlja besedno napoved brez njih, MTR pa
  // verjetnost padavin (pop), ne količine. Zato glavna ocena teče SAMO po
  // temperaturah: le tako so vsi štirje modeli in igralec na istem merilu.
  var VIRI = [
    { id: 'arso', ime: 'ARSO', dez: false },
    { id: 'open_meteo', ime: 'Open-Meteo', dez: true },
    { id: 'meteorec', ime: 'MTR', dez: false },
    { id: 'aifs', ime: 'ECMWF AIFS', dez: true }
  ];

  function napaka(nap, dej) {
    if (nap === null || nap === undefined || dej === null || dej === undefined) return null;
    return Math.round(Math.abs(nap - dej) * 10) / 10;
  }

  function tocke(err, tol) {
    if (err === null || err === undefined) return null;
    return Math.max(0, Math.round(100 * (1 - err / tol)));
  }

  /* Ali je vir napovedal moker dan? Milimetri, kjer jih vir ima; verjetnost
     (pop >= 0,5) pri MTR. Vrne null, če vir o padavinah ne pove ničesar. */
  function mokro(nap) {
    if (!nap) return null;
    if (nap.dez !== null && nap.dez !== undefined) return nap.dez >= MOKER_MM;
    if (nap.pop !== null && nap.pop !== undefined) return nap.pop >= 0.5;
    return null;
  }

  /* Ocena ene napovedi proti izmerjenemu dnevu.
     nap: {tmax, tmin, dez?, pop?}   dej: {tmax, tmin, dez}
     Glavna ocena (`skupaj`) je povprečje točk obeh temperatur — dež je zraven
     kot ločena mera, ker ga polovica virov ne napoveduje v milimetrih. */
  function oceni(nap, dej) {
    if (!nap || !dej) return null;
    var e = {
      tmax: napaka(nap.tmax, dej.tmax),
      tmin: napaka(nap.tmin, dej.tmin),
      dez: napaka(nap.dez, dej.dez)
    };
    var t = {
      tmax: tocke(e.tmax, TOL_T),
      tmin: tocke(e.tmin, TOL_T),
      dez: tocke(e.dez, TOL_DEZ)
    };
    var temp = [];
    if (t.tmax !== null) temp.push(t.tmax);
    if (t.tmin !== null) temp.push(t.tmin);
    var m = mokro(nap);
    var dejMokro = (dej.dez === null || dej.dez === undefined) ? null : dej.dez >= MOKER_MM;
    return {
      napake: e,
      tocke: t,
      skupaj: temp.length ? Math.round(temp.reduce(function (a, b) { return a + b; }, 0) / temp.length) : null,
      mokro: m,
      zadel_mokro: (m === null || dejMokro === null) ? null : (m === dejMokro)
    };
  }

  /* Lestvica enega razrešenega dne: igralec + vsi modeli, ki so ta dan
     napovedali, urejeni po skupni oceni. Vir brez ocene (manjkajoča napoved)
     na lestvico ne gre — ne sme pristati na dnu, kot da bi se zmotil. */
  function lestvica(dan, vnos) {
    var out = [];
    var dej = dan && dan.dejansko;
    if (!dej) return out;
    if (vnos) {
      var o = oceni(vnos, dej);
      if (o && o.skupaj !== null) out.push({ id: 'ti', ime: 'Ti', jaz: true, nap: vnos, o: o });
    }
    VIRI.forEach(function (v) {
      var nap = (dan.modeli || {})[v.id];
      if (!nap) return;
      var oc = oceni(nap, dej);
      if (oc && oc.skupaj !== null) out.push({ id: v.id, ime: v.ime, jaz: false, nap: nap, o: oc });
    });
    out.sort(function (a, b) { return b.o.skupaj - a.o.skupaj; });
    return out;
  }

  /* Koliko modelov je igralec ta dan premagal (in koliko jih je sploh bilo). */
  function premagani(vrstice) {
    var jaz = null, modeli = 0, pod = 0;
    vrstice.forEach(function (r) { if (r.jaz) jaz = r; else modeli++; });
    if (!jaz) return null;
    vrstice.forEach(function (r) { if (!r.jaz && r.o.skupaj < jaz.o.skupaj) pod++; });
    return { premagal: pod, od: modeli, mesto: vrstice.indexOf(jaz) + 1, skupaj: vrstice.length };
  }

  function povp(a) {
    if (!a.length) return null;
    return Math.round((a.reduce(function (x, y) { return x + y; }, 0) / a.length) * 100) / 100;
  }

  /* Sezonska statistika. KLJUČNO: modele meri SAMO na dnevih, ki jih je igralec
     tudi igral. Primerjava s 50-dnevnim povprečjem modela proti tvojim petim
     dnevom ne bi bila primerjava, ampak dve različni meritvi na isti tabeli. */
  function sezona(razreseni, vnosi) {
    var dnevi = Object.keys(vnosi || {}).filter(function (d) {
      return razreseni && razreseni[d] && razreseni[d].dejansko;
    }).sort();
    var zbir = {};
    function prazno(ime) {
      return { ime: ime, tmax: [], tmin: [], dez: [], skupaj: [], mokro_zadel: 0, mokro_n: 0, n: 0 };
    }
    zbir.ti = prazno('Ti');
    VIRI.forEach(function (v) { zbir[v.id] = prazno(v.ime); });

    var zmage = 0, remiji = 0;
    dnevi.forEach(function (d) {
      var dan = razreseni[d];
      var vrstice = lestvica(dan, vnosi[d]);
      vrstice.forEach(function (r) {
        var z = zbir[r.id];
        if (!z) return;
        z.n++;
        if (r.o.napake.tmax !== null) z.tmax.push(r.o.napake.tmax);
        if (r.o.napake.tmin !== null) z.tmin.push(r.o.napake.tmin);
        if (r.o.napake.dez !== null) z.dez.push(r.o.napake.dez);
        if (r.o.skupaj !== null) z.skupaj.push(r.o.skupaj);
        if (r.o.zadel_mokro !== null) { z.mokro_n++; if (r.o.zadel_mokro) z.mokro_zadel++; }
      });
      var p = premagani(vrstice);
      if (p && p.mesto === 1) zmage++;
      else if (p && p.premagal > 0) remiji++;
    });

    var vrsta = Object.keys(zbir).map(function (id) {
      var z = zbir[id];
      return {
        id: id, ime: z.ime, n: z.n,
        mae_tmax: povp(z.tmax), mae_tmin: povp(z.tmin), mae_dez: povp(z.dez),
        tocke: povp(z.skupaj),
        mokro_delez: z.mokro_n ? Math.round((z.mokro_zadel / z.mokro_n) * 100) : null
      };
    }).filter(function (z) { return z.n > 0; });
    vrsta.sort(function (a, b) { return (b.tocke === null ? -1 : b.tocke) - (a.tocke === null ? -1 : a.tocke); });

    return { dnevi: dnevi, n: dnevi.length, vrstice: vrsta, zmage: zmage, delne: remiji, niz: niz(vnosi) };
  }

  /* Niz zaporednih dni z oddano napovedjo, šteto nazaj od zadnjega oddanega.
     Meri vztrajnost, ne uspeha — zato ne zahteva razrešitve. */
  function niz(vnosi) {
    var d = Object.keys(vnosi || {}).sort();
    if (!d.length) return 0;
    var n = 1;
    for (var i = d.length - 1; i > 0; i--) {
      var a = new Date(d[i] + 'T00:00:00Z').getTime();
      var b = new Date(d[i - 1] + 'T00:00:00Z').getTime();
      if (Math.round((a - b) / 86400000) === 1) n++; else break;
    }
    return n;
  }

  /* Datum + n dni, brez odvisnosti od časovnega pasu (delamo v UTC polnoči). */
  function plusDni(iso, n) {
    var t = new Date(iso + 'T00:00:00Z');
    t.setUTCDate(t.getUTCDate() + n);
    return t.toISOString().slice(0, 10);
  }

  function danesISO(zdaj) {
    var d = zdaj || new Date();
    return [d.getFullYear(),
      String(d.getMonth() + 1).padStart(2, '0'),
      String(d.getDate()).padStart(2, '0')].join('-');
  }

  /* Ali krog še sprejema napoved? Tarča mora biti PRIHODNJI dan: za dan, ki že
     teče (ali je mimo), napoved ni napoved. Ob izpadu dnevnega teka je krog
     zastarel in stran to pove, namesto da bi tiho pobirala napovedi za nazaj. */
  function odprt(krog, zdaj) {
    if (!krog || !krog.tarca) return false;
    return krog.tarca > danesISO(zdaj);
  }

  var Model = {
    MOKER_MM: MOKER_MM, TOL_T: TOL_T, TOL_DEZ: TOL_DEZ, VIRI: VIRI,
    napaka: napaka, tocke: tocke, mokro: mokro, oceni: oceni,
    lestvica: lestvica, premagani: premagani, sezona: sezona, niz: niz,
    plusDni: plusDni, danesISO: danesISO, odprt: odprt
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = Model;
  global.Napovej = Model;

  if (typeof document === 'undefined') return;   // Node: samo model, brez prikaza

  // ═══════════════════════════════════════════════════════════════════════
  //  PRIKAZ
  // ═══════════════════════════════════════════════════════════════════════

  var LS = 'meteorec-napovej-v1';
  var $ = function (id) { return document.getElementById(id); };

  function st(v, d) {
    if (v === null || v === undefined) return '—';
    return v.toFixed(d === undefined ? 1 : d).replace('.', ',');
  }

  /* Slovenska množina: 1 dan, 2 dneva, 3 dnevi, 5 dni. Brez tega piše
     »niz 1 dni«, kar je drobna reč, a je prvo, kar bralec opazi. */
  function mnozina(n, ena, dva, tri, pet) {
    var m = Math.abs(n) % 100;
    if (m === 1) return ena;
    if (m === 2) return dva;
    if (m === 3 || m === 4) return tri;
    return pet;
  }

  function datumSlo(iso) {
    var p = iso.split('-');
    return Number(p[2]) + '. ' + Number(p[1]) + '. ' + p[0];
  }

  /* ── Shramba ────────────────────────────────────────────────────────────
     Oddana napoved se NE prepiše. Enkrat oddana je oddana — sicer bi lahko
     zjutraj, ko je dan že razrešen, popravil včerajšnjo in »premagal« vse. */
  function beri() {
    try {
      var d = JSON.parse(localStorage.getItem(LS) || '{}');
      return (d && typeof d.vnosi === 'object' && d.vnosi) ? d.vnosi : {};
    } catch (e) { return {}; }
  }

  function shrani(datum, vnos) {
    var vsi = beri();
    if (vsi[datum]) return false;              // zaklenjeno, ne dotikamo se
    vsi[datum] = vnos;
    try {
      localStorage.setItem(LS, JSON.stringify({ v: 1, vnosi: vsi }));
    } catch (e) { return false; }
    return true;
  }

  /* ── Krog ───────────────────────────────────────────────────────────────
     Vdelan v HTML; če je krog.json svežji (stran je predpomnjena, datoteka pa
     ne), ga zamenjamo — isti vzorec kot nivo.json pri igri. */
  function vdelanKrog() {
    var el = $('np-krog');
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  var krog = vdelanKrog();

  function osveziKrog() {
    if (!krog) return Promise.resolve();
    return fetch('/napovej/krog.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (nov) {
        if (nov && nov.tarca && (!krog.tarca || nov.tarca > krog.tarca)) krog = nov;
      })
      .catch(function () { /* stran deluje z vdelanim krogom */ });
  }

  /* ── Izris ──────────────────────────────────────────────────────────────── */

  function izrisiNamig() {
    if (!krog || !krog.namig) return;
    var k = krog.namig.klima || {}, v = krog.namig.vceraj || {};
    var pari = [
      ['np-h-tmax', st(k.tmax_med) + ' °C'],
      ['np-h-tmin', st(k.tmin_med) + ' °C'],
      ['np-h-dez', k.dez_delez === null || k.dez_delez === undefined ? '—' : k.dez_delez + ' %'],
      ['np-h-vtmax', st(v.tmax) + ' °C'],
      ['np-h-vtmin', st(v.tmin) + ' °C'],
      ['np-h-vdez', st(v.dez) + ' mm']
    ];
    pari.forEach(function (p) { var el = $(p[0]); if (el) el.textContent = p[1]; });
    var d = $('np-h-datum');
    if (d && v.datum) d.textContent = datumSlo(v.datum);
  }

  function vrsticaLestvice(r, kat) {
    var val, err;
    if (kat === 'tmax') { val = st(r.nap.tmax) + ' °C'; err = r.o.napake.tmax; }
    else { val = st(r.nap.tmin) + ' °C'; err = r.o.napake.tmin; }
    return '<tr' + (r.jaz ? ' class="np-me"' : '') + '><th>' + r.ime + '</th>' +
      '<td>' + val + '</td><td>' + (err === null ? '—' : '±' + st(err)) + '</td></tr>';
  }

  /* Kartica oddaje: pred oddajo obrazec, po oddaji tvoja napoved + nasprotniki. */
  function izrisiOddajo() {
    var box = $('np-play');
    var f = $('np-form'), l = $('np-locked');
    if (!box || !krog || !f || !l) return;   // kartico je morda že prevzelo obvestilo
    var tarca = krog.tarca;
    var vnos = beri()[tarca];

    if (!odprt(krog) && !vnos) {
      box.innerHTML = '<p class="np-note">🟡 Krog za ' + datumSlo(tarca) + ' je zaključen, ' +
        'nov pa še ni bil objavljen. Napovedi za dan, ki že teče, igra ne sprejema — ' +
        'poskusi znova, ko se stran zjutraj osveži.</p>';
      return;
    }
    if (!vnos) {
      f.hidden = false;
      l.hidden = true;
      return;
    }

    f.hidden = true;
    l.hidden = false;

    var modeli = VIRI.map(function (v) {
      var m = (krog.modeli || {})[v.id];
      if (!m) return '';
      var dez = m.dez !== null && m.dez !== undefined ? st(m.dez) + ' mm'
        : (m.pop !== null && m.pop !== undefined ? Math.round(m.pop * 100) + ' % možnost' : '—');
      return '<tr><th>' + v.ime + '</th><td>' + st(m.tmax) + ' °C</td><td>' + st(m.tmin) +
        ' °C</td><td>' + dez + '</td></tr>';
    }).join('');

    l.innerHTML =
      '<p class="np-kicker">Tvoja napoved za ' + datumSlo(tarca) + ' je zaklenjena</p>' +
      '<table class="np-table np-wide"><tr><th></th><th>Najvišja</th><th>Najnižja</th><th>Dež</th></tr>' +
      '<tr class="np-me"><th>Ti</th><td>' + st(vnos.tmax) + ' °C</td><td>' + st(vnos.tmin) +
      ' °C</td><td>' + st(vnos.dez) + ' mm</td></tr>' + modeli + '</table>' +
      '<p class="np-note">Tako so se odločili modeli. Jutri zjutraj, ko postaja izmeri ' +
      'dejanski dan, te ta stran oceni po istem pravilu kot njih.</p>';
  }

  /* Zadnji razrešeni dan, ki ga je igralec igral — »kako sem se odrezal«. */
  function izrisiIzid() {
    var box = $('np-result');
    if (!box || !krog) return;
    var vnosi = beri(), raz = krog.razreseni || {};
    var dnevi = Object.keys(vnosi).filter(function (d) { return raz[d] && raz[d].dejansko; }).sort();
    if (!dnevi.length) { box.hidden = true; return; }
    var d = dnevi[dnevi.length - 1];
    var dan = raz[d], vrstice = lestvica(dan, vnosi[d]), p = premagani(vrstice);
    if (!p) { box.hidden = true; return; }
    var dej = dan.dejansko;

    var naslov = p.mesto === 1
      ? '🏆 ' + datumSlo(d) + ': premagal si vse modele'
      : (p.premagal > 0
        ? '✅ ' + datumSlo(d) + ': premagal si ' + p.premagal + ' od ' + p.od + ' modelov'
        : '📉 ' + datumSlo(d) + ': tokrat so bili modeli boljši');

    box.hidden = false;
    box.innerHTML =
      '<h2 class="np-h2">' + naslov + '</h2>' +
      '<p class="np-note">Postaja je izmerila <strong>' + st(dej.tmax) + ' °C</strong> / <strong>' +
      st(dej.tmin) + ' °C</strong>, padavine ' + st(dej.dez) + ' mm.</p>' +
      '<div class="np-cols">' +
      '<div><h3>Najvišja</h3><table class="np-table">' +
      vrstice.slice().sort(function (a, b) {
        return (a.o.napake.tmax === null ? 99 : a.o.napake.tmax) - (b.o.napake.tmax === null ? 99 : b.o.napake.tmax);
      }).map(function (r) { return vrsticaLestvice(r, 'tmax'); }).join('') + '</table></div>' +
      '<div><h3>Najnižja</h3><table class="np-table">' +
      vrstice.slice().sort(function (a, b) {
        return (a.o.napake.tmin === null ? 99 : a.o.napake.tmin) - (b.o.napake.tmin === null ? 99 : b.o.napake.tmin);
      }).map(function (r) { return vrsticaLestvice(r, 'tmin'); }).join('') + '</table></div>' +
      '</div>' +
      '<p class="np-share-row"><button type="button" class="np-btn np-ghost" id="np-share">Deli rezultat</button>' +
      '<span id="np-share-msg" class="np-note"></span></p>';

    var btn = $('np-share');
    if (btn) btn.addEventListener('click', function () { deli(d, vrstice, p); });
  }

  function deli(d, vrstice, p) {
    var jaz = vrstice.filter(function (r) { return r.jaz; })[0];
    var vrstic = vrstice.map(function (r) {
      return (r.jaz ? '👤 ' : '🤖 ') + r.ime + ' ' + r.o.skupaj;
    }).join('\n');
    var txt = 'Prehiti model · ' + datumSlo(d) + '\n' +
      'Moja napoved: ' + st(jaz.nap.tmax) + ' / ' + st(jaz.nap.tmin) + ' °C\n' +
      vrstic + '\n' +
      p.mesto + '. mesto od ' + p.skupaj + '\n' +
      'https://meteorec.si/napovej/';
    if (navigator.share) {
      navigator.share({ text: txt }).catch(function () { });
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(txt).then(function () {
        var m = $('np-share-msg');
        if (m) m.textContent = 'Rezultat je kopiran.';
      }).catch(function () { });
    }
  }

  function izrisiSezono() {
    var box = $('np-season');
    if (!box || !krog) return;
    var s = sezona(krog.razreseni || {}, beri());
    if (!s.n) { box.hidden = true; return; }
    var vrstice = s.vrstice.map(function (z) {
      return '<tr' + (z.id === 'ti' ? ' class="np-me"' : '') + '><th>' + z.ime + '</th>' +
        '<td>' + st(z.tocke, 0) + '</td>' +
        '<td>±' + st(z.mae_tmax) + '</td>' +
        '<td>±' + st(z.mae_tmin) + '</td>' +
        '<td>' + (z.mokro_delez === null ? '—' : z.mokro_delez + ' %') + '</td>' +
        '<td>' + z.n + '</td></tr>';
    }).join('');
    box.hidden = false;
    box.innerHTML =
      '<h2 class="np-h2">Tvoja sezona</h2>' +
      '<p class="np-note">' + s.n + ' ' +
      mnozina(s.n, 'razrešena napoved', 'razrešeni napovedi', 'razrešene napovedi', 'razrešenih napovedi') +
      ' · ' + s.zmage + '× prvo mesto · trenutni niz ' + s.niz + ' ' +
      mnozina(s.niz, 'dan', 'dneva', 'dnevi', 'dni') + '. Modeli so tu merjeni ' +
      '<strong>samo na dnevih, ki si jih igral</strong> — drugače primerjava ne bi bila poštena.</p>' +
      '<table class="np-table np-wide"><tr><th></th><th>Točke</th><th>Najvišja</th><th>Najnižja</th>' +
      '<th>Mokro/suho</th><th>Dni</th></tr>' + vrstice + '</table>' +
      '<p class="np-note">Točke: 100 pomeni popolno napoved, 0 pomeni zgrešeno za 5 °C ali več; ' +
      'stolpca s temperaturama sta povprečni absolutni napaki v °C. »Mokro/suho« je delež dni, ' +
      'ko je vir pravilno napovedal, ali bo dneva vsaj ' + st(MOKER_MM) + ' mm dežja.</p>';
  }

  function izrisi() {
    izrisiNamig();
    izrisiOddajo();
    izrisiIzid();
    izrisiSezono();
  }

  /* ── Oddaja ─────────────────────────────────────────────────────────────── */

  function stevilo(el, min, max) {
    var v = parseFloat(String(el.value).replace(',', '.'));
    if (!isFinite(v) || v < min || v > max) return null;
    return Math.round(v * 10) / 10;
  }

  function oddaj(e) {
    e.preventDefault();
    var msg = $('np-msg');
    if (!krog || !odprt(krog)) {
      msg.textContent = 'Krog ni odprt — stran se osveži vsako jutro.';
      return;
    }
    var tmax = stevilo($('np-tmax'), -30, 45);
    var tmin = stevilo($('np-tmin'), -35, 35);
    var dez = stevilo($('np-dez'), 0, 200);
    if (tmax === null || tmin === null || dez === null) {
      msg.textContent = 'Vpiši vse tri vrednosti (najvišja −30 do 45 °C, najnižja −35 do 35 °C, dež 0–200 mm).';
      return;
    }
    if (tmin > tmax) {
      msg.textContent = 'Najnižja temperatura ne more biti višja od najvišje.';
      return;
    }
    if (!shrani(krog.tarca, { tmax: tmax, tmin: tmin, dez: dez, ob: new Date().toISOString() })) {
      msg.textContent = 'Napoved za ta dan je že oddana.';
    }
    izrisi();
  }

  function poveziDrsnike() {
    [['np-tmax', 'np-tmax-r'], ['np-tmin', 'np-tmin-r'], ['np-dez', 'np-dez-r']].forEach(function (p) {
      var num = $(p[0]), rng = $(p[1]);
      if (!num || !rng) return;
      rng.addEventListener('input', function () { num.value = rng.value; });
      num.addEventListener('input', function () {
        var v = parseFloat(String(num.value).replace(',', '.'));
        if (isFinite(v)) rng.value = v;
      });
    });
  }

  function init() {
    if (!krog) return;
    poveziDrsnike();
    var f = $('np-form');
    if (f) f.addEventListener('submit', oddaj);
    izrisi();
    osveziKrog().then(izrisi);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})(typeof globalThis !== 'undefined' ? globalThis : this);
