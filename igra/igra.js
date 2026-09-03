/*
 * igra/igra.js — »Termika«: arkadna igra jadralnega padalca nad Zgornjo
 * Savinjsko dolino. Vzletiš z Golt in poskušaš po dolini preleteti čim dlje.
 *
 * Zakaj je to več kot igra: NIVO SE VSAK DAN SESTAVI IZ PRAVEGA VREMENA.
 * Strop, moč termike, razmik med stebri, veter po višini in dež pridejo iz
 * iste napovedi Open-Meteo, ki poganja /vreme-za-padalce/. Ob sončnem
 * julijskem dnevu prideš do Celja, ob plitvi konvekciji pristaneš pod
 * Goltami — in prav to je poanta: igra te nauči brati vremensko sliko.
 *
 * ROČNO pisana, samostojna datoteka (ni generirana). Stran /igra/ ne nalaga
 * app.js — isto načelo kot meteogasilec/gasilec.js: podstran, ki app.js ne
 * potrebuje, ga ne vleče zaradi ene funkcije.
 *
 * TA DATOTEKA NIVOJA NE RAČUNA. Nivo v celoti sestavi
 * tools/generate_igra_page.py (dnevno, prek padalci-forecast.yml) in ga
 * zapiše vdelano v HTML (#pg-level) ter v /igra/nivo.json. Razlog je
 * determinizem: modelski teki Open-Meteo se čez dan menjajo, zato bi klic iz
 * brskalnika ob 7:00 in ob 20:00 dal drugačen strop in drugačno moč termike —
 * obljuba »isti dan, isti nivo za vse« bi bila laž, deljeni rezultati pa
 * neprimerljivi. Ob tem tu ne nastane druga kopija modela, ki bi se s
 * Pythonovo sčasoma razšla (isto načelo kot daily_features pri MTR).
 *
 * ZGRADBA: spodaj je najprej ČIST MODEL (fizika, teren, termika) brez vsake
 * navezave na DOM, nato prikazni del. Model se izvozi tudi za Node, ker ga
 * preverja tools/test_igra.mjs — isti pristop kot pri Horn naklonu/ekspoziciji
 * v gasilec.js, ki je bil pred vklopom enotno testiran na sintetičnih vhodih.
 * Nova fizika naj gre v model, ne v prikazni del.
 */
(function (global) {
  'use strict';

  // ═══════════════════════════════════════════════════════════════════════
  //  MODEL — čista fizika, brez DOM. Vse funkcije delajo na objektu `sim`.
  // ═══════════════════════════════════════════════════════════════════════

  // Polara padala. Približek šolskega krila razreda EN-B: najmanjši spust
  // 0,95 m/s pri 8,5 m/s (31 km/h), najboljše drsenje ~9,9 : 1 pri 10,5 m/s
  // (38 km/h), s pospeševalnikom ~7,5 : 1 pri 14,4 m/s (52 km/h).
  var V_CIRCLE = 8.5, V_GLIDE = 10.5, V_FAST = 14.4;
  var BANK_PENALTY = 1.35;      // spust pri kroženju z nagibom ~45°
  var NUDGE_SPEED = 2.6;        // popravek lege med kroženjem (m/s)
  // Pod toliko metri nad tlemi je termika šibka in razbita. 80 m je blizu
  // temu, kar pilot nad prisojnim pobočjem res še izkoristi — višja meja bi
  // ob nizkem stropu naredila reševanje z majhne višine nemogoče.
  var AGL_RAMP = 80;
  var TOP_RAMP = 150;           // toliko metrov pod stropom dvig ugaša
  function sinkAt(v) { return 0.95 + 0.0279 * (v - 8.5) * (v - 8.5); }

  // Sejano naključje. Seme pride iz nivoja (izpeljano iz datuma), zato je
  // razporeditev stebrov isti dan za vse enaka. Uporablja se SAMO za
  // postavitev nivoja — nikoli za fiziko, vnos ali izračun rezultata.
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

  function lerpPairs(pairs, km) {
    if (km <= pairs[0][0]) return pairs[0][1];
    if (km >= pairs[pairs.length - 1][0]) return pairs[pairs.length - 1][1];
    for (var i = 1; i < pairs.length; i++) {
      if (km <= pairs[i][0]) {
        var a = pairs[i - 1], b = pairs[i];
        return a[1] + (b[1] - a[1]) * (km - a[0]) / (b[0] - a[0]);
      }
    }
    return pairs[pairs.length - 1][1];
  }

  // MERODAJEN je profil iz nivoja (POT v tools/generate_igra_page.py) — to je
  // samo rezerva za okrnjen nivo. Namerna kopija: klientska stran do Pythona
  // nima dostopa. Če spremeniš POT, popravi tudi to.
  var TERRAIN_FALLBACK = [
    [0.0, 1400], [0.6, 1300], [1.2, 1150], [2.0, 950], [3.0, 760],
    [4.0, 620], [5.5, 500], [7.0, 430], [8.5, 395], [10.3, 374],
    [12.0, 355], [13.6, 338], [15.0, 380], [16.5, 470], [17.8, 400],
    [19.1, 320], [21.0, 360], [23.4, 290], [25.7, 280], [28.0, 320],
    [30.5, 300], [33.5, 250], [36.0, 285], [38.5, 320], [41.7, 241],
    [44.0, 260]
  ];
  var PLACES_FALLBACK = [
    { km: 0.0, ime: 'Golte' }, { km: 10.3, ime: 'Rečica' },
    { km: 13.6, ime: 'Mozirje' }, { km: 19.1, ime: 'Letuš' },
    { km: 23.4, ime: 'Braslovče' }, { km: 25.7, ime: 'Polzela' },
    { km: 33.5, ime: 'Žalec' }, { km: 41.7, ime: 'Celje' }
  ];

  // Vadbeni dan: zadnja rezerva, kadar ni ne vdelanega nivoja ne nivo.json.
  // Označen je izrecno kot vadbeni, nikoli kot »današnji«.
  var TRAINING_LEVEL = {
    datum: null, generated: null, vir: 'vadba', seme: 20260101, ura: null,
    strop_m: 2000, strop_bl_m: 2050, baza_m: 1950,
    termika_ms: 2.4, w_star: 1.8, sink_ms: 0.55, gostota_km: 2.0,
    z_i_m: 1650, veter_tla_ms: 1.2, veter_180_ms: 2.8,
    veter_kmh: 12, veter_smer: 285, turbulenca: 0.3,
    padavine_mm: 0, koda_vremena: 2, konec_km: 44
  };

  function buildTerrain(level) {
    if (level.teren && level.teren.h && level.teren.h.length > 2) {
      return {
        step: (level.teren.korak_m || 250) / 1000,
        from: level.teren.od_km || 0,
        h: level.teren.h
      };
    }
    var step = 0.25, h = [];
    for (var km = 0; km <= (level.konec_km || 44) + 1e-9; km += step) {
      h.push(lerpPairs(TERRAIN_FALLBACK, km));
    }
    return { step: step, from: 0, h: h };
  }

  function terrainAt(sim, km) {
    var t = sim.terrain;
    var f = (km - t.from) / t.step;
    if (f <= 0) return t.h[0];
    if (f >= t.h.length - 1) return t.h[t.h.length - 1];
    var i = Math.floor(f);
    return t.h[i] + (t.h[i + 1] - t.h[i]) * (f - i);
  }

  // Veter po višini iz TREH izmerjenih nivojev: 10 m, 180 m in ~1500 m
  // (850 hPa). Prej je bil zgornji del ekstrapoliran po Hellmannovem zakonu iz
  // 180 m, kar je bilo ugibanje — in pogosto v napačno smer, ker je dolinski
  // vetrič pri tleh redno obrnjen nasproti gradientnemu vetru zgoraj.
  // Vrednosti so v nivoju že projicirane na koridor dneva: + je hrbtnik.
  function windAt(sim, agl) {
    var l = sim.level;
    var lo = l.veter_tla_ms || 0;
    var mid = l.veter_180_ms;
    if (mid === undefined || mid === null) mid = lo;
    var hi = l.veter_visoko_ms;
    if (hi === undefined || hi === null) hi = mid;
    if (agl <= 10) return lo;
    if (agl <= 180) return lo + (mid - lo) * (agl - 10) / 170;
    if (agl <= 1500) return mid + (hi - mid) * (agl - 180) / 1320;
    return hi;
  }

  function buildThermals(sim) {
    var l = sim.level, rnd = mulberry32(l.seme || 1);
    var list = [], km = 0.6, guard = 0;
    var gostota = clamp(l.gostota_km || 2, 0.7, 4.5);
    // Premer stebra je vezan na globino konvekcije (~z_i/9 v polmeru), ne
    // fiksen. Če je polmer fiksen, se ob plitvi konvekciji stebri prekrivajo,
    // nebo postane ena sama termika in dan se da preleteti brez enega
    // samega kroga — preverjeno s tools/test_igra.mjs.
    // Premer jedra je pri konvekciji reda z_i/3, torej polmer ~z_i/6. Prej je
    // bil tu z_i/9 in stebri so bili tako tanki, da jih je bilo mogoče
    // prečkati, ne pa zadržati — dvigi so bili le drobne packe med spustom.
    var zi = l.z_i_m || sim.ceilAGLref || 1200;
    var r0 = clamp(zi * 0.16, 110, 340);
    while (km < sim.endKm && guard++ < 300) {
      var here = terrainAt(sim, km);
      var around = (terrainAt(sim, km - 0.9) + terrainAt(sim, km + 0.9)) / 2;
      // Termiko sprožijo grebeni in prisojna pobočja, zato steber nad
      // izpostavljeno točko dobi pribitek. Kazen za dno doline je blaga:
      // odkar je profil iz pravega DEM-a in ne iz gladke ročne krivulje, je
      // krajevna razgibanost velika in prejšnja meja (−30 %) je zadela skoraj
      // vsak dolinski steber — dvigi so padli pod spust pri kroženju in
      // kroženje ni več dvigalo. Sončno dno doline je v resnici spodoben
      // sprožilec (polja, vasi), le slabši od grebena.
      var prom = clamp((here - around) / 220, -0.18, 0.30);
      list.push({
        km: km,
        r0: r0 * (0.85 + 0.4 * rnd()),
        moc: (l.termika_ms || 2) * (0.85 + 0.35 * rnd()) * (1 + prom)
      });
      km += gostota * (0.78 + 0.46 * rnd());
    }
    return list;
  }

  // Navpična hitrost zraka (m/s, + je dvig).
  function airVertical(sim, km, alt) {
    var l = sim.level;
    var ground = terrainAt(sim, km);
    var agl = alt - ground;
    if (agl < 0) return 0;
    if (alt > sim.ceilASL) return -l.sink_ms;   // nad konvekcijsko plastjo

    // Steber se z višino nagne po vetru: kar pri tleh sproži greben, je na
    // višini že odneseno po dolini. To je pravi problem preletov.
    var offset = clamp(sim.tiltPerM * agl, -2.5, 2.5);
    var lift = 0, th = sim.thermals;
    for (var i = 0; i < th.length; i++) {
      var t = th[i];
      var dx = (km - (t.km + offset)) * 1000;
      if (dx > 2200 || dx < -2200) continue;
      // Steber se z višino razširi in oslabi.
      var r = t.r0 * (0.6 + 0.9 * clamp(agl / sim.ceilAGLref, 0, 1.2));
      var d = dx / r;
      var core = t.moc * Math.exp(-d * d);
      if (core < 0.02) continue;
      core *= Math.min(1, agl / AGL_RAMP) * Math.min(1, (sim.ceilASL - alt) / TOP_RAMP);
      lift += core;
    }
    if (lift > 0.02) return lift;
    // Med stebri: masovni spust. Zrak, ki gre gor, se mora nekje spustiti —
    // in močnejši ko je dan, hujši je spust vmes.
    return -l.sink_ms * clamp(agl / 220, 0.3, 1);
  }

  function makeSim(level, rand) {
    var sim = {
      level: level,
      rand: rand || Math.random,
      endKm: level.konec_km || 44,
      places: (level.mejniki && level.mejniki.length) ? level.mejniki : PLACES_FALLBACK,
      terrain: null, thermals: [], clouds: [],
      ceilASL: 0, ceilAGLref: 0, tiltPerM: 0,
      km: 0, alt: 0, vario: 0, simTime: 0, best: 0,
      reached: '', atCeiling: false, status: 'flying'
    };
    sim.terrain = buildTerrain(level);
    sim.ceilASL = clamp(level.strop_m || 1600, 400, 4500);
    sim.ceilAGLref = Math.max(300, sim.ceilASL - 374);
    // Nagib stebra: pri dvigu w* in vetru u se steber na višini h zamakne za
    // u/w* · h. Pri šibki termiki in močnem vetru je zamik ogromen — takrat
    // termika res »ne stoji«.
    sim.tiltPerM = (level.veter_180_ms || 0) /
      Math.max(0.5, level.w_star || level.termika_ms || 1) / 1000;
    sim.thermals = buildThermals(sim);
    sim.clouds = buildClouds(sim);
    resetSim(sim);
    return sim;
  }

  function buildClouds(sim) {
    var out = [], l = sim.level;
    if (!l.baza_m) return out;              // moder dan — kumulusov ni
    for (var i = 0; i < sim.thermals.length; i++) {
      var t = sim.thermals[i];
      out.push({
        km: t.km + clamp(sim.tiltPerM * (l.baza_m - terrainAt(sim, t.km)), -2.5, 2.5),
        alt: l.baza_m + 40,
        w: 300 + t.r0 * 1.6,
        // Debelina kumulusa je sorazmerna moči stebra pod njim — v resnici je
        // ravno tako in prav po tem pilot izbira, kateri oblak je vreden ovinka.
        h: 90 + 80 * clamp(t.moc / Math.max(l.termika_ms, 0.1), 0, 1.4)
      });
    }
    return out;
  }

  function resetSim(sim) {
    sim.km = 0.2;
    sim.alt = terrainAt(sim, 0.2) + 40;
    sim.vario = 0;
    sim.simTime = 0;
    sim.best = 0.2;
    sim.reached = '';
    sim.atCeiling = false;
    sim.status = 'flying';
  }

  /** En korak fizike. ctrl = { mode: 'glide'|'circle'|'fast', nudge: -1..1 }. */
  function stepFixed(sim, ctrl, dts) {
    if (sim.status !== 'flying') return sim.status;
    var l = sim.level;
    sim.simTime += dts;

    var mode = ctrl.mode || 'glide';
    var v = mode === 'fast' ? V_FAST : (mode === 'circle' ? V_CIRCLE : V_GLIDE);
    var sink = sinkAt(v) * (mode === 'circle' ? BANK_PENALTY : 1);
    if (l.padavine_mm > 0.3) sink *= 1.08;      // mokro krilo

    var agl = sim.alt - terrainAt(sim, sim.km);
    var u = windAt(sim, Math.max(0, agl));
    // Med kroženjem po zraku ne napreduješ — le zanaša te veter (in popravek,
    // s katerim loviš jedro).
    var vx = (mode === 'circle' ? (ctrl.nudge || 0) * NUDGE_SPEED : v) + u;
    sim.km += vx * dts / 1000;

    var w = airVertical(sim, sim.km, sim.alt);
    if (l.turbulenca > 0.05) w += (sim.rand() - 0.5) * l.turbulenca * 2;

    // Strop drži samo navzdol: v oblak se ne leti. Kadar je konvekcija plitva,
    // je strop lahko NIŽJI od vzletišča (dan z močno inverzijo — z Golt takrat
    // res samo zdrsneš) — takrat skoznjo padaš normalno in te ne sme prilepiti
    // na strop, sicer bi let končal že v prvi desetinki sekunde.
    var podStropom = sim.alt <= sim.ceilASL;
    sim.atCeiling = podStropom && sim.alt >= sim.ceilASL - 6;
    if (sim.atCeiling && w > 0) w = 0;

    var vz = w - sink;
    sim.alt += vz * dts;
    if (podStropom && sim.alt > sim.ceilASL) sim.alt = sim.ceilASL;
    sim.vario += (vz - sim.vario) * 0.06;

    if (sim.km > sim.best) sim.best = sim.km;
    for (var p = sim.places.length - 1; p >= 1; p--) {
      if (sim.best >= sim.places[p].km) { sim.reached = sim.places[p].ime; break; }
    }

    if (sim.km >= sim.endKm) { sim.km = sim.endKm; sim.status = 'finished'; return sim.status; }
    if (sim.km < 0) sim.km = 0;
    if (sim.alt <= terrainAt(sim, sim.km)) {
      sim.alt = terrainAt(sim, sim.km);
      sim.status = 'landed';
    }
    return sim.status;
  }

  /**
   * Preprosta strategija za PREVERJANJE nivoja (tools/test_igra.mjs) — ne
   * uporablja je igra sama. Kroži, dokler dviguje in dokler je pod stropom;
   * sicer drsi. Meri, kaj dan sploh dopušča.
   */
  function autoFly(level, opts) {
    opts = opts || {};
    var sim = makeSim(level, opts.rand || Math.random);
    var dts = 1 / 60, maxT = opts.maxSimSeconds || 6 * 3600;
    var ctrl = { mode: 'glide', nudge: 0 };
    while (sim.status === 'flying' && sim.simTime < maxT) {
      var w = airVertical(sim, sim.km, sim.alt);
      var room = sim.ceilASL - sim.alt;
      ctrl.mode = (w > 0.45 && room > 25) ? 'circle' : 'glide';
      stepFixed(sim, ctrl, dts);
    }
    return { km: sim.best, status: sim.status, minutes: sim.simTime / 60, reached: sim.reached };
  }

  var Model = {
    V_CIRCLE: V_CIRCLE, V_GLIDE: V_GLIDE, V_FAST: V_FAST,
    BANK_PENALTY: BANK_PENALTY, NUDGE_SPEED: NUDGE_SPEED,
    TERRAIN_FALLBACK: TERRAIN_FALLBACK, PLACES_FALLBACK: PLACES_FALLBACK,
    TRAINING_LEVEL: TRAINING_LEVEL,
    sinkAt: sinkAt, mulberry32: mulberry32, clamp: clamp, lerpPairs: lerpPairs,
    buildTerrain: buildTerrain, terrainAt: terrainAt, windAt: windAt,
    buildThermals: buildThermals, airVertical: airVertical,
    makeSim: makeSim, resetSim: resetSim, stepFixed: stepFixed, autoFly: autoFly
  };

  if (typeof module !== 'undefined' && module.exports) { module.exports = Model; return; }
  global.IgraModel = Model;

  // ═══════════════════════════════════════════════════════════════════════
  //  PRIKAZ — od tu naprej DOM. Brez fizike.
  // ═══════════════════════════════════════════════════════════════════════

  if (typeof document === 'undefined') return;
  var root = document.getElementById('pg-game');
  if (!root) return;
  var canvas = document.getElementById('pg-canvas');
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext('2d');

  // Igralni čas teče hitreje od resničnega, sicer bi en prelet trajal uro.
  // Pri 30× traja najboljši dan (Golte→Celje) okoli 5 minut, povprečen dan
  // dobri dve, plitev pa pol minute. Vidni pas je širok 2,6 km, kar pri tem
  // tempu da ~7 sekund, da steber pred sabo opaziš in se odločiš — zato
  // hitrejši tempo ni mogoč, ne da bi igra postala ugibanje.
  var TIME_SCALE = 30;
  var FIXED_DT = 1 / 60;   // fiksen korak: na počasnem telefonu se mora nivo
                           // odigrati enako kot na hitrem

  var sim = null;
  var ui = {
    vir: '', svez: null, phase: 'loading',   // loading | ready | flying | over
    mode: 'glide', nudge: 0, lastTs: 0, acc: 0, shake: 0, frameNo: 0,
    trail: [], trailAcc: 0                   // sled leta (barogram med letom)
  };
  var TRAIL_MAX = 160;      // ~4 km sledi pri vzorčenju spodaj
  var TRAIL_EVERY = 1.6;    // simulacijske sekunde med točkama
  var held = { circle: false, fast: false };

  function fmt(v, d) {
    var s = (Math.round(v * Math.pow(10, d)) / Math.pow(10, d)).toFixed(d);
    return s.replace('.', ',');
  }
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  var DIRS = ['S', 'SSV', 'SV', 'VSV', 'V', 'VJV', 'JV', 'JJV',
    'J', 'JJZ', 'JZ', 'ZJZ', 'Z', 'ZSZ', 'SZ', 'SSZ'];
  function dirLabel(deg) {
    if (deg === null || deg === undefined || isNaN(deg)) return '—';
    return DIRS[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16];
  }

  // Svežina podatka. NAMERNA kopija pragov iz renderFreshness() v
  // meteogasilec/gasilec.js (🟢 <26 h, 🟡 26–50 h, 🔴 >50 h) — strani si
  // klientske kode ne delita, ker ju piše drug generator. Če pragove
  // spremeniš, popravi obe. Načelo je isto: stare vrednosti ne skrivamo,
  // samo označimo jo.
  function svezina(generatedISO) {
    if (!generatedISO) return { ikona: '', ur: null };
    var t = Date.parse(generatedISO);
    if (isNaN(t)) return { ikona: '', ur: null };
    var ur = (Date.now() - t) / 3600000;
    return { ikona: ur < 26 ? '🟢' : (ur <= 50 ? '🟡' : '🔴'), ur: ur };
  }

  // ── Nalaganje nivoja ───────────────────────────────────────────────────
  function readInline() {
    var e = document.getElementById('pg-level');
    if (!e) return null;
    try {
      var d = JSON.parse(e.textContent || e.innerText || 'null');
      return (d && d.termika_ms !== undefined) ? d : null;
    } catch (err) { return null; }
  }

  function applyLevel(level, vir) {
    sim = makeSim(level);
    ui.vir = vir;
    ui.svez = svezina(level.generated);
    renderConditions();
    buildRoute();
    updateHud();
    if (ui.phase === 'loading') { ui.phase = 'ready'; showOverlay('ready'); }
  }

  function loadLevel() {
    var inline = readInline();
    if (inline) applyLevel(inline, inline.vir || 'open-meteo');

    // nivo.json je zaradi service workerja lahko svežji od vdelanega —
    // poberemo ga, a igre sredi leta ne prekinjamo.
    fetch('/igra/nivo.json?_=' + Math.floor(Date.now() / 300000))
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) {
        if (!d || d.termika_ms === undefined) return;
        if (inline && d.datum === inline.datum && d.generated === inline.generated) return;
        if (ui.phase === 'flying') return;
        applyLevel(d, d.vir || 'open-meteo');
      })
      .catch(function () { if (!inline) applyLevel(TRAINING_LEVEL, 'vadba'); });
  }

  // ── Izris ──────────────────────────────────────────────────────────────
  var VIEW_W = 2600, VIEW_H = 900;   // m vidnega pasu (navpično raztegnjeno)
  var W = 900, H = 506;
  var reduceMotion = false;
  try {
    reduceMotion = !!(window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  } catch (e) { /* brez podpore: polna animacija */ }

  function resize() {
    var rect = canvas.getBoundingClientRect();
    var cssW = Math.max(280, Math.round(rect.width || canvas.clientWidth || 900));
    // Na ozkem zaslonu je široko razmerje neigralno (pri 366 px širine bi bilo
    // platno visoko 205 px, kar sam vario stolpec skoraj zapolni), zato je tam
    // višje. Navzgor ga omeji višina okna, da ostane prostor za gumbe.
    var ratio = cssW < 560 ? 0.86 : 0.56;
    var cssH = Math.round(cssW * ratio);
    var maxH = Math.round((window.innerHeight || 800) * 0.55);
    if (cssH > maxH) cssH = Math.max(180, maxH);
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.style.height = cssH + 'px';
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    W = cssW; H = cssH;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function camera() {
    var gy = terrainAt(sim, sim.km);
    return {
      x: sim.km * 1000 - VIEW_W * 0.33,
      top: Math.max(sim.alt + VIEW_H * 0.34, gy + VIEW_H * 0.80)
    };
  }
  function sx(m, cam) { return (m - cam.x) / VIEW_W * W; }
  function sy(a, cam) { return (cam.top - a) / VIEW_H * H; }

  // ── Nebo ───────────────────────────────────────────────────────────────
  // Trije zaustavki namesto dveh: zenit, sredina in soparna plast tik nad
  // obzorjem. Dvobarvni preliv je bil raven kot stena — prav spodnja svetla
  // plast je tisto, kar naredi globino.
  function skyStops() {
    var l = sim.level, code = l.koda_vremena || 0;
    if (code === 45 || code === 48) return ['#6a727d', '#8f97a1', '#b9bfc6'];
    if ((l.padavine_mm || 0) > 0.7) return ['#1e2b3c', '#3a4c62', '#5d7085'];
    if (code <= 1) return ['#0a3670', '#3d8fd4', '#a9d6f2'];
    if (code <= 3) return ['#1e4472', '#5f92bf', '#bcd4e4'];
    return ['#33455a', '#6c7f93', '#aab5c0'];
  }

  function drawSky(cam) {
    var st = skyStops();
    var g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, st[0]);
    g.addColorStop(0.62, st[1]);
    g.addColorStop(1, st[2]);
    ctx.fillStyle = g;
    ctx.fillRect(-12, -12, W + 24, H + 24);

    var code = sim.level.koda_vremena || 0;
    if (code <= 3 && (sim.level.padavine_mm || 0) < 0.7) drawSun();
    drawHaze(cam);
  }

  // Sonce stoji glede na uro vrhunca termike — ob 13h visoko, ob 17h nizko.
  // Ne premika se s kamero: je nebesno telo, ne del pokrajine.
  function drawSun() {
    var ura = sim.level.ura ? parseInt(sim.level.ura.slice(0, 2), 10) : 13;
    var t = clamp((ura - 6) / 12, 0, 1);          // 6h → vzhod, 18h → zahod
    var x = W * (0.12 + 0.76 * t);
    var y = H * (0.52 - 0.40 * Math.sin(Math.PI * t));
    var r = Math.max(11, W * 0.017);
    var glow = ctx.createRadialGradient(x, y, r * 0.6, x, y, r * 7);
    glow.addColorStop(0, 'rgba(255,236,180,.42)');
    glow.addColorStop(0.35, 'rgba(255,226,150,.13)');
    glow.addColorStop(1, 'rgba(255,226,150,0)');
    ctx.fillStyle = glow;
    ctx.beginPath(); ctx.arc(x, y, r * 7, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(255,247,214,.95)';
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  }

  // Soparna plast nad dolino: v resnici je meja konvekcijske plasti pogosto
  // vidna kot rjavkast rob, in prav tam se termika ustavi.
  function drawHaze(cam) {
    var hy = sy(sim.ceilASL, cam);
    if (hy < -60 || hy > H + 60) return;
    var g = ctx.createLinearGradient(0, hy - H * 0.05, 0, hy + H * 0.16);
    g.addColorStop(0, 'rgba(214,190,150,0)');
    g.addColorStop(0.4, 'rgba(214,190,150,.10)');
    g.addColorStop(1, 'rgba(214,190,150,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, hy - H * 0.05, W, H * 0.21);
  }

  function draw() {
    if (!sim) { drawLoading(); return; }
    var cam = camera(), l = sim.level;
    ctx.save();
    if (ui.shake > 0.02 && !reduceMotion) {
      ctx.translate((Math.random() - 0.5) * ui.shake * 5, (Math.random() - 0.5) * ui.shake * 5);
    }

    drawSky(cam);
    drawRidges(cam);
    for (var i = 0; i < sim.clouds.length; i++) {
      var c = sim.clouds[i], cxp = sx(c.km * 1000, cam);
      if (cxp < -320 || cxp > W + 320) continue;
      drawCumulus(cxp, sy(c.alt, cam), c.w / VIEW_W * W, c.h / VIEW_H * H);
    }
    drawCeiling(cam, l);
    drawThermals(cam, l);
    drawTerrain(cam);
    if ((l.padavine_mm || 0) > 0.15) drawRain(l);
    drawTrail(cam);
    drawGlider(cam);
    ctx.restore();
    drawInstruments(cam);
  }

  function drawLoading() {
    var g0 = ctx.createLinearGradient(0, 0, 0, H);
    g0.addColorStop(0, '#12283f'); g0.addColorStop(1, '#5a7d9e');
    ctx.fillStyle = g0; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(232,237,248,.85)';
    ctx.font = '600 13px system-ui,sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Pripravljam današnje razmere …', W / 2, H / 2);
    ctx.textAlign = 'left';
  }

  function drawCeiling(cam, l) {
    var cy = sy(sim.ceilASL, cam);
    if (cy < -40 || cy > H) return;
    ctx.strokeStyle = 'rgba(255,255,255,.30)';
    ctx.setLineDash([6, 7]); ctx.lineWidth = 1.1;
    ctx.beginPath(); ctx.moveTo(0, cy); ctx.lineTo(W, cy); ctx.stroke();
    ctx.setLineDash([]);
    // Padalo je vedno pri ~33 % širine, zato gre oznaka desno od njega —
    // sicer se ob prehodu skozi strop besedilo in krilo prekrijeta.
    var txt = (l.baza_m ? 'baza oblakov ' : 'vrh termike ') + Math.round(sim.ceilASL) + ' m';
    ctx.font = '600 11px system-ui,sans-serif';
    var tw = ctx.measureText(txt).width;
    // Desno je vario stolpec (~38 px), levo pri 33 % padalo — oznaka mora med
    // njiju, na ozkem zaslonu pa se umakne levo.
    var tx = Math.max(W * 0.36, Math.min(W * 0.52, W - 42 - tw));
    var ty = Math.max(13, cy - 7);
    ctx.fillStyle = 'rgba(4,7,14,.34)';
    ctx.fillRect(tx - 4, ty - 10, tw + 8, 14);
    ctx.fillStyle = 'rgba(255,255,255,.78)';
    ctx.fillText(txt, tx, ty);
  }

  // Kumulus s senčenjem: bela kapa zgoraj, siva ravna baza spodaj. Ravno po
  // ravni, temni bazi pilot prepozna delujoč oblak.
  function drawCumulus(x, y, w, h) {
    ctx.save();
    var g = ctx.createLinearGradient(0, y - h * 0.6, 0, y + h * 0.55);
    g.addColorStop(0, 'rgba(255,255,255,.97)');
    g.addColorStop(0.62, 'rgba(238,244,250,.95)');
    g.addColorStop(1, 'rgba(178,193,211,.92)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.ellipse(x, y - h * 0.10, w * 0.40, h * 0.52, 0, 0, Math.PI * 2);
    ctx.ellipse(x - w * 0.27, y + h * 0.10, w * 0.29, h * 0.40, 0, 0, Math.PI * 2);
    ctx.ellipse(x + w * 0.29, y + h * 0.08, w * 0.31, h * 0.42, 0, 0, Math.PI * 2);
    ctx.ellipse(x - w * 0.08, y + h * 0.20, w * 0.34, h * 0.34, 0, 0, Math.PI * 2);
    ctx.fill();
    // Ravna, temnejša baza.
    ctx.fillStyle = 'rgba(120,140,166,.55)';
    ctx.beginPath();
    ctx.ellipse(x, y + h * 0.36, w * 0.44, h * 0.13, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // Grebeni v ozadju: dve plasti z različno paralakso. Ena sama ploskev je
  // bila videti kot prazna klanina — z dvema dolina dobi globino.
  // Grebeni v ozadju NISO izpeljani iz profila poti: ta opisuje dno doline, po
  // katerem letimo, ne gora ob njej. Ko sem jih poskusil dobiti z raztegom
  // profila, so se skrili za bližnje pobočje (ali pa zrasli čez vse nebo).
  // Zato so lastna silhueta — vsota treh sinusov, determinističnih iz svetovne
  // lege, v višinskem pasu, ki ustreza obronkom Savinjske doline.
  // Vrhovi ostajajo v pasu ~650–1100 m: obronki Savinjske doline se nad dnom
  // dvignejo za nekaj sto metrov, ne za kilometer in pol. Z večjimi amplitudami
  // je greben zapolnil zgornjo polovico zaslona in šel celo čez sonce.
  var RIDGES = [
    { par: 0.55, base: 880, a: [130, 62, 30, 13], f: [0.55, 1.30, 2.90, 6.70],
      p: [0.7, 2.1, 4.3, 1.2], col: 'rgba(104,142,180,.40)' },
    { par: 0.76, base: 690, a: [105, 50, 24, 11], f: [0.80, 1.90, 3.70, 8.30],
      p: [1.9, 0.4, 3.1, 5.6], col: 'rgba(56,92,126,.54)' }
  ];
  function ridgeElev(km, L) {
    // Četrti, visokofrekvenčni člen da grebenu robatost — s tremi je bil
    // videti kot sipina, ne kot hrib.
    return L.base
      + Math.sin(km * L.f[0] + L.p[0]) * L.a[0]
      + Math.sin(km * L.f[1] + L.p[1]) * L.a[1]
      + Math.sin(km * L.f[2] + L.p[2]) * L.a[2]
      + Math.sin(km * L.f[3] + L.p[3]) * L.a[3];
  }
  function drawRidges(cam) {
    for (var li = 0; li < RIDGES.length; li++) {
      var L = RIDGES[li];
      ctx.fillStyle = L.col;
      ctx.beginPath();
      ctx.moveTo(-2, H + 8);
      for (var px = -2; px <= W + 2; px += 10) {
        var km = (cam.x * L.par + px / W * VIEW_W) / 1000;
        ctx.lineTo(px, sy(ridgeElev(km, L), cam));
      }
      ctx.lineTo(W + 2, H + 8);
      ctx.closePath(); ctx.fill();
    }
  }

  // Stebri: mehak stožec PLUS dvigajoči se delci. Sam preliv je bil amorfna
  // packa; delci povedo tudi, kako močno vleče — hitrost dviga je sorazmerna
  // moči stebra, tako kot pri variu.
  function drawThermals(cam, l) {
    // Ob modrem dnevu so stebri komaj zaznavni — takrat se leti po variu in
    // po terenu, ne po očeh. Prav to je razlika, ki jo igra uči. Čisto
    // nevidni pa ne smejo biti: pravi pilot ima ob modrem dnevu namige, ki
    // jih tu ni mogoče narisati (ptice, druga padala, občutek krila).
    var vis = l.baza_m ? 0.16 : 0.08;
    var offLow = clamp(sim.tiltPerM * 150, -2.5, 2.5);
    var offHigh = clamp(sim.tiltPerM * sim.ceilAGLref, -2.5, 2.5);
    var ty = sy(sim.ceilASL, cam);
    for (var i = 0; i < sim.thermals.length; i++) {
      var t = sim.thermals[i];
      var xb = sx((t.km + offLow) * 1000, cam), xt = sx((t.km + offHigh) * 1000, cam);
      if (Math.max(xb, xt) < -200 || Math.min(xb, xt) > W + 200) continue;
      var gy = sy(terrainAt(sim, t.km), cam);
      var wb = t.r0 * 0.7 / VIEW_W * W, wt = t.r0 * 1.5 / VIEW_W * W;
      var rel = clamp(t.moc / Math.max(l.termika_ms, 0.1), 0, 1.5);
      var gr = ctx.createLinearGradient(0, gy, 0, ty);
      gr.addColorStop(0, 'rgba(255,196,90,0)');
      gr.addColorStop(0.35, 'rgba(255,196,90,' + (vis * rel).toFixed(3) + ')');
      gr.addColorStop(1, 'rgba(255,196,90,0)');
      ctx.fillStyle = gr;
      ctx.beginPath();
      ctx.moveTo(xb - wb, gy); ctx.lineTo(xt - wt, ty);
      ctx.lineTo(xt + wt, ty); ctx.lineTo(xb + wb, gy);
      ctx.closePath(); ctx.fill();

      if (reduceMotion) continue;
      // Delci se dvigajo od tal proti stropu; hitrejši so v močnejšem stebru.
      var n = 7, span = gy - ty;
      if (span <= 0) continue;
      ctx.fillStyle = 'rgba(255,222,150,' + (0.30 + 0.34 * (l.baza_m ? 1 : 0.45)).toFixed(2) + ')';
      for (var k = 0; k < n; k++) {
        var ph = ((sim.simTime * (0.05 + 0.045 * rel) + k / n + i * 0.37) % 1);
        var py = gy - span * ph;
        var f = ph;                                   // delež poti navzgor
        var pw = wb + (wt - wb) * f;
        var px2 = (xb + (xt - xb) * f) + Math.sin((ph * 7 + i) * 2.1) * pw * 0.42;
        var rr = 1.5 + 1.6 * rel * (1 - f * 0.5);
        ctx.globalAlpha = Math.sin(Math.PI * ph) * 0.9;
        ctx.beginPath(); ctx.arc(px2, py, rr, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
  }

  function drawTerrain(cam) {
    // Sam profil.
    var pts = [], step = 4;
    for (var p = -2; p <= W + 2; p += step) {
      pts.push([p, sy(terrainAt(sim, (cam.x + p / W * VIEW_W) / 1000), cam)]);
    }
    var g = ctx.createLinearGradient(0, sy(1500, cam), 0, H);
    g.addColorStop(0, '#3c5a3f');
    g.addColorStop(0.45, '#24402a');
    g.addColorStop(1, '#14251a');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(-2, H + 8);
    for (var i = 0; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.lineTo(W + 2, H + 8);
    ctx.closePath(); ctx.fill();

    // Sončni rob na grebenu.
    ctx.strokeStyle = 'rgba(150,205,150,.55)';
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    for (var j = 0; j < pts.length; j++) {
      if (j === 0) ctx.moveTo(pts[j][0], pts[j][1]); else ctx.lineTo(pts[j][0], pts[j][1]);
    }
    ctx.stroke();

    drawForest(cam);
    drawPlaces(cam);
  }

  // Gozd: drobni stožci, pripeti na SVETOVNE koordinate (ne na piksle), da ob
  // premikanju ne migotajo. Le nad ~420 m — nižje je dolina s polji.
  function drawForest(cam) {
    if (W < 340) return;
    var stepM = 55;
    var from = Math.floor(cam.x / stepM) * stepM;
    ctx.fillStyle = 'rgba(20,48,28,.85)';
    for (var m = from; m < cam.x + VIEW_W + stepM; m += stepM) {
      var km = m / 1000;
      var e = terrainAt(sim, km);
      if (e < 420) continue;
      // Determinističen odmik iz svetovne lege — brez naključja na okvir.
      var j = Math.sin(m * 0.017) * 0.5 + 0.5;
      var x = sx(m + j * stepM * 0.7, cam);
      if (x < -8 || x > W + 8) continue;
      var y = sy(e, cam);
      var h = 5 + j * 5;
      ctx.beginPath();
      ctx.moveTo(x, y - h);
      ctx.lineTo(x - h * 0.36, y + 1.5);
      ctx.lineTo(x + h * 0.36, y + 1.5);
      ctx.closePath(); ctx.fill();
    }
  }

  function drawPlaces(cam) {
    ctx.font = '600 11px system-ui,sans-serif';
    ctx.textAlign = 'center';
    for (var i = 0; i < sim.places.length; i++) {
      var pl = sim.places[i], x = sx(pl.km * 1000, cam);
      if (x < -70 || x > W + 70) continue;
      var y = sy(terrainAt(sim, pl.km), cam);
      var g = ctx.createLinearGradient(0, y - 46, 0, y);
      g.addColorStop(0, 'rgba(255,255,255,0)');
      g.addColorStop(1, 'rgba(255,255,255,.34)');
      ctx.fillStyle = g;
      ctx.fillRect(x - 0.5, y - 46, 1, 46);
      ctx.fillStyle = 'rgba(255,255,255,.95)';
      ctx.beginPath(); ctx.arc(x, y, 2.4, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = 'rgba(238,243,252,.94)';
      ctx.fillText(pl.ime, x, y - 52);
      ctx.fillStyle = 'rgba(238,243,252,.5)';
      ctx.font = '500 10px "JetBrains Mono",ui-monospace,monospace';
      ctx.fillText(fmt(pl.km, 1) + ' km', x, y - 41);
      ctx.font = '600 11px system-ui,sans-serif';
    }
    ctx.textAlign = 'left';
  }

  function drawRain(l) {
    if (reduceMotion) return;
    var n = Math.round(clamp(l.padavine_mm, 0.2, 4) * 20);
    ctx.strokeStyle = 'rgba(190,214,240,.40)'; ctx.lineWidth = 1;
    ctx.beginPath();
    for (var i = 0; i < n; i++) {
      var x = Math.random() * W, y = Math.random() * H;
      ctx.moveTo(x, y); ctx.lineTo(x - 3, y + 11);
    }
    ctx.stroke();
  }

  // Sled leta, obarvana po dvigu/spustu v tistem trenutku. Ni le okras: na
  // njej vidiš, kje si pridobival in kje zapravljal — barogram med letom.
  function drawTrail(cam) {
    var tr = ui.trail;
    if (tr.length < 2) return;
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    for (var i = 1; i < tr.length; i++) {
      var a = tr[i - 1], b = tr[i];
      var ax = sx(a.km * 1000, cam), bx = sx(b.km * 1000, cam);
      if ((ax < -20 && bx < -20) || (ax > W + 20 && bx > W + 20)) continue;
      var age = i / tr.length;                       // 0 = najstarejši
      var up = b.vz > 0.15, down = b.vz < -1.5;
      ctx.strokeStyle = (up ? 'rgba(52,211,153,' : (down ? 'rgba(248,113,113,' : 'rgba(226,236,250,'))
        + (0.10 + 0.42 * age).toFixed(2) + ')';
      ctx.beginPath();
      ctx.moveTo(ax, sy(a.alt, cam));
      ctx.lineTo(bx, sy(b.alt, cam));
      ctx.stroke();
    }
  }

  function drawGlider(cam) {
    var x = sx(sim.km * 1000, cam), y = sy(sim.alt, cam);
    var circling = ui.mode === 'circle';
    // Med kroženjem se krilo nagiba; pri pospeševalniku se spusti naprej.
    var bank = circling ? Math.sin(sim.simTime * 0.5) * 0.42
      : (ui.mode === 'fast' ? 0.17 : 0.05);
    // Navidezno skrajšanje krila, ko je obrnjeno stran — iz tega nastane
    // občutek kroženja, ne le zibanja.
    var squash = circling ? (0.35 + 0.65 * Math.abs(Math.cos(sim.simTime * 0.5))) : 1;

    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(bank);
    ctx.scale(squash, 1);

    // Kupola z rebri.
    var kg = ctx.createLinearGradient(0, -17, 0, -7);
    kg.addColorStop(0, '#ffe08a');
    kg.addColorStop(1, '#f0a52e');
    ctx.fillStyle = kg;
    ctx.beginPath();
    ctx.moveTo(-15, -8);
    ctx.quadraticCurveTo(0, -19, 15, -8);
    ctx.quadraticCurveTo(0, -13.5, -15, -8);
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = 'rgba(120,72,10,.35)'; ctx.lineWidth = 0.7;
    for (var c = -2; c <= 2; c++) {
      var cx = c * 5.4;
      ctx.beginPath();
      ctx.moveTo(cx, -8.6);
      ctx.lineTo(cx * 0.92, -13.6 + Math.abs(c) * 1.1);
      ctx.stroke();
    }
    // Vrvi.
    ctx.strokeStyle = 'rgba(255,255,255,.5)'; ctx.lineWidth = 0.9;
    ctx.beginPath();
    ctx.moveTo(-11.5, -7.6); ctx.lineTo(-0.6, 4);
    ctx.moveTo(-4, -8.6); ctx.lineTo(-0.6, 4);
    ctx.moveTo(11.5, -7.6); ctx.lineTo(0.6, 4);
    ctx.moveTo(4, -8.6); ctx.lineTo(0.6, 4);
    ctx.stroke();
    ctx.restore();

    // Pilot v sedežu — brez raztega, da ostane okrogel.
    ctx.save();
    ctx.translate(x, y); ctx.rotate(bank * 0.55);
    ctx.fillStyle = '#dfe7f5';
    ctx.beginPath();
    if (ctx.roundRect) { ctx.roundRect(-3.4, 3.2, 6.8, 6.4, 2.6); }
    else { ctx.arc(0, 6.4, 3.3, 0, Math.PI * 2); }
    ctx.fill();
    ctx.fillStyle = '#a8b6cc';
    ctx.beginPath(); ctx.arc(0, 3.4, 2.1, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  // ── Inštrumenti ────────────────────────────────────────────────────────
  function drawInstruments(cam) {
    drawVario();
    drawWindBadge(cam);
    if (sim.atCeiling) {
      var t = 'BAZA OBLAKOV — višje ne gre';
      ctx.font = '700 12px system-ui,sans-serif';
      var w = ctx.measureText(t).width;
      ctx.fillStyle = 'rgba(4,7,14,.55)';
      if (ctx.roundRect) {
        ctx.beginPath(); ctx.roundRect(W / 2 - w / 2 - 9, 9, w + 18, 21, 10); ctx.fill();
      } else ctx.fillRect(W / 2 - w / 2 - 9, 9, w + 18, 21);
      ctx.fillStyle = 'rgba(255,209,102,.98)';
      ctx.textAlign = 'center';
      ctx.fillText(t, W / 2, 24);
      ctx.textAlign = 'left';
    }
  }

  // Vario kot pravi inštrument: razdelki na ±1..±5, sredinska os, obarvani
  // coni. Gol pravokotnik ni povedal, ali je 2 m/s veliko ali malo.
  function drawVario() {
    var bw = 15, bh = Math.min(190, H - 86), bx = W - bw - 16, by = 40;
    var mid = by + bh / 2, half = bh / 2;
    ctx.save();
    ctx.fillStyle = 'rgba(4,7,14,.48)';
    if (ctx.roundRect) { ctx.beginPath(); ctx.roundRect(bx - 5, by - 5, bw + 10, bh + 10, 9); ctx.fill(); }
    else ctx.fillRect(bx - 5, by - 5, bw + 10, bh + 10);

    // Blaga cona dviga/spusta v ozadju.
    ctx.fillStyle = 'rgba(52,211,153,.10)'; ctx.fillRect(bx, by, bw, half);
    ctx.fillStyle = 'rgba(248,113,113,.10)'; ctx.fillRect(bx, mid, bw, half);

    var v = clamp(sim.vario, -5, 5);
    var hgt = (v / 5) * half;
    var vg = ctx.createLinearGradient(bx, mid - hgt, bx, mid);
    if (v >= 0) { vg.addColorStop(0, '#6ee7b7'); vg.addColorStop(1, '#10b981'); }
    else { vg.addColorStop(0, '#ef4444'); vg.addColorStop(1, '#fca5a5'); }
    ctx.fillStyle = vg;
    if (v >= 0) ctx.fillRect(bx, mid - hgt, bw, hgt);
    else ctx.fillRect(bx, mid, bw, -hgt);

    // Razdelki. Številke gredo LEVO od plošče, ne vanjo — v stolpcu so se
    // zlivale z barvnim stanjem in bile neberljive.
    ctx.font = '500 9px "JetBrains Mono",ui-monospace,monospace';
    ctx.textAlign = 'right';
    for (var k = -5; k <= 5; k++) {
      var y = mid - (k / 5) * half;
      var major = (k % 2 === 0);
      ctx.strokeStyle = 'rgba(255,255,255,' + (major ? .45 : .22) + ')';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(bx + bw - (major ? 7 : 4), y); ctx.lineTo(bx + bw, y); ctx.stroke();
      if (major && k !== 0) {
        ctx.fillStyle = 'rgba(4,7,14,.5)';
        ctx.fillText(String(Math.abs(k)), bx - 9.5, y + 3.5);
        ctx.fillStyle = 'rgba(232,237,248,.62)';
        ctx.fillText(String(Math.abs(k)), bx - 10, y + 3);
      }
    }
    ctx.strokeStyle = 'rgba(255,255,255,.7)'; ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.moveTo(bx - 5, mid); ctx.lineTo(bx + bw + 5, mid); ctx.stroke();

    // Odčitek.
    ctx.font = '700 11px "JetBrains Mono",ui-monospace,monospace';
    ctx.fillStyle = sim.vario > 0.2 ? '#6ee7b7' : (sim.vario < -1.5 ? '#fca5a5' : 'rgba(232,237,248,.9)');
    ctx.fillText(fmt(sim.vario, 1), bx + bw + 5, by + bh + 17);
    ctx.font = '500 8px system-ui,sans-serif';
    ctx.fillStyle = 'rgba(232,237,248,.5)';
    ctx.fillText('m/s', bx + bw + 5, by + bh + 27);
    ctx.textAlign = 'left';
    ctx.restore();
  }

  // Veter na trenutni višini — puščica pove smer, dolžina jakost.
  function drawWindBadge(cam) {
    var u = windAt(sim, Math.max(0, sim.alt - terrainAt(sim, sim.km)));
    var kmh = Math.abs(u) * 3.6;
    var txt = fmt(kmh, 0) + ' km/h';
    ctx.font = '600 11px "JetBrains Mono",ui-monospace,monospace';
    var tw = ctx.measureText(txt).width;
    var bw2 = tw + 34, bx = 12, by = 12;
    ctx.fillStyle = 'rgba(4,7,14,.45)';
    if (ctx.roundRect) { ctx.beginPath(); ctx.roundRect(bx, by, bw2, 20, 10); ctx.fill(); }
    else ctx.fillRect(bx, by, bw2, 20);
    var ax = bx + 13, ay = by + 10, dir = u >= 0 ? 1 : -1;
    var len = 5 + clamp(kmh / 4, 0, 7);
    ctx.strokeStyle = u >= 0 ? 'rgba(125,211,252,.95)' : 'rgba(253,186,116,.95)';
    ctx.lineWidth = 1.8; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(ax - dir * len * 0.5, ay); ctx.lineTo(ax + dir * len * 0.5, ay);
    ctx.moveTo(ax + dir * len * 0.5, ay); ctx.lineTo(ax + dir * (len * 0.5 - 3.4), ay - 3);
    ctx.moveTo(ax + dir * len * 0.5, ay); ctx.lineTo(ax + dir * (len * 0.5 - 3.4), ay + 3);
    ctx.stroke();
    ctx.fillStyle = 'rgba(232,237,248,.92)';
    ctx.fillText(txt, bx + 24, by + 14);
  }

  // ── Zanka ──────────────────────────────────────────────────────────────
  function frame(ts) {
    requestAnimationFrame(frame);
    if (!ui.lastTs) ui.lastTs = ts;
    var dt = Math.min(0.25, (ts - ui.lastTs) / 1000);
    ui.lastTs = ts;

    if (ui.phase === 'flying' && sim && !document.hidden) {
      ui.acc += dt * TIME_SCALE;
      var guard = 0, ctrl = { mode: ui.mode, nudge: ui.nudge };
      while (ui.acc >= FIXED_DT && ui.phase === 'flying' && guard++ < 400) {
        if (stepFixed(sim, ctrl, FIXED_DT) !== 'flying') { endFlight(); break; }
        ui.acc -= FIXED_DT;
        ui.trailAcc += FIXED_DT;
        if (ui.trailAcc >= TRAIL_EVERY) {
          ui.trailAcc = 0;
          ui.trail.push({ km: sim.km, alt: sim.alt, vz: sim.vario });
          if (ui.trail.length > TRAIL_MAX) ui.trail.shift();
        }
      }
      if (sim.level.turbulenca > 0.35) ui.shake = Math.min(1, sim.level.turbulenca - 0.3);
      ui.shake *= 0.93;
      updateHud();
      beep(dt);
    }
    ui.frameNo++;
    // Na dotičnih napravah rišemo vsak drugi okvir; fizika teče vedno.
    if (!(ui.frameNo % 2 && navigator.maxTouchPoints > 0)) draw();
  }

  // ── HUD ────────────────────────────────────────────────────────────────
  function el(id) { return document.getElementById(id); }
  function setTxt(id, v) { var e = el(id); if (e) e.textContent = v; }

  function updateHud() {
    setTxt('pg-km', fmt(sim.km, 1));
    setTxt('pg-alt', Math.round(sim.alt));
    setTxt('pg-agl', Math.round(Math.max(0, sim.alt - terrainAt(sim, sim.km))));
    setTxt('pg-vario', fmt(sim.vario, 1));
    var v = el('pg-vario');
    if (v) v.className = 'pg-v' + (sim.vario > 0.2 ? ' up' : (sim.vario < -1.5 ? ' down' : ''));
    setTxt('pg-time', Math.floor(sim.simTime / 60) + ' min');
    var pct = clamp(sim.km / sim.endKm, 0, 1) * 100;
    var f = el('pg-route-fill'), m = el('pg-route-mark');
    if (f) f.style.width = pct.toFixed(1) + '%';
    if (m) m.style.left = pct.toFixed(1) + '%';
  }

  // Pike na traku so kraji iz nivoja — postavimo jih enkrat ob nalaganju.
  // Tudi konca traku: koridor se z vremenom menja, zato ne smeta biti
  // trdo zapisana v HTML.
  function buildRoute() {
    var bar = el('pg-route-bar');
    if (!bar) return;
    var p = sim.places;
    setTxt('pg-route-a', p.length ? p[0].ime : 'Golte');
    setTxt('pg-route-b', p.length ? p[p.length - 1].ime : '');
    var old = bar.querySelectorAll('.pg-route-tick');
    for (var i = 0; i < old.length; i++) bar.removeChild(old[i]);
    for (var j = 1; j < sim.places.length; j++) {
      var d = document.createElement('i');
      d.className = 'pg-route-tick';
      d.style.left = (clamp(sim.places[j].km / sim.endKm, 0, 1) * 100).toFixed(1) + '%';
      d.title = sim.places[j].ime;
      bar.appendChild(d);
    }
  }

  function renderConditions() {
    var l = sim.level, kor = l.koridor || {};
    setTxt('pg-c-korridor', kor.ime || '—');
    setTxt('pg-c-ceiling', Math.round(sim.ceilASL) + ' m');
    setTxt('pg-c-lift', fmt(l.termika_ms || 0, 1) + ' m/s');
    setTxt('pg-c-wind', fmt(l.veter_kmh || 0, 0) + ' km/h ' + dirLabel(l.veter_smer));
    setTxt('pg-c-cross', fmt((l.veter_precno_ms || 0) * 3.6, 0) + ' km/h');
    setTxt('pg-c-zi', Math.round(l.z_i_m || 0) + ' m');
    setTxt('pg-c-turb', fmt(l.turbulenca || 0, 2));
    setTxt('pg-c-spacing', fmt(l.gostota_km || 0, 1) + ' km');
    var src = el('pg-source');
    if (!src) return;
    var txt;
    if (ui.vir === 'vadba') {
      txt = '🔴 Vadbeni dan — današnjih razmer ni bilo mogoče pridobiti.';
    } else {
      txt = (ui.svez && ui.svez.ikona ? ui.svez.ikona + ' ' : '') +
        'Nivo dneva ' + (l.datum || '?') +
        (l.ura ? ' · vrhunec termike ob ' + l.ura : '') +
        (ui.vir === 'rezerva' ? ' · iz povprečnih razmer, napovedi ni bilo mogoče pridobiti'
          : (ui.vir === 'zastarel' ? ' · današnja napoved ni bila dosegljiva' : ''));
      if (ui.svez && ui.svez.ur !== null && ui.svez.ur > 26) {
        txt += ' · podatki niso sveži (' + Math.round(ui.svez.ur) + ' h)';
      }
    }
    src.textContent = txt;
    src.className = 'pg-source' +
      ((ui.vir !== 'open-meteo' || (ui.svez && ui.svez.ur > 26)) ? ' warn' : '');
  }

  function announce(msg) { var e = el('pg-live'); if (e) e.textContent = msg; }

  // ── Prekrivno okno ─────────────────────────────────────────────────────
  function showOverlay(kind) {
    var ov = el('pg-overlay');
    if (!ov) return;
    ov.hidden = false;
    if (kind === 'ready') {
      var r = dayRating();
      ov.innerHTML = '<div class="pg-ov-in">' +
        '<p class="pg-ov-kicker">Nivo dneva' +
        (sim.level.datum ? ' · ' + esc(sim.level.datum) : '') + '</p>' +
        '<h2 class="pg-ov-title">' + esc(r.title) + '</h2>' +
        '<p class="pg-ov-smer">' + esc(smerBesedilo()) + '</p>' +
        '<p class="pg-ov-sub">' + esc(r.sub) + '</p>' +
        '<button class="pg-start" id="pg-start" type="button">Vzleti z Golt</button>' +
        '<p class="pg-ov-help">Drži <b>Kroži</b>, ko vario kaže dvig · spusti in drsi naprej' +
        ' · <b>Pospeši</b> proti vetru in skozi spust</p></div>';
      var b = el('pg-start');
      if (b) { b.addEventListener('click', startFlight); b.focus(); }
    } else {
      var best = loadBest(), rec = sim.best > best.km + 0.049;
      if (rec) saveBest(sim.best, sim.level.datum || '');
      ov.innerHTML = '<div class="pg-ov-in">' +
        '<p class="pg-ov-kicker">' +
        (sim.status === 'finished' ? 'Prelet dokončan' : 'Pristanek') + '</p>' +
        '<h2 class="pg-ov-title">' + fmt(sim.best, 1) + ' km</h2>' +
        '<p class="pg-ov-sub">' + esc(distanceComment()) + '</p>' +
        (rec ? '<p class="pg-ov-rec">🏅 Nov osebni rekord</p>'
          : '<p class="pg-ov-sub pg-small">Osebni rekord: ' + fmt(best.km, 1) + ' km' +
          (best.date ? ' (' + esc(best.date) + ')' : '') + '</p>') +
        '<div class="pg-ov-btns">' +
        '<button class="pg-start" id="pg-again" type="button">Še enkrat</button>' +
        '<button class="pg-share" id="pg-share" type="button">Deli rezultat</button></div>' +
        '<p class="pg-ov-help" id="pg-share-note"></p></div>';
      var a = el('pg-again'); if (a) { a.addEventListener('click', startFlight); a.focus(); }
      var s = el('pg-share'); if (s) s.addEventListener('click', share);
      announce('Pristanek. Preleteno ' + fmt(sim.best, 1) + ' kilometrov.' +
        (sim.reached ? ' Najdlje do kraja ' + sim.reached + '.' : ''));
    }
  }
  function hideOverlay() { var ov = el('pg-overlay'); if (ov) ov.hidden = true; }

  // Katera smer in zakaj. To je poanta koridorjev: smeri ne izbereš ti,
  // izbere jo veter — enako kot pilot, ki se zjutraj odloči, kam bo letel.
  function smerBesedilo() {
    var kor = sim.level.koridor;
    if (!kor || !kor.ime) return '';
    var h = kor.hrbtnik_kmh;
    if (h === null || h === undefined) return kor.ime;
    if (h > 3) return kor.ime + ' — veter na višini te nese tja (' + fmt(h, 0) + ' km/h v hrbet).';
    if (h > -1) return kor.ime + ' — veter ne pomaga in ne ovira; danes šteje samo termika.';
    return kor.ime + ' — vse smeri so proti vetru, ta je najmanj slaba (' +
      fmt(Math.abs(h), 0) + ' km/h čelno).';
  }

  // Ocena dneva ZA IGRO — koliko višine ti dan podari. To NI priletnost:
  // tisto meri fly_score() in je izpisana v strežniškem delu strani.
  function dayRating() {
    var l = sim.level;
    var climb = (l.termika_ms || 0) - sinkAt(V_CIRCLE) * BANK_PENALTY;
    var strop = Math.round(sim.ceilASL);
    if (l.koda_vremena === 45 || l.koda_vremena === 48) {
      return { title: 'Megla', sub: 'Sonce ne pride do tal, termike ni. Z Golt lahko samo zdrsneš v sivino.' };
    }
    if ((l.padavine_mm || 0) > 1.2) {
      return { title: 'Dežuje', sub: 'Termika je zbita, zrak pada. Danes gre za preživetje prvih kilometrov.' };
    }
    if (strop < 1400) {
      return {
        title: 'Nizek strop', sub: 'Konvekcija seže le do ' + strop +
          ' m — to je pod vzletiščem. Z Golt boš najprej samo padal; loviti se začne šele v dolini.'
      };
    }
    if (climb < 0.3) return { title: 'Mrtev zrak', sub: 'Dvigov skoraj ni. Vprašanje ni, kako visoko, ampak kako daleč prideš z eno samo višino.' };
    if (climb < 1.0) return { title: 'Šibek dan', sub: 'Dvigi okoli ' + fmt(climb, 1) + ' m/s. Vsak steber šteje, nobene višine ne smeš zapraviti.' };
    if (climb < 2.0) return { title: 'Soliden dan', sub: 'Dvigi okoli ' + fmt(climb, 1) + ' m/s, strop ' + strop + ' m. Dolina je odprta.' };
    if (climb < 3.0) return { title: 'Dober dan', sub: 'Dvigi ' + fmt(climb, 1) + ' m/s do ' + strop + ' m. Za dober kos koridorja je dovolj — če ne zgrešiš stebrov.' };
    return { title: 'Odličen dan', sub: 'Dvigi ' + fmt(climb, 1) + ' m/s, strop ' + strop + ' m. Danes je konec koridorja na dosegu.' };
  }

  // Komentar ob pristanku se ravna po MEJNIKIH koridorja, ne po pribitih
  // kilometrih: proti Celju jih je 42, čez Raduho 11,5 — »do Rečice« pri
  // koridorju na Koroško ne pomeni nič.
  function distanceComment() {
    if (sim.status === 'finished') {
      return 'Preletel si ves koridor do konca. Tak dan si zapomniš.';
    }
    var zadnji = null, naslednji = null;
    for (var i = 0; i < sim.places.length; i++) {
      if (sim.best >= sim.places[i].km) zadnji = sim.places[i];
      else { naslednji = sim.places[i]; break; }
    }
    var t = '';
    if (!zadnji || zadnji.km <= 0.01) {
      t = sim.best < 3
        ? 'Takoj po vzletu na tla. Poišči dvig, preden izgubiš višino.'
        : 'Pristanek še pod vzletiščem — prvega stebra nisi ujel.';
    } else if (!naslednji) {
      t = 'Prišel si mimo zadnjega mejnika (' + zadnji.ime + '). To je bil dober prelet.';
    } else {
      t = 'Najdlje do kraja ' + zadnji.ime + '. Do naslednjega (' + naslednji.ime +
        ') ti je zmanjkalo ' + fmt(naslednji.km - sim.best, 1) + ' km.';
    }
    var delez = Math.round(clamp(sim.best / sim.endKm, 0, 1) * 100);
    return t + ' Prehodil si ' + delez + ' % koridorja.';
  }

  // ── Rekord ─────────────────────────────────────────────────────────────
  // Rekord se vodi PO KORIDORJIH. Koridorji so različno dolgi (proti Celju 44
  // km, proti Črni 14), zato en sam skupni rekord ne bi pomenil nič — 20 km
  // čez Raduho je nekaj čisto drugega kot 20 km po ravni dolini.
  var LS = 'wx-igra-rekord';
  function korId() {
    return (sim && sim.level && sim.level.koridor && sim.level.koridor.id) || 'celje';
  }
  function loadAllBest() {
    try {
      var d = JSON.parse(localStorage.getItem(LS) || '{}');
      // Stara oblika ({km, date}) je bila iz časa ene same poti — ta je bila
      // vedno Savinjska proti Celju, zato se preseli tja.
      if (typeof d.km === 'number') d = { celje: { km: d.km, date: d.date || '' } };
      return d && typeof d === 'object' ? d : {};
    } catch (e) { return {}; }
  }
  function loadBest() {
    var r = loadAllBest()[korId()] || {};
    return { km: +r.km || 0, date: r.date || '' };
  }
  function saveBest(km, date) {
    try {
      var vse = loadAllBest();
      vse[korId()] = { km: Math.round(km * 10) / 10, date: date };
      localStorage.setItem(LS, JSON.stringify(vse));
      setTxt('pg-best', fmt(km, 1) + ' km');
    } catch (e) { /* zaseben zavihek ali polna shramba — rekord pač ne ostane */ }
  }

  // ── Deljenje ───────────────────────────────────────────────────────────
  function shareText() {
    var l = sim.level, n = 8;
    var done = Math.round(clamp(sim.best / sim.endKm, 0, 1) * n), bar = '';
    for (var i = 0; i < n; i++) bar += (i < done ? '🟩' : '⬜');
    var kor = l.koridor || {};
    return '🪂 Meteorec — Termika ' + (l.datum || '') + '\n' +
      (kor.kratko ? 'Smer dneva: ' + kor.kratko + '\n' : '') +
      'Golte → ' + (sim.reached || 'pod Goltami') + ' · ' + fmt(sim.best, 1) + ' km\n' +
      bar + '\n' +
      'Strop ' + Math.round(sim.ceilASL) + ' m · dvigi ' + fmt(l.termika_ms || 0, 1) +
      ' m/s · veter ' + fmt(l.veter_kmh || 0, 0) + ' km/h ' + dirLabel(l.veter_smer) + '\n' +
      'https://meteorec.si/igra/';
  }
  function share() {
    var txt = shareText(), note = el('pg-share-note');
    if (navigator.share) {
      navigator.share({ text: txt })
        .then(function () { if (note) note.textContent = 'Deljeno.'; })
        .catch(function () { copy(txt, note); });
    } else { copy(txt, note); }
  }
  function copy(txt, note) {
    var ok = function () { if (note) note.textContent = 'Rezultat je v odložišču — prilepi ga, kamor želiš.'; };
    var no = function () { if (note) note.textContent = 'Kopiranje ni uspelo.'; };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(ok).catch(no);
    } else {
      try {
        var ta = document.createElement('textarea');
        ta.value = txt; ta.setAttribute('readonly', '');
        ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); document.body.removeChild(ta); ok();
      } catch (e) { no(); }
    }
  }

  // ── Zvok ───────────────────────────────────────────────────────────────
  // Vario pisk je duša jadralnega padalstva, a nihče ne mara strani, ki sama
  // zapiska — privzeto izklopljen, vklopi ga gumb (in s tem uporabnikova
  // poteza, kar brskalniki tako ali tako zahtevajo).
  var audio = { on: false, ac: null, next: 0 };
  function beep(dt) {
    if (!audio.on || !audio.ac) return;
    audio.next -= dt;
    if (audio.next > 0) return;
    if (sim.vario < 0.2) { audio.next = 0.25; return; }
    var v = clamp(sim.vario, 0, 5);
    audio.next = Math.max(0.09, 0.44 - v * 0.065);
    try {
      var o = audio.ac.createOscillator(), g = audio.ac.createGain();
      o.type = 'square'; o.frequency.value = 620 + v * 190;
      g.gain.value = 0.035;
      o.connect(g); g.connect(audio.ac.destination);
      var t0 = audio.ac.currentTime;
      o.start(t0); o.stop(t0 + 0.06);
    } catch (e) { audio.on = false; }
  }
  function toggleSound() {
    var b = el('pg-btn-sound');
    if (!audio.ac) {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) { if (b) b.disabled = true; return; }
      try { audio.ac = new AC(); } catch (e) { if (b) b.disabled = true; return; }
    }
    if (audio.ac.state === 'suspended') audio.ac.resume();
    audio.on = !audio.on;
    if (b) {
      b.setAttribute('aria-pressed', audio.on ? 'true' : 'false');
      b.textContent = audio.on ? '🔊 Vario' : '🔇 Vario';
    }
  }

  // ── Krmiljenje ─────────────────────────────────────────────────────────
  function applyMode() {
    ui.mode = held.circle ? 'circle' : (held.fast ? 'fast' : 'glide');
    var bc = el('pg-btn-circle'), bf = el('pg-btn-speed');
    if (bc) bc.classList.toggle('on', held.circle);
    if (bf) bf.classList.toggle('on', held.fast);
  }

  function startFlight() {
    if (!sim) return;
    resetSim(sim);
    hideOverlay();
    ui.phase = 'flying'; ui.lastTs = 0; ui.acc = 0;
    ui.trail = []; ui.trailAcc = 0;
    held.circle = false; held.fast = false; ui.nudge = 0; applyMode();
    updateHud(); root.focus();
    announce('Vzlet z Golt.');
  }

  function endFlight() {
    ui.phase = 'over';
    held.circle = false; held.fast = false; ui.nudge = 0; applyMode();
    updateHud();
    showOverlay('over');
  }

  // Držalna površina: gumb ali kar samo platno. Kazalec zajamemo, sicer bi
  // vodoravno vlečenje (popravek lege) zdrsnilo z gumba in kroženje bi se
  // sredi termike prekinilo.
  function bindHold(surface, key) {
    if (!surface) return;
    var down = function (e) {
      if (ui.phase !== 'flying') return;
      e.preventDefault();
      if (surface.setPointerCapture && e.pointerId !== undefined) {
        try { surface.setPointerCapture(e.pointerId); } catch (err) { /* ni bistveno */ }
      }
      held[key] = true; applyMode(); root.focus();
    };
    var up = function (e) {
      if (!held[key]) return;
      e.preventDefault();
      held[key] = false;
      if (key === 'circle') ui.nudge = 0;
      applyMode();
    };
    surface.addEventListener('pointerdown', down);
    surface.addEventListener('pointerup', up);
    surface.addEventListener('pointercancel', up);
    surface.addEventListener('pointerleave', up);
    if (key === 'circle') {
      surface.addEventListener('pointermove', function (e) {
        if (!held.circle) return;
        var r = surface.getBoundingClientRect();
        ui.nudge = clamp((e.clientX - (r.left + r.width / 2)) / (r.width / 2), -1, 1);
      });
    }
  }

  function onKey(e, down) {
    // Tipke prevzamemo samo, kadar je igra v žarišču — sicer bi preslednica
    // obiskovalcu ugrabila drsenje po strani.
    if (!root.contains(document.activeElement)) return;
    var k = e.key;
    if (k === ' ' || k === 'Spacebar' || k === 'ArrowUp' || k === 'w' || k === 'W') {
      e.preventDefault();
      if (down && (ui.phase === 'ready' || ui.phase === 'over')) { startFlight(); return; }
      if (ui.phase !== 'flying') return;
      held.circle = down; applyMode();
    } else if (k === 'Shift' || k === 'd' || k === 'D') {
      if (ui.phase !== 'flying') return;
      e.preventDefault(); held.fast = down; applyMode();
    } else if (k === 'ArrowLeft' || k === 'a' || k === 'A') {
      if (ui.phase !== 'flying') return;
      e.preventDefault(); ui.nudge = down ? -1 : 0;
    } else if (k === 'ArrowRight') {
      if (ui.phase !== 'flying') return;
      e.preventDefault(); ui.nudge = down ? 1 : 0;
    }
  }

  // ── Zagon ──────────────────────────────────────────────────────────────
  function init() {
    resize();
    window.addEventListener('resize', resize);
    // Kroženje gre po gumbu IN po samem platnu — na telefonu je držanje prsta
    // na sliki najbolj naravno, gumb pa pove, da to sploh gre.
    bindHold(el('pg-btn-circle'), 'circle');
    bindHold(canvas, 'circle');
    bindHold(el('pg-btn-speed'), 'fast');
    var snd = el('pg-btn-sound');
    if (snd) snd.addEventListener('click', toggleSound);
    document.addEventListener('keydown', function (e) { onKey(e, true); });
    document.addEventListener('keyup', function (e) { onKey(e, false); });
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) { held.circle = false; held.fast = false; applyMode(); }
      ui.lastTs = 0;
    });

    var b = loadBest();
    if (b.km > 0) setTxt('pg-best', fmt(b.km, 1) + ' km');

    loadLevel();
    requestAnimationFrame(frame);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else { init(); }
})(typeof globalThis !== 'undefined' ? globalThis : this);
