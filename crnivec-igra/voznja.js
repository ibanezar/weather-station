/*
 * crnivec-igra/voznja.js — »Čez Črnivec«: arkadna vožnja po R1-225 od
 * Stahovice čez prelaz (902 m) do Gornjega Grada. Igra na crnivec.si/igra/.
 *
 * NIVO SE VSAK DAN SESTAVI IZ PRAVIH RAZMER. Vozišče po odsekih (suho,
 * mokro, led, sneg), megla v dolini in sunki na vrhu pridejo iz istega
 * izračuna kot glavna stran crnivec.si (termin »Na poti v službo«, ocena
 * poledice black_ice_category, meritev DRSI) — sestavi ga
 * tools/generate_crnivec_igra.py in ga vdela v stran (#cv-level) ter zapiše
 * v /igra/nivo.json. TA DATOTEKA NIVOJA NE RAČUNA — isto načelo kot Termika
 * (igra/igra.js): isti dan, isti nivo za vse, sicer so časi na lestvici
 * neprimerljivi.
 *
 * Bistvo igre je ena odločitev: VERIGE. Na startu jih nadeneš brez kazni,
 * med vožnjo pa samo ustavljen in s kaznijo (VERIGE_S). Z verigami te led in
 * sneg držita, na suhem pa ropotaš počasi (največ 50 km/h). Kdor na suhem
 * dnevu vozi z verigami, izgubi; kdor na ledu brez njih, konča v jarku.
 *
 * ROČNO pisana datoteka (ni generirana). Izvorna je v crnivec-igra/, na
 * crnivec.si/igra/ jo skopira generator. ZGRADBA: najprej ČIST MODEL (proga,
 * površine, fizika) brez DOM-a, izvožen za Node (tools/test_crnivec_igra.mjs),
 * nato prikazni del. Nova fizika gre v model, ne v prikaz.
 */
(function (global) {
  'use strict';

  // ═══════════════════════════════════════════════════════════════════════
  //  MODEL
  // ═══════════════════════════════════════════════════════════════════════

  // Proga je PRAVA cesta R1-225 iz OpenStreetMap (crnivec-igra/proga.json,
  // sestavi jo enkratni tools/build_crnivec_igra_proga.py): ukrivljenost za
  // vsak meter igre (k) in kilometrina prave ceste (km). Stisnjena je
  // neenakomerno -- ostri ovinki ostanejo skoraj v pravi velikosti, ravnine
  // se stisnejo (glej opombo v skripti). Nastavi jo nastaviProgo(); v
  // brskalniku iz #cv-proga, v testu iz datoteke.
  var PROGA = null, KM = null;
  var L = 0;                  // dolžina proge v metrih igre
  var L_REAL_KM = 0;          // dolžina prave ceste (km)
  var HALF = 3.4;             // pol širine vozišča (m)
  var OFF = HALF + 0.9;       // dlje od sredine = v jarku
  var G = 9.81;
  var VMAX = 25;              // 90 km/h
  var VMAX_VERIGE = 13.9;     // 50 km/h
  var ACC = 4.2, BRAKE = 8.5;
  // Največja ukrivljenost, ki jo da volan (1/m) -- polni zasuk je polmer
  // 10 m, najožja serpentina ima 17 m. Avto zavija SAMO z volanom: prva
  // različica je ukrivljenost ceste prištela sama (in avto še poravnavala s
  // cesto), zato je v ovinek zavil brez igralca (Filip, 28. 9. 2026).
  var KMAX = 0.1;
  var PEN_JAREK = 8;          // s kazni za jarek
  var VERIGE_S = 15;          // s kazni, ko med vožnjo nadeneš ali snameš verige

  // Oprijem (koeficient trenja) po površini. Z verigami je na suhem in
  // mokrem malo slabši (veriga drsi po asfaltu), na ledu in snegu pa bistveno
  // boljši. Vrednosti so arkadne, a v pravem razmerju (suh asfalt ~1, moker
  // ~0,7, utrjen sneg ~0,3-0,4, led ~0,1-0,2).
  var MU = { suho: 1.0, mokro: 0.72, sneg: 0.36, led: 0.17 };
  var MU_VERIGE = { suho: 0.85, mokro: 0.68, sneg: 0.72, led: 0.5 };
  var SURF_CODE = ['suho', 'mokro', 'sneg', 'led'];

  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function hashStr(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }

  function nastaviProgo(p) {
    PROGA = p;
    L = p.k.length - 1;
    L_REAL_KM = p.dolzina_km;
    KM = new Float32Array(p.km);
  }

  // Kilometer prave ceste na metru igre s.
  function kmNa(s) {
    var i = Math.max(0, Math.min(L, Math.floor(s)));
    var f = Math.max(0, Math.min(1, s - i));
    return i < L ? KM[i] + (KM[i + 1] - KM[i]) * f : KM[L];
  }
  // Meter igre, kjer je kilometer km prave ceste (za table, kamne, vrh).
  function sNaKm(km) {
    var lo = 0, hi = L;
    while (hi - lo > 1) { var m = (lo + hi) >> 1; if (KM[m] < km) lo = m; else hi = m; }
    return hi;
  }

  // Ukrivljenost po metrih (k > 0 = levi ovinek) in iz nje središčnica.
  function buildTrack() {
    if (!PROGA) throw new Error('proga ni nastavljena (nastaviProgo)');
    var k = new Float32Array(PROGA.k);
    var x = new Float32Array(L + 1), y = new Float32Array(L + 1), h = new Float32Array(L + 1);
    for (var i = 1; i <= L; i++) {
      h[i] = h[i - 1] + k[i - 1];
      // Smer (-sin h, -cos h) na zaslonu: večji h zavije LEVO, isto kot k > 0
      // in psi > 0 (proti +d) v modelu. Levo od ceste je (-cos h, +sin h).
      x[i] = x[i - 1] - Math.sin(h[i]);
      y[i] = y[i - 1] - Math.cos(h[i]);
    }
    return { L: L, k: k, x: x, y: y, h: h };
  }

  function odsekNa(level, s) {
    var od = (level && level.odseki) || [];
    if (!od.length) return null;
    var km = kmNa(s);
    var i = Math.min(od.length - 1, Math.max(0, Math.floor(km)));
    return od[i];
  }

  // Površina po metrih. Led je v odseku v zaplatah (delež led_delez), ne
  // enakomerno — »ponekod je lahko led« tako res pomeni ponekod. Postavitev
  // zaplat je sejana iz datuma: isti dan je led za vse na istem mestu.
  function buildSurface(level) {
    var surf = new Uint8Array(L + 1);
    var rnd = mulberry32(hashStr('led|' + ((level && level.datum) || '')));
    var CH = 18;                                  // dolžina zaplate (m igre)
    for (var s0 = 0; s0 <= L; s0 += CH) {
      var o = odsekNa(level, s0) || { povrsina: 'suho' };
      var p = o.povrsina || 'suho';
      var r = rnd();
      var code = 0;
      if (p === 'sneg') code = 2;
      else if (p === 'led') code = r < (o.led_delez == null ? 1 : o.led_delez) ? 3 : (o.mokro ? 1 : 0);
      else if (p === 'mokro') code = 1;
      for (var s = s0; s < s0 + CH && s <= L; s++) surf[s] = code;
    }
    return surf;
  }

  function zNa(level, s) {
    var od = (level && level.odseki) || [];
    if (!od.length) return 0;
    var km = Math.max(0, Math.min(L_REAL_KM, kmNa(s)));
    var i = Math.min(od.length - 1, Math.floor(km));
    var a = od[i];
    var f = km - i;
    return a.z_od + (a.z_do - a.z_od) * Math.min(1, f);
  }

  function meglaNa(level, s) {
    var o = odsekNa(level, s);
    return !!(o && o.megla);
  }

  function makeSim(level, opts) {
    var track = (opts && opts.track) || buildTrack();
    return {
      level: level, track: track, surf: buildSurface(level),
      s: 0, d: 0, psi: 0, v: 0, t: 0, pen: 0, jarki: 0, menjave: 0,
      verige: !!(opts && opts.verige), drsi: false, done: false,
      volan: 0, dogodek: null
    };
  }

  function surfAt(sim, s) {
    var i = Math.max(0, Math.min(L, Math.floor(s)));
    return SURF_CODE[sim.surf[i]];
  }
  function muAt(sim, s) {
    var p = surfAt(sim, s);
    return (sim.verige ? MU_VERIGE : MU)[p];
  }
  function kAt(sim, s) {
    var i = Math.max(0, Math.min(L, Math.floor(s)));
    return sim.track.k[i];
  }

  // Sunki na vrhu (samo nad 750 m, samo ob izmerjenih sunkih DRSI).
  // Determinističen potek v času, brez naključja: isti čas, isti sunek.
  function sunek(sim) {
    var g = sim.level && sim.level.sunki_kmh;
    if (!g || g < 30) return 0;
    if (zNa(sim.level, sim.s) < 750) return 0;
    var w = (g - 25) / 3.6 * 0.07;               // m/s bočnega zanosa
    var t = sim.t;
    return w * Math.sin(0.9 * t) * Math.max(0, Math.sin(0.37 * t + 1));
  }

  // En korak fizike. vnos = { plin: 0..1, zavora: 0..1, volan: -1..1 }.
  function step(sim, vnos, dt) {
    if (sim.done) return sim;
    sim.dogodek = null;
    var mu = muAt(sim, sim.s);
    var grip = mu * G;
    var vmax = sim.verige ? VMAX_VERIGE : VMAX;

    // Vzdolžno: pospešek in zaviranje omejuje oprijem (na ledu kolesa
    // spodrsavajo, zavore ne primejo).
    var a = 0;
    if (vnos.zavora > 0) a = -Math.min(BRAKE, grip) * vnos.zavora;
    else if (vnos.plin > 0) a = Math.min(ACC, grip * 0.9) * vnos.plin;
    a -= 0.25 + 0.0016 * sim.v * sim.v;          // upor
    if (sim.v > vmax) a = Math.min(a, -2.5);      // verige: čez 50 ne gre
    sim.v = Math.max(0, sim.v + a * dt);

    // Bočno: vozilo zavija, kolikor obrneš volan, a največ grip / v². Kar
    // se razlikuje od ukrivljenosti ceste k, zasuče avto glede na cesto (psi).
    var k = kAt(sim, sim.s);
    var kWant = vnos.volan * KMAX;
    var kLim = sim.v > 0.5 ? grip / (sim.v * sim.v) : 10;
    var kCar = Math.max(-kLim, Math.min(kLim, kWant));
    sim.drsi = Math.abs(kWant) > kLim + 1e-6 && sim.v > 2;
    sim.psi += sim.v * (kCar - k) * dt;
    sim.psi = Math.max(-1.2, Math.min(1.2, sim.psi));
    sim.d += (sim.v * Math.sin(sim.psi) + sunek(sim)) * dt;
    sim.s += sim.v * Math.cos(sim.psi) * dt;
    sim.t += dt;

    if (Math.abs(sim.d) > OFF) {
      sim.jarki++;
      sim.pen += PEN_JAREK;
      sim.d = 0; sim.psi = 0; sim.v = 0;
      sim.dogodek = 'jarek';
    }
    if (sim.s >= L) { sim.s = L; sim.done = true; sim.dogodek = 'cilj'; }
    return sim;
  }

  // Verige se menjajo samo pri miru. Na startu (s < 1, t == 0) brez kazni.
  function menjajVerige(sim) {
    if (sim.done || sim.v > 0.5) return false;
    sim.verige = !sim.verige;
    if (sim.t > 0 || sim.s > 1) { sim.pen += VERIGE_S; sim.menjave++; }
    sim.v = 0;
    sim.dogodek = sim.verige ? 'verige-na' : 'verige-dol';
    return true;
  }

  function koncniCas(sim) { return Math.round((sim.t + sim.pen) * 10) / 10; }

  // Hitrost, s katero se ovinek pri tem oprijemu še da odpeljati.
  function varnaHitrost(mu, k) {
    return Math.abs(k) < 1e-6 ? Infinity : Math.sqrt(mu * G / Math.abs(k));
  }

  var Model = {
    nastaviProgo: nastaviProgo, kmNa: kmNa, sNaKm: sNaKm,
    get L() { return L; }, get L_REAL_KM() { return L_REAL_KM; }, get PROGA() { return PROGA; },
    HALF: HALF, OFF: OFF, G: G, VMAX: VMAX,
    VMAX_VERIGE: VMAX_VERIGE, MU: MU, MU_VERIGE: MU_VERIGE, PEN_JAREK: PEN_JAREK,
    VERIGE_S: VERIGE_S, BRAKE: BRAKE, KMAX: KMAX,
    buildTrack: buildTrack, buildSurface: buildSurface, makeSim: makeSim, step: step,
    menjajVerige: menjajVerige, koncniCas: koncniCas, surfAt: surfAt, muAt: muAt, kAt: kAt,
    zNa: zNa, meglaNa: meglaNa, sunek: sunek, odsekNa: odsekNa, varnaHitrost: varnaHitrost, mulberry32: mulberry32
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = Model;
  global.VoznjaModel = Model;
  if (typeof document === 'undefined') return;

  // ═══════════════════════════════════════════════════════════════════════
  //  PRIKAZ
  // ═══════════════════════════════════════════════════════════════════════

  var API = 'https://weatherireica1.filip-eremita.workers.dev';
  var LS_IGRALEC = 'crn-igra-igralec', LS_IME = 'crn-igra-ime', LS_BEST = 'crn-igra-best';
  var DT = 1 / 120;
  var PX = 7;                  // pikslov na meter igre (pri širini 360 px)
  var SURF_BARVA = { suho: null, mokro: 'rgba(30,41,59,.45)', sneg: 'rgba(248,250,252,.92)', led: 'rgba(147,197,253,.85)' };
  var SURF_IME = { suho: 'suho', mokro: 'mokro', sneg: 'sneg', led: 'LED' };

  function el(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmtCas(sec) {
    var m = Math.floor(sec / 60), s = sec - m * 60;
    return m + ':' + (s < 10 ? '0' : '') + s.toFixed(1).replace('.', ',');
  }
  function fmt(x, d) { return Number(x).toFixed(d).replace('.', ','); }

  var level = null, track = null, sim = null, ui = { faza: 'start', zadnji: 0, acc: 0, sporocilo: '', sporT: 0 };
  var keys = {}, touch = { plin: 0, zavora: 0, levo: 0, desno: 0 };
  var canvas, ctx, W = 360, H = 480, dpr = 1;
  var drevesa = null, ovinki = [], table = [], profil = null;
  var sledi = [], delci = [], kaplje = [], listi = [], hise = [], kamni = [], temaC = null;
  var S_VRH = 0;              // vrh prelaza na progi (m igre), iz proga.vrh_km
  var PROFIL_Y = 70, PROFIL_H = 34, Z_MIN = 400, Z_MAX = 930;

  function beriNivo() {
    try { return JSON.parse(el('cv-level').textContent); } catch (e) { return null; }
  }

  function resize() {
    var box = canvas.parentNode.getBoundingClientRect();
    W = Math.max(280, Math.round(box.width));
    H = Math.round(Math.min(window.innerHeight * 0.72, W * 1.35));
    dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.height = H + 'px';
    PX = W / 52;
    narisiProfil();
    draw();
  }

  // Pokrajina po višini: ena postavitev za cel dan (seme proge), da se ob
  // ponovni vožnji ne premika. Spodaj travniki z listavci, od ~620 m smrekov
  // gozd (gostejši), ob Stahovici in Gornjem Gradu hiše, vsak km kamen.
  // Snežna odeja (odsek.odeja iz nivoja) pobeli tla in krošnje.
  var Z_GOZD = 620;
  // V naselju: do 300 m od kraja iz OSM (proga.naselja) ali na začetku/koncu.
  function vasNa(km) {
    if (km < 0.6 || km > L_REAL_KM - 0.8) return true;
    var n = (PROGA && PROGA.naselja) || [];
    for (var i = 0; i < n.length; i++) if (Math.abs(n[i].km - km) < 0.3) return true;
    return false;
  }
  function odejaNa(s) {
    var o = odsekNa(level, s);
    return o && o.odeja != null ? !!o.odeja : !!(level && level.odeja_cm >= 1);
  }
  function postaviPokrajino() {
    var rnd = mulberry32(4242), out = [], hs = [];
    for (var s = 0; s < L; s += 5) {
      var z = zNa(level, s), km = kmNa(s), vas = vasNa(km);
      var gozd = z >= Z_GOZD;
      var h = track.h[s];
      for (var j = 0; j < 3; j++) {
        var r0 = rnd(), side = rnd() < 0.5 ? -1 : 1, dist = HALF + 3 + rnd() * 24;
        // Hiša samo ob ravnem delu, sicer jo ovinek »povozi«.
        if (vas && j === 0 && s % 15 === 0 && dist < 18 && Math.abs(track.k[s]) < 1 / 80) {
          hs.push({ s: s, side: side, off: side * (OFF + 7 + rnd() * 7), w: 5 + rnd() * 3, l: 7 + rnd() * 4,
            strop: ['#b45309', '#9a3412', '#7c2d12', '#57534e'][Math.floor(rnd() * 4)] });
          continue;
        }
        if (r0 < (gozd ? 0.25 : vas ? 0.85 : 0.6)) continue;
        var off = side * dist;
        out.push({ x: track.x[s] - Math.cos(h) * off, y: track.y[s] + Math.sin(h) * off,
          r: (gozd ? 1.6 : 1.5) + rnd() * 1.6, s: s, smreka: gozd, sneg: false });
      }
    }
    // Sneg na krošnjah po odsekih (odvisen od nivoja, ne od semena)
    out.forEach(function (d) { d.sneg = odejaNa(d.s); });
    drevesa = out;
    hise = hs.map(function (x) {
      var t = tocka(x.s, x.off);
      return { x: t.x, y: t.y, a: -track.h[x.s], w: x.w, l: x.l, strop: x.strop, s: x.s };
    });
    kamni = [];
    for (var k = 1; k < L_REAL_KM; k++) kamni.push({ s: sNaKm(k), km: k });
  }

  // Barva tal po višini (in snegu): dolina svetlejši travnik, gozd temnejši.
  function tlaBarva(s) {
    if (odejaNa(s)) return '#e2e8f0';
    var z = zNa(level, s);
    if (vasNa(kmNa(s))) return '#6fa82a';
    if (z < Z_GOZD - 60) return '#65a30d';
    if (z < Z_GOZD) return '#4d7c0f';
    return '#3f6212';
  }

  // Točka na progi: s (m igre) in bočni odmik (pozitiven = levo od sredine).
  function tocka(s, off) {
    var i = Math.max(0, Math.min(L, Math.round(s))), h = track.h[i];
    return { x: track.x[i] - Math.cos(h) * off, y: track.y[i] + Math.sin(h) * off };
  }

  // Serpentine in ostri ovinki (polmer pod 30 m): pred njimi opozorilni znak,
  // na zunanji strani odbojna ograja.
  function najdiOvinke() {
    var out = [], s = 0;
    while (s <= L) {
      if (Math.abs(track.k[s]) > 1 / 30) {
        var s0 = s, smer = track.k[s] > 0 ? 1 : -1;
        while (s <= L && Math.abs(track.k[s]) > 1 / 30 && (track.k[s] > 0 ? 1 : -1) === smer) s++;
        if (s - s0 > 10) out.push({ s0: s0, s1: s, smer: smer });
      }
      s++;
    }
    ovinki = out;
    // Table naselij (OSM place ob cesti) malo pred krajem, vrh in cilj.
    table = [{ s: 25, tip: 'kraj', txt: 'Stahovica' }];
    ((PROGA && PROGA.naselja) || []).forEach(function (n) {
      if (n.ime === 'Gornji Grad' || n.km < 0.4) return;
      table.push({ s: sNaKm(Math.max(0, n.km - 0.2)), tip: 'kraj', txt: n.ime });
    });
    table.push({ s: S_VRH, tip: 'vrh', txt: 'ČRNIVEC', sub: '902 m' });
    table.push({ s: L - 30, tip: 'kraj', txt: 'Gornji Grad' });
  }

  // Višinski profil proge, pobarvan po površinah — nariše se enkrat (ob
  // velikosti), v HUD-u se nanj nariše samo pika avta.
  var PROFIL_BARVA = { suho: '#a8a29e', mokro: '#475569', led: '#60a5fa', sneg: '#f8fafc' };
  function profilY(z) { return PROFIL_Y + PROFIL_H - 4 - (z - Z_MIN) / (Z_MAX - Z_MIN) * (PROFIL_H - 8); }
  function narisiProfil() {
    if (!level || !level.odseki) return;
    profil = document.createElement('canvas');
    profil.width = W * dpr; profil.height = (PROFIL_Y + PROFIL_H) * dpr;
    var c = profil.getContext('2d');
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.fillStyle = 'rgba(255,255,255,.9)'; c.strokeStyle = '#111'; c.lineWidth = 2;
    c.beginPath(); c.moveTo(16, PROFIL_Y); c.lineTo(W - 16, PROFIL_Y);
    c.quadraticCurveTo(W - 8, PROFIL_Y, W - 8, PROFIL_Y + 8); c.lineTo(W - 8, PROFIL_Y + PROFIL_H - 8);
    c.quadraticCurveTo(W - 8, PROFIL_Y + PROFIL_H, W - 16, PROFIL_Y + PROFIL_H); c.lineTo(16, PROFIL_Y + PROFIL_H);
    c.quadraticCurveTo(8, PROFIL_Y + PROFIL_H, 8, PROFIL_Y + PROFIL_H - 8); c.lineTo(8, PROFIL_Y + 8);
    c.quadraticCurveTo(8, PROFIL_Y, 16, PROFIL_Y); c.closePath(); c.fill(); c.stroke();
    risiProfil(c, 14, PROFIL_Y, W - 28, PROFIL_H, 1.6);
  }

  // Profil proge s površinami v pravokotnik (x0, y0, w, h) -- za HUD in za
  // sliko rezultata. Višina po isti formuli kot profilY() (zamik 4, rob 8).
  function risiProfil(c, x0, y0, w, h, crta) {
    function px(km) { return x0 + w * km / L_REAL_KM; }
    function py(z) { return y0 + h - 4 - (z - Z_MIN) / (Z_MAX - Z_MIN) * (h - 8); }
    level.odseki.forEach(function (o) {
      var a = px(o.od_km), b = px(Math.min(L_REAL_KM, o.od_km + 1));
      c.fillStyle = PROFIL_BARVA[o.povrsina] || PROFIL_BARVA.suho;
      c.globalAlpha = o.povrsina === 'led' ? 0.45 + 0.55 * (o.led_delez || 0) : 1;
      c.beginPath();
      c.moveTo(a, y0 + h - 3); c.lineTo(a, py(o.z_od)); c.lineTo(b, py(o.z_do));
      c.lineTo(b, y0 + h - 3); c.closePath(); c.fill();
      c.globalAlpha = 1;
      if (o.megla) {
        c.fillStyle = 'rgba(203,213,225,.85)';
        c.fillRect(a, y0 + 3, b - a + 0.5, Math.max(2, Math.min(py(o.z_od), py(o.z_do)) - y0 - 4));
      }
    });
    c.strokeStyle = '#111'; c.lineWidth = crta; c.beginPath();
    level.odseki.forEach(function (o, i) {
      if (!i) c.moveTo(px(o.od_km), py(o.z_od));
      c.lineTo(px(Math.min(L_REAL_KM, o.od_km + 1)), py(o.z_do));
    });
    c.stroke();
  }

  function vnos() {
    var l = keys.ArrowLeft || keys.a || keys.A || touch.levo;
    var r = keys.ArrowRight || keys.d || keys.D || touch.desno;
    var cilj = (l ? 1 : 0) - (r ? 1 : 0);
    // Volan se obrača postopoma (tipke so digitalne), sicer je vožnja trzava.
    // Pri večji hitrosti počasneje (kot pravi volan: pri 90 km/h ga ne
    // zasučeš do konca). Prvotnih 3,5/s je bilo pretrdo (Filip, 28. 9. 2026).
    var rate = cilj === 0 ? 2.4 : 1.8 / (1 + sim.v / 20);
    sim.volan += Math.max(-rate * DT, Math.min(rate * DT, cilj - sim.volan));
    ui.zavora = (keys.ArrowDown || keys.s || keys.S || keys[' '] || touch.zavora) ? 1 : 0;
    return {
      plin: (keys.ArrowUp || keys.w || keys.W || touch.plin) ? 1 : 0,
      zavora: ui.zavora,
      volan: sim.volan
    };
  }

  function loop(ts) {
    if (ui.faza !== 'voznja') return;
    var dtReal = Math.min(0.1, (ts - (ui.zadnji || ts)) / 1000);
    ui.zadnji = ts;
    ui.acc += dtReal;
    var vn = null;
    while (ui.acc >= DT) {
      vn = vnos();
      step(sim, vn, DT);
      ui.acc -= DT;
      if (sim.dogodek === 'jarek') { sporoci('V JARKU! +' + PEN_JAREK + ' s'); ui.shake = 0.45; ui.sledL = null; zvokJarek(); }
      if (!ui.vrh && sim.s >= S_VRH) { ui.vrh = true; sporoci('VRH! 902 m'); }
      if (sim.done) break;
    }
    kamera(dtReal);
    zvokTik(dtReal, vn);
    draw();
    if (sim.done) { konec(); return; }
    requestAnimationFrame(loop);
  }

  // Smer kamere: smer ceste malo pred avtom, zglajena (~0,4 s), da se svet v
  // ovinku zasuče mehko in da se vidi, kam cesta zavije.
  function kamera(dt) {
    var ahead = Math.max(0, Math.min(L, Math.floor(sim.s + 8)));
    var cilj = track.h[ahead];
    if (ui.camH == null) { ui.camH = cilj; return; }
    ui.camH += (cilj - ui.camH) * Math.min(1, dt * 2.5);
    if (ui.shake > 0) ui.shake = Math.max(0, ui.shake - dt);
    ucinki(dt);
  }

  // Lega avta v svetu: središče, smer naprej in desno (enotska vektorja).
  function legaAvta() {
    var si = Math.max(0, Math.min(L, Math.floor(sim.s))), hh = track.h[si];
    var H0 = hh + sim.psi;
    return {
      x: track.x[si] - Math.cos(hh) * sim.d, y: track.y[si] + Math.sin(hh) * sim.d, h: H0,
      fx: -Math.sin(H0), fy: -Math.cos(H0), rx: Math.cos(H0), ry: -Math.sin(H0)
    };
  }

  // Sledi zdrsa, pršec (voda, sneg) in iskrice na ledu. Samo prikaz — na
  // fiziko ne vplivajo.
  function ucinki(dt) {
    var a = legaAvta(), p = surfAt(sim, sim.s);
    var zadaj = [
      { x: a.x - a.fx * 1.45 - a.rx * 0.78, y: a.y - a.fy * 1.45 - a.ry * 0.78 },
      { x: a.x - a.fx * 1.45 + a.rx * 0.78, y: a.y - a.fy * 1.45 + a.ry * 0.78 }
    ];
    var drsa = sim.v > 3 && (sim.drsi || (ui.zavora && p !== 'suho'));
    if (drsa && ui.sledL) {
      for (var k = 0; k < 2; k++) {
        var prej = ui.sledL[k];
        if (Math.abs(prej.x - zadaj[k].x) + Math.abs(prej.y - zadaj[k].y) > 0.25) {
          sledi.push({ x1: prej.x, y1: prej.y, x2: zadaj[k].x, y2: zadaj[k].y, led: p === 'led' || p === 'sneg' });
        }
      }
      if (sledi.length > 700) sledi.splice(0, sledi.length - 700);
    }
    ui.sledL = drsa ? zadaj : null;

    if (sim.v > 5 && (p === 'mokro' || p === 'sneg' || p === 'led')) {
      var n = p === 'led' ? (Math.random() < 0.25 ? 1 : 0) : (Math.random() < Math.min(0.9, sim.v / 25) ? 2 : 0);
      for (var i = 0; i < n; i++) {
        var z = zadaj[i % 2], str = (Math.random() - 0.5) * 2;
        delci.push({
          x: z.x, y: z.y,
          vx: -a.fx * sim.v * 0.25 + a.rx * str * 1.5, vy: -a.fy * sim.v * 0.25 + a.ry * str * 1.5,
          t: 0, life: p === 'led' ? 0.35 : 0.35, r: p === 'led' ? 0.18 : 0.2 + Math.random() * 0.2, p: p
        });
      }
    }
    for (var j = delci.length - 1; j >= 0; j--) {
      var d = delci[j];
      d.t += dt; d.x += d.vx * dt; d.y += d.vy * dt; d.r += dt * 0.8;
      if (d.t > d.life) delci.splice(j, 1);
    }
    if (delci.length > 200) delci.splice(0, delci.length - 200);
    padavine(dt);
    veter(dt);
  }

  // Dež ali sneg na zaslonu, samo v odsekih, kjer v uri nivoja pada. Gostota
  // po količini padavin. Delci so v pikslih zaslona (ne v svetu); vožnja jih
  // pospeši navzdol.
  function novaKaplja(tip, kjerkoli) {
    return { tip: tip, x: Math.random() * (W + 80) - 40, y: kjerkoli ? Math.random() * H : -10 - Math.random() * 40,
      vy: tip === 'sneg' ? 40 + Math.random() * 60 : 650 + Math.random() * 250,
      vx: tip === 'sneg' ? 0 : -70, f: Math.random() * 6.28, r: 1.2 + Math.random() * 1.8 };
  }
  function padavine(dt) {
    var o = odsekNa(level, sim.s), tip = o && o.pada;
    var cilj = tip ? Math.min(170, Math.round(50 + (level.padavine_mm || 0) * 80)) : 0;
    while (kaplje.length < cilj) kaplje.push(novaKaplja(tip, true));
    var hitro = sim.v * PX * 0.9;
    for (var i = kaplje.length - 1; i >= 0; i--) {
      var k = kaplje[i];
      k.f += dt * 2;
      k.y += (k.vy + hitro) * dt;
      k.x += (k.tip === 'sneg' ? Math.sin(k.f) * 25 : k.vx) * dt;
      if (k.y > H + 10 || k.tip !== tip) {
        if (kaplje.length > cilj || k.tip !== tip) kaplje.splice(i, 1);
        else kaplje[i] = novaKaplja(tip, false);
      }
    }
  }

  // Sunek: čez zaslon v smeri vetra nese listje (ali sneg, kadar leži), da je
  // vidno, zakaj avto zanaša. g > 0 potiska proti +d (levo na zaslonu).
  function veter(dt) {
    var g = sunek(sim), sneg = odejaNa(sim.s);
    if (Math.abs(g) > 0.15 && Math.random() < Math.min(1, Math.abs(g) * 1.5)) {
      var smer = g > 0 ? -1 : 1;
      listi.push({ x: smer < 0 ? W + 10 : -10, y: Math.random() * H * 0.9 + 40, vx: smer * (180 + Math.abs(g) * 260),
        vy: (Math.random() - 0.3) * 40, f: Math.random() * 6.28, t: 0,
        barva: sneg ? '#f8fafc' : ['#d97706', '#b45309', '#a16207', '#65a30d'][Math.floor(Math.random() * 4)] });
    }
    for (var i = listi.length - 1; i >= 0; i--) {
      var l = listi[i];
      l.t += dt; l.f += dt * 9; l.x += l.vx * dt; l.y += (l.vy + sim.v * PX * 0.9) * dt;
      if (l.x < -20 || l.x > W + 20 || l.y > H + 20 || l.t > 4) listi.splice(i, 1);
    }
  }

  // ── Zvok (Web Audio, sestavljen sproti, brez datotek) ─────────────────
  // Privzeto izklopljen; izbira se zapomni (LS_ZVOK). Motor po hitrosti,
  // »TAK-TAK« verig po prevoženi poti, cviljenje ob zdrsu, udarec ob jarku.
  var LS_ZVOK = 'crn-igra-zvok';
  var zv = { on: false, ac: null, faza: 0 };
  function zvokPripravi() {
    if (zv.ac) return true;
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return false;
    var ac = zv.ac = new AC();
    zv.master = ac.createGain(); zv.master.gain.value = 0.6; zv.master.connect(ac.destination);
    zv.motor = ac.createOscillator(); zv.motor.type = 'sawtooth'; zv.motor.frequency.value = 45;
    var lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 700;
    zv.motorG = ac.createGain(); zv.motorG.gain.value = 0;
    zv.motor.connect(lp); lp.connect(zv.motorG); zv.motorG.connect(zv.master); zv.motor.start();
    var buf = ac.createBuffer(1, ac.sampleRate, ac.sampleRate), d = buf.getChannelData(0);
    for (var i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    zv.sum = buf;
    var src = ac.createBufferSource(); src.buffer = buf; src.loop = true;
    var bp = ac.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 1900; bp.Q.value = 1.2;
    zv.drsG = ac.createGain(); zv.drsG.gain.value = 0;
    src.connect(bp); bp.connect(zv.drsG); zv.drsG.connect(zv.master); src.start();
    return true;
  }
  function zvokNastavi(on) {
    zv.on = on && zvokPripravi();
    if (zv.ac) { if (zv.on) zv.ac.resume(); else zv.ac.suspend(); }
    try { localStorage.setItem(LS_ZVOK, zv.on ? '1' : '0'); } catch (e) { /* ni usodno */ }
    var b = el('cv-zvok');
    if (b) { b.textContent = zv.on ? '🔊 Zvok vklopljen' : '🔇 Zvok izklopljen'; b.setAttribute('aria-pressed', zv.on ? 'true' : 'false'); }
  }
  function pisk(frek, dolz, tip, glas, kFrek) {
    if (!zv.on || !zv.ac) return;
    var t = zv.ac.currentTime, o = zv.ac.createOscillator(), g = zv.ac.createGain();
    o.type = tip || 'sine'; o.frequency.setValueAtTime(frek, t);
    if (kFrek) o.frequency.exponentialRampToValueAtTime(kFrek, t + dolz);
    g.gain.setValueAtTime(glas || 0.2, t); g.gain.exponentialRampToValueAtTime(0.001, t + dolz);
    o.connect(g); g.connect(zv.master); o.start(t); o.stop(t + dolz + 0.02);
  }
  function sum(dolz, glas, hp) {
    if (!zv.on || !zv.ac) return;
    var t = zv.ac.currentTime, s0 = zv.ac.createBufferSource(), f = zv.ac.createBiquadFilter(), g = zv.ac.createGain();
    s0.buffer = zv.sum; f.type = 'highpass'; f.frequency.value = hp || 2500;
    g.gain.setValueAtTime(glas, t); g.gain.exponentialRampToValueAtTime(0.001, t + dolz);
    s0.connect(f); f.connect(g); g.connect(zv.master); s0.start(t, Math.random() * 0.5); s0.stop(t + dolz + 0.02);
  }
  function zvokTik(dt, vn) {
    if (!zv.on || !zv.ac) return;
    var t = zv.ac.currentTime, vozi = ui.faza === 'voznja';
    zv.motor.frequency.setTargetAtTime(42 + sim.v * 4.2 + (vn && vn.plin ? 12 : 0), t, 0.08);
    zv.motorG.gain.setTargetAtTime(vozi ? 0.05 + (vn && vn.plin ? 0.035 : 0) : 0, t, 0.1);
    zv.drsG.gain.setTargetAtTime(vozi && sim.drsi ? 0.1 : 0, t, 0.05);
    if (vozi && sim.verige && sim.v > 1) {
      zv.faza += dt * sim.v * 0.55;
      if (zv.faza >= 1) { zv.faza -= 1; sum(0.035, 0.22, 3000); }
    }
  }
  function zvokJarek() { pisk(110, 0.35, 'sine', 0.5, 35); sum(0.25, 0.3, 300); }
  function zvokCilj() { pisk(660, 0.18, 'square', 0.08); setTimeout(function () { pisk(880, 0.3, 'square', 0.08); }, 160); }

  function sporoci(t) { ui.sporocilo = t; ui.sporT = 1.6; }

  function draw() {
    if (!ctx || !track) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (!sim) return;
    var odeja = odejaNa(sim.s);

    var si = Math.max(0, Math.min(L, Math.floor(sim.s)));
    var hx = track.x[si], hy = track.y[si], hh = track.h[si];
    var cx = hx - Math.cos(hh) * sim.d, cy = hy + Math.sin(hh) * sim.d;
    var heading = hh + sim.psi;
    // Kamera sledi CESTI (središčnici, gladko), ne avtu: ko obrneš volan, se
    // obrne in premakne avto, okolica ostane (Filip, 28. 9. 2026 -- prej je bil
    // avto vedno pokončen in se je vrtel svet). ui.camH se gladi v kamera().
    var camH = ui.camH == null ? hh : ui.camH;

    var shx = ui.shake > 0 ? (Math.random() - 0.5) * ui.shake * 24 : 0;
    var shy = ui.shake > 0 ? (Math.random() - 0.5) * ui.shake * 24 : 0;
    ctx.fillStyle = tlaBarva(sim.s);
    ctx.fillRect(0, 0, W, H);
    ctx.save();
    svetT(ctx, camH, hx, hy, shx, shy);

    var od = Math.max(0, si - 40), doS = Math.min(L, si + Math.ceil(H / PX) + 30);
    // Hiše (Stahovica, Gornji Grad)
    for (var hI = 0; hI < hise.length; hI++) {
      var hs = hise[hI];
      if (hs.s < od - 30 || hs.s > doS + 30) continue;
      ctx.save(); ctx.translate(hs.x, hs.y); ctx.rotate(hs.a);
      ctx.fillStyle = 'rgba(0,0,0,.25)'; ctx.fillRect(-hs.w / 2 + 0.6, -hs.l / 2 + 0.8, hs.w, hs.l);
      ctx.fillStyle = odejaNa(hs.s) ? '#f1f5f9' : hs.strop; ctx.strokeStyle = '#111'; ctx.lineWidth = 0.22;
      ctx.fillRect(-hs.w / 2, -hs.l / 2, hs.w, hs.l); ctx.strokeRect(-hs.w / 2, -hs.l / 2, hs.w, hs.l);
      ctx.beginPath(); ctx.moveTo(0, -hs.l / 2); ctx.lineTo(0, hs.l / 2); ctx.stroke();
      ctx.restore();
    }
    // Drevesa: listavci (okrogli) spodaj, smreke (zvezdaste) v gozdu
    for (var i = 0; i < drevesa.length; i++) {
      var dv = drevesa[i];
      if (dv.s < od - 30 || dv.s > doS + 30) continue;
      if (dv.smreka) {
        ctx.fillStyle = dv.sneg ? '#64748b' : '#14532d';
        ctx.beginPath();
        for (var kI = 0; kI < 16; kI++) {
          var rr0 = kI % 2 ? dv.r * 0.55 : dv.r, an = kI * Math.PI / 8;
          if (kI) ctx.lineTo(dv.x + Math.cos(an) * rr0, dv.y + Math.sin(an) * rr0);
          else ctx.moveTo(dv.x + rr0, dv.y);
        }
        ctx.closePath(); ctx.fill();
        ctx.fillStyle = dv.sneg ? '#f8fafc' : '#052e16';
        ctx.beginPath(); ctx.arc(dv.x, dv.y, dv.r * (dv.sneg ? 0.45 : 0.22), 0, 6.283); ctx.fill();
      } else {
        ctx.fillStyle = dv.sneg ? '#94a3b8' : '#166534';
        ctx.beginPath(); ctx.arc(dv.x, dv.y, dv.r, 0, 6.283); ctx.fill();
        ctx.fillStyle = dv.sneg ? '#f8fafc' : 'rgba(74,222,128,.35)';
        ctx.beginPath(); ctx.arc(dv.x - dv.r * 0.3, dv.y - dv.r * 0.3, dv.r * 0.45, 0, 6.283); ctx.fill();
      }
    }
    // Bankina
    pot(od, doS);
    ctx.strokeStyle = odeja ? '#f8fafc' : '#a3a3a3';
    ctx.lineWidth = OFF * 2; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.stroke();
    // Asfalt
    ctx.strokeStyle = '#4b5563';
    ctx.lineWidth = HALF * 2;
    ctx.stroke();
    // Površine (mokro, sneg, led) kot plasti čez asfalt
    var a0 = od, cur = sim.surf[od];
    for (var s = od + 1; s <= doS; s++) {
      if (sim.surf[s] !== cur || s === doS) {
        var b = SURF_BARVA[SURF_CODE[cur]];
        if (b) { pot(a0, s); ctx.strokeStyle = b; ctx.lineWidth = HALF * 2 - 0.3; ctx.lineCap = 'butt'; ctx.stroke(); }
        a0 = s; cur = sim.surf[s];
      }
    }
    // Sredinska črta
    pot(od, doS);
    ctx.setLineDash([2.4, 2.4]); ctx.strokeStyle = 'rgba(255,255,255,.8)'; ctx.lineWidth = 0.18; ctx.lineCap = 'butt';
    ctx.stroke(); ctx.setLineDash([]);
    // Sledi zdrsa
    ctx.lineCap = 'round'; ctx.lineWidth = 0.32;
    for (var j = 0; j < sledi.length; j++) {
      var sl = sledi[j];
      ctx.strokeStyle = sl.led ? 'rgba(30,58,138,.35)' : 'rgba(17,17,17,.45)';
      ctx.beginPath(); ctx.moveTo(sl.x1, sl.y1); ctx.lineTo(sl.x2, sl.y2); ctx.stroke();
    }
    // Odbojne ograje na zunanji strani ostrih ovinkov
    for (var o = 0; o < ovinki.length; o++) {
      var ov = ovinki[o];
      if (ov.s1 + 8 < od || ov.s0 - 8 > doS) continue;
      var off = -ov.smer * (OFF + 0.45), a1 = Math.max(0, ov.s0 - 8), b1 = Math.min(L, ov.s1 + 8);
      ctx.beginPath();
      for (var q = a1; q <= b1; q += 2) { var t0 = tocka(q, off); if (q === a1) ctx.moveTo(t0.x, t0.y); else ctx.lineTo(t0.x, t0.y); }
      ctx.lineCap = 'butt'; ctx.strokeStyle = '#111'; ctx.lineWidth = 0.75; ctx.stroke();
      ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 0.4; ctx.stroke();
      ctx.fillStyle = '#111';
      for (var q2 = a1; q2 <= b1; q2 += 4) { var t1 = tocka(q2, off - ov.smer * 0.35); ctx.fillRect(t1.x - 0.15, t1.y - 0.15, 0.3, 0.3); }
    }
    // Opozorilni znaki pred ovinki in table (kraj, vrh)
    for (var o2 = 0; o2 < ovinki.length; o2++) {
      var sz = ovinki[o2].s0 - 32;
      if (sz < od - 10 || sz > doS || sz < 0) continue;
      var tz = tocka(sz, -(OFF + 1.8));
      pokoncno(tz.x, tz.y, camH, function () { znakOvinek(ovinki[o2].smer); });
    }
    for (var kk = 0; kk < kamni.length; kk++) {
      var km0 = kamni[kk];
      if (km0.s < od - 10 || km0.s > doS) continue;
      var tk = tocka(km0.s, -(OFF + 0.9));
      pokoncno(tk.x, tk.y, camH, function () { kamen(km0.km); });
    }
    for (var t = 0; t < table.length; t++) {
      var tb = table[t];
      if (tb.s < od - 10 || tb.s > doS) continue;
      var tt = tocka(tb.s, -(OFF + 3.2));
      pokoncno(tt.x, tt.y, camH, function () { tabla(tb); });
    }
    // Pršec in iskrice
    for (var dI = 0; dI < delci.length; dI++) {
      var dc = delci[dI], al = 1 - dc.t / dc.life;
      ctx.fillStyle = dc.p === 'mokro' ? 'rgba(203,213,225,' + (0.55 * al) + ')'
        : dc.p === 'sneg' ? 'rgba(255,255,255,' + (0.85 * al) + ')' : 'rgba(224,242,254,' + al + ')';
      ctx.beginPath(); ctx.arc(dc.x, dc.y, dc.r, 0, 6.283); ctx.fill();
    }
    // Cilj
    if (doS >= L) {
      var fh = track.h[L];
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.2; ctx.setLineDash([0.8, 0.8]);
      ctx.beginPath();
      ctx.moveTo(track.x[L] - Math.cos(fh) * HALF, track.y[L] + Math.sin(fh) * HALF);
      ctx.lineTo(track.x[L] + Math.cos(fh) * HALF, track.y[L] - Math.sin(fh) * HALF);
      ctx.stroke(); ctx.setLineDash([]);
    }

    // Avto v svetu: na svojem bočnem odmiku, obrnjen v smer vožnje
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(-heading + (sim.drsi ? Math.sin(sim.t * 40) * 0.04 : 0));
    narisiAvto();
    ctx.restore();
    ctx.restore();

    tema(camH, hx, hy, shx, shy);

    // Megla: vidljivost pade na ~vis metrov pred avtom
    if (meglaNa(level, sim.s)) {
      var yCar = H * 0.74, vis = 24 * PX;
      var gr = ctx.createLinearGradient(0, yCar, 0, yCar - vis);
      gr.addColorStop(0, 'rgba(226,232,240,.15)');
      gr.addColorStop(1, 'rgba(226,232,240,.97)');
      ctx.fillStyle = gr; ctx.fillRect(0, yCar - vis, W, vis);
      ctx.fillStyle = 'rgba(226,232,240,.97)'; ctx.fillRect(0, 0, W, Math.max(0, yCar - vis));
      ctx.fillStyle = 'rgba(226,232,240,.25)'; ctx.fillRect(0, yCar, W, H - yCar);
    }

    // Padavine in listje v vetru (zaslon)
    for (var pI = 0; pI < kaplje.length; pI++) {
      var kp = kaplje[pI];
      if (kp.tip === 'sneg') {
        ctx.fillStyle = 'rgba(255,255,255,.9)';
        ctx.beginPath(); ctx.arc(kp.x, kp.y, kp.r, 0, 6.283); ctx.fill();
      } else {
        ctx.strokeStyle = 'rgba(191,219,254,.6)'; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.moveTo(kp.x, kp.y); ctx.lineTo(kp.x + 2, kp.y - 14); ctx.stroke();
      }
    }
    for (var lI = 0; lI < listi.length; lI++) {
      var li = listi[lI];
      ctx.save(); ctx.translate(li.x, li.y); ctx.rotate(li.f);
      ctx.fillStyle = li.barva; ctx.beginPath(); ctx.ellipse(0, 0, 4, 2, 0, 0, 6.283); ctx.fill();
      ctx.restore();
    }

    hud();
  }

  function svetT(c, camH, hx, hy, shx, shy) {
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.translate(W / 2 + (shx || 0), H * 0.74 + (shy || 0));
    c.scale(PX, PX);
    c.rotate(camH);
    c.translate(-hx, -hy);
  }

  // Tema (noč, somrak) iz level.svetloba (višina sonca ob uri nivoja): temna
  // plast, iz katere žarometi izrežejo stožec pred avtom.
  function tema(camH, hx, hy, shx, shy) {
    var sv = level && level.svetloba;
    var moc = sv === 'noc' ? 0.74 : sv === 'somrak' ? 0.4 : 0;
    if (!moc) return;
    if (!temaC || temaC.width !== canvas.width || temaC.height !== canvas.height) {
      temaC = document.createElement('canvas');
      temaC.width = canvas.width; temaC.height = canvas.height;
    }
    var t = temaC.getContext('2d');
    t.setTransform(1, 0, 0, 1, 0, 0);
    t.globalCompositeOperation = 'source-over';
    t.clearRect(0, 0, temaC.width, temaC.height);
    t.fillStyle = 'rgba(8,12,32,' + moc + ')';
    t.fillRect(0, 0, temaC.width, temaC.height);
    t.globalCompositeOperation = 'destination-out';
    svetT(t, camH, hx, hy, shx, shy);
    var a = legaAvta();
    var fx = a.x + a.fx * 2.1, fy = a.y + a.fy * 2.1, dol = 34;
    var gr = t.createRadialGradient(fx, fy, 0, fx, fy, dol);
    gr.addColorStop(0, 'rgba(0,0,0,.95)'); gr.addColorStop(0.6, 'rgba(0,0,0,.6)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
    t.fillStyle = gr;
    t.beginPath();
    t.moveTo(fx - a.rx * 0.9, fy - a.ry * 0.9);
    t.lineTo(fx + a.fx * dol - a.rx * 11, fy + a.fy * dol - a.ry * 11);
    t.lineTo(fx + a.fx * dol + a.rx * 11, fy + a.fy * dol + a.ry * 11);
    t.lineTo(fx + a.rx * 0.9, fy + a.ry * 0.9);
    t.closePath(); t.fill();
    var gr2 = t.createRadialGradient(a.x, a.y, 0, a.x, a.y, 4.5);
    gr2.addColorStop(0, 'rgba(0,0,0,.55)'); gr2.addColorStop(1, 'rgba(0,0,0,0)');
    t.fillStyle = gr2; t.beginPath(); t.arc(a.x, a.y, 4.5, 0, 6.283); t.fill();
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(temaC, 0, 0);
    ctx.restore();
    if (sv === 'somrak') {
      var g2 = ctx.createLinearGradient(0, 0, 0, H * 0.5);
      g2.addColorStop(0, 'rgba(251,146,60,.22)'); g2.addColorStop(1, 'rgba(251,146,60,0)');
      ctx.fillStyle = g2; ctx.fillRect(0, 0, W, H * 0.5);
    }
  }

  function kamen(km) {
    ctx.fillStyle = '#fff'; ctx.strokeStyle = '#111'; ctx.lineWidth = 1.5;
    ctx.fillRect(-6, -14, 12, 14); ctx.strokeRect(-6, -14, 12, 14);
    ctx.fillStyle = '#dc2626'; ctx.fillRect(-6, -14, 12, 4);
    ctx.fillStyle = '#111'; ctx.font = '800 8px Inter,system-ui,sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(String(km), 0, -5);
  }

  // Stripovski avto (v metrih, sprednji del proti -y).
  function narisiAvto() {
    ctx.fillStyle = 'rgba(0,0,0,.28)';
    rr(-0.95 + 0.35, -2.15 + 0.45, 1.9, 4.3, 0.5); ctx.fill();
    // Kolesa (z verigami rumena)
    ctx.fillStyle = '#111';
    [[-1.12, -1.75], [0.72, -1.75], [-1.12, 0.95], [0.72, 0.95]].forEach(function (k) {
      ctx.fillRect(k[0], k[1], 0.4, 0.85);
      if (sim.verige) {
        ctx.fillStyle = '#fde047';
        for (var i = 0; i < 3; i++) ctx.fillRect(k[0] - 0.02, k[1] + 0.1 + i * 0.27, 0.44, 0.1);
        ctx.fillStyle = '#111';
      }
    });
    ctx.fillStyle = '#dc2626'; ctx.strokeStyle = '#111'; ctx.lineWidth = 0.22;
    rr(-0.95, -2.15, 1.9, 4.3, 0.55); ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#b91c1c'; rr(-0.72, -0.6, 1.44, 1.55, 0.25); ctx.fill();
    ctx.fillStyle = '#bfdbfe'; ctx.strokeStyle = '#111'; ctx.lineWidth = 0.12;
    rr(-0.74, -1.45, 1.48, 0.72, 0.2); ctx.fill(); ctx.stroke();
    rr(-0.68, 1.05, 1.36, 0.45, 0.15); ctx.fill(); ctx.stroke();
    // Žarometi in zavorne luči
    ctx.fillStyle = '#fef9c3';
    ctx.fillRect(-0.8, -2.12, 0.42, 0.18); ctx.fillRect(0.38, -2.12, 0.42, 0.18);
    var zav = ui.faza === 'voznja' && ui.zavora;
    if (zav) { ctx.shadowColor = '#ef4444'; ctx.shadowBlur = 14; }
    ctx.fillStyle = zav ? '#ff3b3b' : '#7f1d1d';
    ctx.fillRect(-0.82, 1.95, 0.46, 0.2); ctx.fillRect(0.36, 1.95, 0.46, 0.2);
    ctx.shadowBlur = 0;
  }

  function rr(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }

  // Predmet ob cesti, obrnjen pokončno proti gledalcu (risanje v pikslih).
  function pokoncno(x, y, camH, fn) {
    ctx.save();
    ctx.translate(x, y); ctx.rotate(-camH); ctx.scale(1 / PX, 1 / PX);
    fn();
    ctx.restore();
  }

  function znakOvinek(smer) {
    ctx.fillStyle = '#111'; ctx.fillRect(-1.5, -6, 3, 16);
    ctx.beginPath(); ctx.moveTo(0, -30); ctx.lineTo(14, -6); ctx.lineTo(-14, -6); ctx.closePath();
    ctx.fillStyle = '#fff'; ctx.fill();
    ctx.lineJoin = 'round'; ctx.lineWidth = 3.5; ctx.strokeStyle = '#dc2626'; ctx.stroke();
    ctx.lineWidth = 1; ctx.strokeStyle = '#111'; ctx.stroke();
    // puščica ovinka (levo/desno)
    ctx.strokeStyle = '#111'; ctx.lineWidth = 2.4; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(0, -9); ctx.quadraticCurveTo(0, -18, -5 * smer, -20); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-5 * smer, -23); ctx.lineTo(-8 * smer, -20); ctx.lineTo(-5 * smer, -17);
    ctx.stroke();
  }

  function tabla(tb) {
    ctx.font = '900 11px Inter,system-ui,sans-serif';
    var w = Math.max(ctx.measureText(tb.txt).width + 14, 54), h = tb.sub ? 30 : 20;
    ctx.fillStyle = '#111'; ctx.fillRect(-w / 2 + 4, -2, 3, 12); ctx.fillRect(w / 2 - 7, -2, 3, 12);
    ctx.fillStyle = tb.tip === 'kraj' ? '#fde047' : '#fff';
    ctx.strokeStyle = '#111'; ctx.lineWidth = 2;
    ctx.fillRect(-w / 2, -h - 2, w, h); ctx.strokeRect(-w / 2, -h - 2, w, h);
    ctx.fillStyle = '#111'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(tb.txt, 0, tb.sub ? -h + 7 : -h / 2 - 2);
    if (tb.sub) { ctx.font = '800 10px Inter,system-ui,sans-serif'; ctx.fillStyle = '#dc2626'; ctx.fillText(tb.sub, 0, -9); }
  }

  function pot(a, b) {
    ctx.beginPath();
    ctx.moveTo(track.x[a], track.y[a]);
    for (var s = a + 2; s <= b; s += 2) ctx.lineTo(track.x[s], track.y[s]);
    ctx.lineTo(track.x[b], track.y[b]);
  }

  function hud() {
    var kmh = Math.round(sim.v * 3.6);
    var km = kmNa(sim.s);
    var z = Math.round(zNa(level, sim.s));
    var p = surfAt(sim, sim.s);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = 'rgba(255,255,255,.92)';
    ctx.strokeStyle = '#111'; ctx.lineWidth = 2;
    roundRect(8, 8, W - 16, 50, 10); ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#111';
    ctx.font = '800 ' + (W < 420 ? 17 : 22) + 'px Inter,system-ui,sans-serif';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    ctx.fillText(kmh + ' km/h', 18, 33);
    ctx.textAlign = 'right';
    ctx.fillText(fmtCas(sim.t + sim.pen), W - 18, 33);
    ctx.textAlign = 'center';
    ctx.font = '700 ' + (W < 420 ? 11 : 12) + 'px Inter,system-ui,sans-serif';
    ctx.fillText(fmt(km, 1) + ' / ' + fmt(L_REAL_KM, 1) + ' km · ' + z + ' m', W / 2, 24);
    ctx.fillStyle = p === 'led' ? '#1d4ed8' : p === 'sneg' ? '#475569' : '#111';
    ctx.fillText((sim.verige ? '⛓ verige · ' : '') + 'vozišče: ' + SURF_IME[p] + (sim.drsi ? ' · DRSI!' : ''), W / 2, 44);

    // Višinski profil s površinami in piko avta
    if (profil) {
      ctx.drawImage(profil, 0, 0, W, PROFIL_Y + PROFIL_H);
      var xk = 14 + (W - 28) * kmNa(sim.s) / L_REAL_KM, yk = profilY(zNa(level, sim.s));
      ctx.strokeStyle = 'rgba(220,38,38,.6)'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(xk, PROFIL_Y + 3); ctx.lineTo(xk, PROFIL_Y + PROFIL_H - 3); ctx.stroke();
      ctx.fillStyle = '#dc2626'; ctx.strokeStyle = '#111'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(xk, yk, 5, 0, 6.283); ctx.fill(); ctx.stroke();
    }

    if (ui.sporT > 0) {
      ui.sporT -= 1 / 60;
      ctx.font = '900 26px Inter,system-ui,sans-serif';
      ctx.textAlign = 'center';
      ctx.lineWidth = 5; ctx.strokeStyle = '#111'; ctx.fillStyle = '#fde047';
      ctx.strokeText(ui.sporocilo, W / 2, H * 0.4);
      ctx.fillText(ui.sporocilo, W / 2, H * 0.4);
    }
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  function zacni(verige) {
    if (zv.hotel && !zv.on) zvokNastavi(true);
    sim = makeSim(level, { track: track, verige: verige });
    ui.faza = 'voznja'; ui.zadnji = 0; ui.acc = 0; ui.sporT = 0; ui.camH = null;
    ui.shake = 0; ui.vrh = false; ui.sledL = null; ui.zavora = 0; sledi = []; delci = []; kaplje = []; listi = [];
    el('cv-overlay').hidden = true;
    el('cv-chain').textContent = verige ? '⛓ Snemi verige' : '⛓ Natakni verige';
    canvas.focus();
    requestAnimationFrame(loop);
  }

  function klikVerige() {
    if (!sim || ui.faza !== 'voznja') return;
    if (menjajVerige(sim)) {
      sporoci(sim.verige ? 'VERIGE GOR! +' + VERIGE_S + ' s' : 'VERIGE DOL! +' + VERIGE_S + ' s');
      el('cv-chain').textContent = sim.verige ? '⛓ Snemi verige' : '⛓ Natakni verige';
    } else {
      sporoci('Najprej ustavi!');
    }
  }

  function beriBest() {
    try {
      var b = JSON.parse(localStorage.getItem(LS_BEST) || 'null');
      return b && b.datum === level.datum ? b : null;
    } catch (e) { return null; }
  }

  function komentar(cas) {
    if (sim.jarki >= 3) return 'Cesta je bila danes močnejša od tebe. Poskusi počasneje.';
    if (sim.jarki > 0) return 'Jarek pri Črnivcu je bolj udoben, kot izgleda, ampak ne za dolgo.';
    var imaLed = level.odseki.some(function (o) { return o.povrsina === 'led' || o.povrsina === 'sneg'; });
    if (sim.verige && !imaLed) return 'TAK-TAK-TAK po suhem. Verige so danes ostale bolj za okras.';
    if (!sim.verige && imaLed) return 'Brez verig in brez jarka. Ali si dober ali pa si imel srečo.';
    return 'Čista vožnja. Gornji Grad te pričakuje s kavo.';
  }

  function konec() {
    ui.faza = 'konec';
    zvokTik(0, null);
    zvokCilj();
    var cas = koncniCas(sim);
    var prej = beriBest();
    var rekord = !prej || cas < prej.cas;
    if (rekord) {
      try { localStorage.setItem(LS_BEST, JSON.stringify({ datum: level.datum, cas: cas })); } catch (e) { /* ni usodno */ }
    }
    posljiRezultat(cas);
    var ov = el('cv-overlay');
    ov.innerHTML = '<div class="cv-ov-in">' +
      '<p class="cv-kicker">Gornji Grad · cilj</p>' +
      '<h2 class="cv-ov-title">' + fmtCas(cas) + '</h2>' +
      '<p class="cv-ov-sub">vožnja ' + fmtCas(Math.round(sim.t * 10) / 10) +
      (sim.jarki ? ' · jarek ×' + sim.jarki + ' (+' + sim.jarki * PEN_JAREK + ' s)' : '') +
      (sim.menjave ? ' · verige ×' + sim.menjave + ' (+' + sim.menjave * VERIGE_S + ' s)' : '') + '</p>' +
      '<p class="cv-ov-sub">' + esc(komentar(cas)) + '</p>' +
      (rekord ? '<p class="cv-rec">🏅 Tvoj najboljši čas danes</p>'
        : '<p class="cv-ov-sub cv-small">Tvoj najboljši danes: ' + fmtCas(prej.cas) + '</p>') +
      '<div class="cv-ov-btns">' +
      '<button class="crn-btn crn-btn-primary" id="cv-again" type="button">Še enkrat</button>' +
      '<button class="crn-btn" id="cv-share" type="button">Deli sliko</button>' +
      '</div><p class="cv-small" id="cv-share-note" role="status" aria-live="polite"></p></div>';
    ov.hidden = false;
    el('cv-again').addEventListener('click', function () { pokaziStart(); });
    el('cv-share').addEventListener('click', function () { deli(cas); });
    el('cv-again').focus();
  }

  // Slika rezultata (1080×1080, za FB in IG): čas, verige, razmere dneva in
  // profil proge v stripovskem slogu strani.
  function slikaRezultata(cas) {
    var S = 1080, c = document.createElement('canvas');
    c.width = S; c.height = S;
    var g = c.getContext('2d');
    g.fillStyle = '#fdf6e3'; g.fillRect(0, 0, S, S);
    g.fillStyle = 'rgba(17,17,17,.13)';
    for (var yy = 12; yy < S; yy += 28) for (var xx = 12; xx < S; xx += 28) { g.beginPath(); g.arc(xx, yy, 2.4, 0, 6.283); g.fill(); }
    g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round';
    function napis(t, y, vel, barva, obris) {
      g.font = '900 ' + vel + 'px Inter,system-ui,sans-serif';
      if (obris) { g.lineWidth = obris; g.strokeStyle = '#111'; g.strokeText(t, S / 2, y); }
      g.fillStyle = barva; g.fillText(t, S / 2, y);
    }
    function skatla(x, y, w, h, barva) {
      g.fillStyle = '#111'; g.fillRect(x + 10, y + 10, w, h);
      g.fillStyle = barva; g.fillRect(x, y, w, h);
      g.lineWidth = 6; g.strokeStyle = '#111'; g.strokeRect(x, y, w, h);
    }
    napis('ČEZ ČRNIVEC', 120, 110, '#dc2626', 14);
    napis('Stahovica → 902 m → Gornji Grad', 205, 36, '#111');
    skatla(190, 260, 700, 220, '#fef08a');
    napis(fmtCas(cas), 372, 170, '#111');
    var pod = (sim.verige ? 'z verigami' : 'brez verig') +
      (sim.jarki ? ' · jarek ×' + sim.jarki : ' · brez jarka');
    napis(pod, 550, 44, '#111');
    var d = level.datum.split('-');
    napis(Number(d[2]) + '. ' + Number(d[1]) + '. ' + d[0] + ' · ' + (level.vozisce || ''), 610, 34, '#374151');
    skatla(80, 670, 920, 250, '#fff');
    risiProfil(g, 110, 700, 860, 190, 5);
    napis('crnivec.si/igra · premagaj me!', 990, 44, '#111');
    return c;
  }

  function deli(cas) {
    var txt = 'Čez Črnivec v ' + fmtCas(cas) + (sim.verige ? ' (z verigami)' : ' (brez verig)') +
      '. Danes ' + (level.vozisce || '') + '. Poskusi premagati:';
    var url = 'https://crnivec.si/igra/';
    var note = el('cv-share-note');
    var platno;
    try { platno = slikaRezultata(cas); } catch (e) { platno = null; }
    function besedilo() {
      if (navigator.share) {
        navigator.share({ title: 'Čez Črnivec', text: txt, url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(txt + ' ' + url).then(function () { note.textContent = 'Besedilo kopirano.'; },
          function () { note.textContent = txt + ' ' + url; });
      } else { note.textContent = txt + ' ' + url; }
    }
    if (!platno || !platno.toBlob) { besedilo(); return; }
    platno.toBlob(function (blob) {
      if (!blob) { besedilo(); return; }
      var file = null;
      try { file = new File([blob], 'cez-crnivec.png', { type: 'image/png' }); } catch (e) { file = null; }
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], text: txt + ' ' + url }).catch(function () {});
        return;
      }
      // Brez deljenja datotek (npr. namizje): prenesi sliko, besedilo v odložišče.
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = 'cez-crnivec.png';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 5000);
      if (navigator.clipboard) navigator.clipboard.writeText(txt + ' ' + url).catch(function () {});
      note.textContent = 'Slika je prenesena, besedilo s povezavo je v odložišču.';
    }, 'image/png');
  }

  function pokaziStart() {
    ui.faza = 'start';
    ui.camH = null;
    sim = makeSim(level, { track: track });
    draw();
    var ov = el('cv-overlay');
    var best = beriBest();
    ov.innerHTML = '<div class="cv-ov-in">' +
      '<p class="cv-kicker">Stahovica · start</p>' +
      '<h2 class="cv-ov-title">Verige?</h2>' +
      '<p class="cv-ov-sub">' + esc(level.opis || '') + '</p>' +
      '<p class="cv-ov-sub cv-small">Na startu jih nadeneš zastonj. Med vožnjo samo, ko stojiš, in stane ' +
      VERIGE_S + ' s. Z verigami gre največ 50 km/h.</p>' +
      (best ? '<p class="cv-ov-sub cv-small">Tvoj najboljši danes: ' + fmtCas(best.cas) + '</p>' : '') +
      '<div class="cv-ov-btns">' +
      '<button class="crn-btn crn-btn-primary" id="cv-go" type="button">Brez verig</button>' +
      '<button class="crn-btn" id="cv-go-v" type="button">⛓ Z verigami</button>' +
      '</div></div>';
    ov.hidden = false;
    el('cv-go').addEventListener('click', function () { zacni(false); });
    el('cv-go-v').addEventListener('click', function () { zacni(true); });
  }

  // ── Lestvica (worker.js, /crnivec/igra/*) ─────────────────────────────
  function igralecId() {
    var re = /^[a-zA-Z0-9_-]{8,40}$/;
    try { var id = localStorage.getItem(LS_IGRALEC); if (id && re.test(id)) return id; } catch (e) { /* naprej */ }
    var abc = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    var bajti = (window.crypto && crypto.getRandomValues) ? crypto.getRandomValues(new Uint8Array(24)) : null;
    var novId = '';
    for (var i = 0; i < 24; i++) novId += abc[(bajti ? bajti[i] : Math.floor(Math.random() * 256)) % abc.length];
    try { localStorage.setItem(LS_IGRALEC, novId); } catch (e) { /* samo za ta klic */ }
    return novId;
  }
  function beriIme() { try { return localStorage.getItem(LS_IME) || ''; } catch (e) { return ''; } }

  function posljiRezultat(cas) {
    if (!level || !level.datum || level.zastarel) return;
    try {
      var qs = new URLSearchParams({
        datum: level.datum, cas: String(cas), verige: sim.verige ? '1' : '0',
        igralec: igralecId(), ime: beriIme()
      });
      fetch(API + '/crnivec/igra/rezultat?' + qs.toString(), { method: 'POST' })
        .then(function (r) { if (r.ok) izrisiLestvico(); })
        .catch(function () {});
    } catch (e) { /* lestvica ni bistvena */ }
  }

  function izrisiLestvico() {
    var body = el('cv-lb');
    if (!body) return;
    fetch(API + '/crnivec/igra/lestvica', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        var l = (j && j.lestvica) || [];
        if (!l.length) { body.innerHTML = '<p class="cv-small">Danes še nihče ni prišel čez. Bodi prvi.</p>'; return; }
        body.innerHTML = '<ol class="cv-lb-list">' + l.map(function (r) {
          return '<li><span class="cv-lb-ime">' + esc(r.ime) + (r.verige ? ' ⛓' : '') + '</span>' +
            '<span class="cv-lb-cas">' + fmtCas(r.cas) + '</span></li>';
        }).join('') + '</ol>';
      })
      .catch(function () { body.innerHTML = '<p class="cv-small">Lestvica trenutno ni dosegljiva.</p>'; });
  }

  function vezi() {
    document.addEventListener('keydown', function (e) {
      if (ui.faza !== 'voznja') return;
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].indexOf(e.key) >= 0) e.preventDefault();
      if (e.key === 'v' || e.key === 'V') { klikVerige(); return; }
      keys[e.key] = true;
    });
    document.addEventListener('keyup', function (e) { keys[e.key] = false; });
    window.addEventListener('blur', function () { keys = {}; touch = { plin: 0, zavora: 0, levo: 0, desno: 0 }; });
    var btns = document.querySelectorAll('[data-cv]');
    Array.prototype.forEach.call(btns, function (b) {
      var k = b.getAttribute('data-cv');
      function on(e) { e.preventDefault(); touch[k] = 1; b.classList.add('is-on'); }
      function off(e) { e.preventDefault(); touch[k] = 0; b.classList.remove('is-on'); }
      b.addEventListener('pointerdown', on);
      b.addEventListener('pointerup', off);
      b.addEventListener('pointerleave', off);
      b.addEventListener('pointercancel', off);
      b.addEventListener('contextmenu', function (e) { e.preventDefault(); });
    });
    el('cv-chain').addEventListener('click', klikVerige);
    var zb = el('cv-zvok');
    if (zb) {
      zb.addEventListener('click', function () { zvokNastavi(!zv.on); });
      var prej = false;
      try { prej = localStorage.getItem(LS_ZVOK) === '1'; } catch (e) { prej = false; }
      // Brskalnik zvoka ne pusti pred prvim klikom -- zapomnjeno izbiro
      // vklopi šele klik na start (zacni()), do takrat gumb samo pove stanje.
      zv.hotel = prej;
      zb.textContent = prej ? '🔊 Zvok se vklopi ob startu' : '🔇 Zvok izklopljen';
    }
    document.addEventListener('visibilitychange', function () {
      if (zv.ac && zv.on) { if (document.hidden) zv.ac.suspend(); else zv.ac.resume(); }
    });
    var ime = el('cv-ime');
    if (ime) {
      ime.value = beriIme();
      ime.addEventListener('change', function () {
        try { localStorage.setItem(LS_IME, ime.value.trim().slice(0, 24)); } catch (e) { /* ni usodno */ }
      });
    }
    window.addEventListener('resize', resize);
  }

  function init() {
    canvas = el('cv-canvas');
    if (!canvas) return;
    level = beriNivo();
    if (!level || !level.odseki || !level.odseki.length) {
      el('cv-overlay').innerHTML = '<div class="cv-ov-in"><p class="cv-ov-sub">Današnjega nivoja ni. Poskusi kasneje.</p></div>';
      return;
    }
    // Nivo iz prejšnjega dne (jutranji izračun še ni tekel): igra se lahko,
    // na lestvico pa ne gre (strežnik sprejme samo današnji datum).
    try {
      var danes = new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Ljubljana' });
      level.zastarel = level.datum !== danes;
    } catch (e) { level.zastarel = false; }
    if (level.zastarel && el('cv-stale')) el('cv-stale').hidden = false;
    ctx = canvas.getContext('2d');
    try { nastaviProgo(JSON.parse(el('cv-proga').textContent)); } catch (e) {
      el('cv-overlay').innerHTML = '<div class="cv-ov-in"><p class="cv-ov-sub">Proga se ni naložila. Osveži stran.</p></div>';
      return;
    }
    S_VRH = sNaKm(PROGA.vrh_km);
    track = buildTrack();
    postaviPokrajino();
    najdiOvinke();
    vezi();
    resize();
    pokaziStart();
    izrisiLestvico();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})(typeof window !== 'undefined' ? window : globalThis);
