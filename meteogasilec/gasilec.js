/*
 * meteogasilec/gasilec.js — skupna klientska logika za /meteogasilec/* strani
 * (naslovnica, /intervencija/). Statičen JS vir, ROČNO pisan (ni generiran).
 *
 * Zakaj ta datoteka obstaja: /meteogasilec/* strani ne nalagajo app.js (so
 * samostojne, self-contained — glej firms_widget_html() v
 * generate_gasilec_page.py). Nova operativna logika (kompas, obrat vetra,
 * freshness, briefing) bi brez tega postala tretja kopija iste stvari poleg
 * app.js in gasilec_model.py. Namesto tega je ena skupna datoteka za VSE
 * podstrani znotraj enega generatorja (generate_gasilec_page.py) — to ni v
 * nasprotju z "generatorji strani si ne delijo knjižnic" iz CLAUDE.md, tisto
 * pravilo velja med različnimi Python generatorji, ne med podstranmi istega.
 *
 * FWI izračun (_calcOneDayFWI/_fwiClass) je NAMERNA dobesedna kopija iz
 * app.js (~vrstica 14818) — enak dogovor kot gasilec_model.py že dokumentira
 * za Python stran: če spremeniš formulo/pragove na eni strani, popravi tudi
 * drugo (app.js, gasilec_model.py, ta datoteka).
 *
 * 16-smerna imena (GASILEC_DIRS) so zrcalna kopija _DIRS/_dir_label() iz
 * generate_gasilec_page.py — isto načelo.
 */
(function (global) {
  'use strict';

  // ── smeri vetra ────────────────────────────────────────────────────────
  var GASILEC_DIRS = ['S', 'SSV', 'SV', 'VSV', 'V', 'VJV', 'JV', 'JJV',
    'J', 'JJZ', 'JZ', 'ZJZ', 'Z', 'ZSZ', 'SZ', 'SSZ'];

  function dirLabel(deg) {
    if (deg == null || isNaN(deg)) return '—';
    var d = ((deg % 360) + 360) % 360;
    return GASILEC_DIRS[Math.round(d / 22.5) % 16];
  }

  // ── obrat vetra ────────────────────────────────────────────────────────
  function angleDiff(a, b) {
    return Math.abs(((b - a + 540) % 360) - 180);
  }

  var WIND_SHIFT_MIN_DEG = 45;
  var WIND_SHIFT_MIN_KMH = 15; // MeteoGasilec kriterij — pri skoraj brezvetrju obrat ni pomemben

  // times/speeds/gusts/dirs: sočasni urni nizi (Open-Meteo hourly). Vrne prvi
  // par ur v `horizonHours`, kjer se smer obrne za >=45° IN je veter/sunki na
  // vsaj eni strani nad pragom. To je MeteoGasilec kriterij, ne uradno ARSO
  // opozorilo.
  function detectWindShift(times, speeds, gusts, dirs, opts) {
    opts = opts || {};
    var horizon = Math.min(times.length, opts.horizonHours || 12);
    for (var i = 0; i < horizon - 1; i++) {
      for (var j = i + 1; j < horizon; j++) {
        var diff = angleDiff(dirs[i], dirs[j]);
        if (diff < WIND_SHIFT_MIN_DEG) continue;
        var strong = Math.max(speeds[i] || 0, gusts[i] || 0) >= WIND_SHIFT_MIN_KMH ||
          Math.max(speeds[j] || 0, gusts[j] || 0) >= WIND_SHIFT_MIN_KMH;
        if (!strong) continue;
        return {
          detected: true,
          fromTime: times[i], toTime: times[j],
          fromDir: dirs[i], toDir: dirs[j],
          degrees: Math.round(diff),
          gustBefore: gusts[i], gustAfter: gusts[j],
        };
      }
    }
    return { detected: false };
  }

  // ── grafičen kompas ────────────────────────────────────────────────────
  // dirFromDeg: smer OD KOD veter prihaja (meteorološka konvencija). Puščica
  // na sliki kaže KAM veter piha (dirFromDeg+180) — to je uporabniku
  // intuitivnejše pri presoji, kam bo veter nosil dim/ogenj.
  function windCompassSvg(dirFromDeg, opts) {
    opts = opts || {};
    var size = opts.size || 128;
    var cx = size / 2, cy = size / 2;
    var r = size / 2 - 16;
    var toDeg = ((dirFromDeg || 0) + 180) % 360;
    var labels = [
      { t: 'S', x: cx, y: 15 },
      { t: 'V', x: size - 9, y: cy + 4 },
      { t: 'J', x: cx, y: size - 6 },
      { t: 'Z', x: 9, y: cy + 4 },
    ];
    var labelsHtml = labels.map(function (l) {
      return '<text x="' + l.x + '" y="' + l.y + '" text-anchor="middle" font-size="11" ' +
        'font-weight="700" fill="currentColor" opacity=".55">' + l.t + '</text>';
    }).join('');
    return '<svg viewBox="0 0 ' + size + ' ' + size + '" width="' + size + '" height="' + size +
      '" class="gf-compass" aria-hidden="true">' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="currentColor" ' +
      'stroke-opacity=".18" stroke-width="1.5"/>' +
      labelsHtml +
      '<g transform="rotate(' + toDeg + ' ' + cx + ' ' + cy + ')">' +
      '<line x1="' + cx + '" y1="' + cy + '" x2="' + cx + '" y2="' + (cy - r + 6) +
      '" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>' +
      '<path d="M ' + (cx - 7) + ' ' + (cy - r + 18) + ' L ' + cx + ' ' + (cy - r + 4) +
      ' L ' + (cx + 7) + ' ' + (cy - r + 18) + ' Z" fill="currentColor"/>' +
      '</g></svg>';
  }

  // ── FWI (kanadski/EFFIS) — glej opombo na vrhu datoteke ───────────────
  function calcOneDayFWI(prev, T, H, W, r, month) {
    H = Math.max(1, Math.min(H, 99)); W = Math.max(0, W); r = Math.max(0, r);
    var F0 = prev.ffmc != null ? prev.ffmc : 85, P0 = prev.dmc != null ? prev.dmc : 6,
      D0 = prev.dc != null ? prev.dc : 15;
    var mo = 147.2 * (101 - F0) / (59.5 + F0);
    var mR = mo;
    if (r > 0.5) {
      var rf = r - 0.5;
      var mr = mo + 42.5 * rf * Math.exp(-100 / (251 - mo)) * (1 - Math.exp(-6.93 / rf));
      if (mo > 150) mr += 0.0015 * Math.pow(mo - 150, 2) * Math.sqrt(rf);
      mR = Math.min(mr, 250);
    }
    var Ed = 0.942 * Math.pow(H, 0.679) + 11 * Math.exp((H - 100) / 10) + 0.18 * (21.1 - T) * (1 - Math.exp(-0.115 * H));
    var Ew = 0.618 * Math.pow(H, 0.753) + 10 * Math.exp((H - 100) / 10) + 0.18 * (21.1 - T) * (1 - Math.exp(-0.115 * H));
    var m1;
    if (mR > Ed) {
      var kd = 0.424 * (1 - Math.pow(H / 100, 1.7)) + 0.0694 * Math.sqrt(W) * (1 - Math.pow(H / 100, 8));
      m1 = Ed + (mR - Ed) * Math.exp(-2.303 * kd);
    } else if (mR < Ew) {
      var kw = 0.424 * (1 - Math.pow((100 - H) / 100, 1.7)) + 0.0694 * Math.sqrt(W) * (1 - Math.pow((100 - H) / 100, 8));
      m1 = Ew - (Ew - mR) * Math.exp(-2.303 * kw);
    } else {
      m1 = mR;
    }
    var ffmc = 59.5 * (250 - m1) / (147.2 + m1);
    var Pr = P0;
    if (r > 1.5) {
      var re = 0.92 * r - 1.27;
      var Mo = 20 + Math.exp(5.6348 - P0 / 43.43);
      var b = P0 <= 33 ? 100 / (0.5 + 0.3 * P0) : P0 <= 65 ? 14 - 1.3 * Math.log(P0) : 6.2 * Math.log(P0) - 17.2;
      var Mr = Mo + 1000 * re / (48.77 + b * re);
      Pr = Math.max(244.72 - 43.43 * Math.log(Mr - 20), 0);
    }
    var Le = [6.5, 7.5, 9.0, 12.8, 13.9, 13.9, 12.4, 10.9, 9.4, 8.0, 7.0, 6.0][month];
    var K = 1.894 * (T + 1.1) * (100 - H) * Le * 1e-6;
    var dmc = Math.max(Pr + 100 * K, 0);
    var Dr = D0;
    if (r > 2.8) {
      var rd = 0.83 * r - 1.27;
      var Qo = 800 * Math.exp(-D0 / 400);
      var Qr = Qo + 3.937 * rd;
      Dr = Math.max(400 * Math.log(800 / Qr), 0);
    }
    var Lf = [-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6][month];
    var dc = Math.max(Dr + Math.max(0, 0.36 * (T + 2.8) + Lf) / 2, 0);
    var fW = Math.exp(0.05039 * W);
    var mF = 147.2 * (101 - ffmc) / (59.5 + ffmc);
    var fF = 91.9 * Math.exp(-0.1386 * mF) * (1 + Math.pow(mF, 5.31) / 4.93e7);
    var isi = 0.208 * fW * fF;
    var bui = dmc <= 0.4 * dc ? 0.8 * dmc * dc / (dmc + 0.4 * dc) :
      dmc - (1 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + Math.pow(0.0114 * dmc, 1.7));
    var fD = bui <= 80 ? 0.626 * Math.pow(Math.max(bui, 0), 0.809) + 2 : 1000 / (25 + 108.64 * Math.exp(-0.023 * bui));
    var B = 0.1 * isi * fD;
    var fwi = B > 1 ? Math.exp(2.72 * Math.pow(0.434 * Math.log(B), 0.647)) : B;
    return { ffmc: ffmc, dmc: dmc, dc: dc, isi: isi, bui: bui, fwi: Math.max(0, fwi) };
  }

  // haversine razdalja v km — uporabljata karta (razdalja do hidranta) in
  // intervencija (ali je GPS lokacija dovolj daleč od Rečice za lokalni FWI).
  function distanceKm(lat1, lon1, lat2, lon2) {
    var R = 6371;
    var toRad = function (d) { return d * Math.PI / 180; };
    var dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  // Sekvenčno gradi dnevni FWI iz Open-Meteo `daily` bloka (temperature_2m_max,
  // relative_humidity_2m_min, windspeed_10m_max, precipitation_sum) — analogno
  // fwi_series() v gasilec_model.py in fetchFireWeather() v app.js. Uporablja
  // se za lokalni FWI po poljubni GPS lokaciji na /intervencija/ (P1) — FWI za
  // fiksno Rečico ostaja strežniško izračunan (gasilec_model.py).
  function fwiSeriesFromDaily(daily) {
    var dates = daily.time || [];
    var tmax = daily.temperature_2m_max || [];
    var rhmin = daily.relative_humidity_2m_min || [];
    var wind = daily.windspeed_10m_max || [];
    var precip = daily.precipitation_sum || [];
    var prev = { ffmc: 85, dmc: 6, dc: 15 };
    var days = [];
    for (var i = 0; i < dates.length; i++) {
      var T = tmax[i] != null ? tmax[i] : 20;
      var H = rhmin[i] != null ? rhmin[i] : 50;
      var W = wind[i] != null ? wind[i] : 0;
      var r = precip[i] != null ? precip[i] : 0;
      var month = new Date(dates[i]).getMonth();
      var res = calcOneDayFWI(prev, T, H, W, r, month);
      prev = res;
      var cls = fwiClass(res.fwi);
      days.push({ date: dates[i], fwi: res.fwi, isi: res.isi, level: cls.label });
    }
    return days;
  }

  function fwiClass(v) {
    if (v < 5.2) return { label: 'Nizka', col: '#22c55e' };
    if (v < 11.2) return { label: 'Zmerna', col: '#84cc16' };
    if (v < 21.3) return { label: 'Visoka', col: '#f59e0b' };
    if (v < 38.0) return { label: 'Zelo visoka', col: '#ef4444' };
    return { label: 'Ekstremna', col: '#7c3aed' };
  }

  // ── freshness ──────────────────────────────────────────────────────────
  // Nikoli ne skrivamo stare vrednosti — samo označimo, kako stara je.
  function renderFreshness(el, isoTimestamp, opts) {
    if (!el) return;
    opts = opts || {};
    var greenH = opts.greenH != null ? opts.greenH : 26;
    var yellowH = opts.yellowH != null ? opts.yellowH : 50;
    if (!isoTimestamp) { el.innerHTML = ''; return; }
    var then = new Date(isoTimestamp).getTime();
    if (isNaN(then)) { el.innerHTML = ''; return; }
    var ageH = (Date.now() - then) / 3600000;
    var dot, label;
    if (ageH < greenH) {
      dot = '🟢';
      label = ageH < 1 ? 'posodobljeno pred ' + Math.max(1, Math.round(ageH * 60)) + ' min'
        : 'posodobljeno pred ' + Math.round(ageH) + ' h';
    } else if (ageH < yellowH) {
      dot = '🟡';
      label = 'podatki starejši — zadnja posodobitev pred ' + Math.round(ageH) + ' h';
    } else {
      dot = '🔴';
      var d = new Date(then);
      label = 'podatki niso aktualni — zadnja uspešna posodobitev ' +
        d.toLocaleDateString('sl', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
        ' ob ' + d.toLocaleTimeString('sl', { hour: '2-digit', minute: '2-digit' });
    }
    el.innerHTML = '<span class="gf-fresh-dot">' + dot + '</span> <span class="gf-fresh-label">' + label + '</span>';
  }

  // ── veter + teren (naklon/ekspozicija) ────────────────────────────────
  // Povsem klientsko, brez strežniške kopije — za razliko od FWI/vetra je
  // odvisno od TRENUTNE aktivne lokacije (GPS jo spremeni), zato SSR rezerva
  // ne bi imela pomena (glej opombo v generate_gasilec_page.py).
  var TERRAIN_STEP_M = 90; // ločljivost DEM-a, ki ga Open-Meteo Elevation API uporablja
  var TERRAIN_ALIGN_DEG = 45; // MeteoGasilec kriterij za "poravnano", isti prag kot obrat vetra

  function offsetLatLon(lat, lon, dNorthM, dEastM) {
    var dLat = dNorthM / 111320;
    var dLon = dEastM / (111320 * Math.cos(lat * Math.PI / 180));
    return [lat + dLat, lon + dLon];
  }

  // En klic na Open-Meteo Elevation API za 3×3 mrežo okrog (lat,lon), korak
  // `stepM` metrov. Vrne poimenovane točke (ne golo zaporedje), da je vrstni
  // red za computeSlopeAspect() nedvoumen.
  function fetchElevationGrid(lat, lon, stepM) {
    stepM = stepM || TERRAIN_STEP_M;
    var pts = {
      nw: offsetLatLon(lat, lon, stepM, -stepM), n: offsetLatLon(lat, lon, stepM, 0),
      ne: offsetLatLon(lat, lon, stepM, stepM), w: offsetLatLon(lat, lon, 0, -stepM),
      center: [lat, lon], e: offsetLatLon(lat, lon, 0, stepM),
      sw: offsetLatLon(lat, lon, -stepM, -stepM), s: offsetLatLon(lat, lon, -stepM, 0),
      se: offsetLatLon(lat, lon, -stepM, stepM),
    };
    var order = ['nw', 'n', 'ne', 'w', 'center', 'e', 'sw', 's', 'se'];
    var lats = order.map(function (k) { return pts[k][0]; }).join(',');
    var lons = order.map(function (k) { return pts[k][1]; }).join(',');
    var url = 'https://api.open-meteo.com/v1/elevation?latitude=' + lats + '&longitude=' + lons;
    return fetch(url).then(function (r) { return r.json(); }).then(function (d) {
      var el = (d && d.elevation) || [];
      var g = {};
      order.forEach(function (k, i) { g[k] = el[i]; });
      return g;
    });
  }

  // Horn (1981) naklon/ekspozicija — standardni GIS algoritem (ArcGIS/QGIS),
  // enotno testiran pred vklopom (glej Node test s sintetičnimi mrežami znane
  // smeri: sever/jug/vzhod/zahod). `aspectDeg` je smer, KAMOR je pobočje
  // obrnjeno (smer padanja terena) — kompas bearing 0-360.
  function computeSlopeAspect(g, cellSizeM) {
    cellSizeM = cellSizeM || TERRAIN_STEP_M;
    var dzdx = ((g.ne + 2 * g.e + g.se) - (g.nw + 2 * g.w + g.sw)) / (8 * cellSizeM);
    var dzdy = ((g.sw + 2 * g.s + g.se) - (g.nw + 2 * g.n + g.ne)) / (8 * cellSizeM);
    var slopeDeg = Math.atan(Math.sqrt(dzdx * dzdx + dzdy * dzdy)) * 57.29578;
    var a = Math.atan2(dzdy, -dzdx) * 57.29578;
    var aspectDeg;
    if (a < 0) aspectDeg = 90.0 - a;
    else if (a > 90.0) aspectDeg = 360.0 - a + 90.0;
    else aspectDeg = 90.0 - a;
    return { slopeDeg: slopeDeg, aspectDeg: aspectDeg };
  }

  // windToDeg: smer KAM veter piha (ne od kod — glej windCompassSvg). Opozori,
  // če je poravnan z aspectDeg (smer padanja pobočja) znotraj praga — to je
  // MeteoGasilec kriterij, poenostavljen (brez vegetacije/gostote gozda).
  function renderTerrainWind(el, aspectDeg, windToDeg, slopeDeg) {
    if (!el) return;
    var diff = angleDiff(aspectDeg, windToDeg);
    var aligned = diff <= TERRAIN_ALIGN_DEG;
    var html = '<div class="gf-interv-stats">' +
      '<div class="gf-stat"><b>' + Math.round(slopeDeg) + '°</b><span>Naklon terena</span></div>' +
      '<div class="gf-stat"><b>' + dirLabel(aspectDeg) + '</b><span>Pobočje pada proti</span></div>' +
      '<div class="gf-stat"><b>' + dirLabel(windToDeg) + '</b><span>Veter piha proti</span></div>' +
      '</div>';
    if (aligned) {
      html += '<div class="gf-shift-warn"><b>⚠ MeteoGasilec kriterij: veter in pobočje sta poravnana</b>' +
        'Veter piha v isto smer, kot pobočje pada (' + dirLabel(aspectDeg) + ') — na takem terenu se ogenj širi ' +
        'bistveno hitreje navzgor. Poenostavljena ocena (brez vegetacije/gostote gozda) — ni nadomestilo za ' +
        'presojo na terenu.</div>';
    } else {
      html += '<p class="gf-note" style="margin:.4rem 0 0">Veter in naklon pobočja trenutno nista poravnana ' +
        '(razlika ' + Math.round(diff) + '°). Poenostavljena ocena — ni nadomestilo za presojo na terenu.</p>';
    }
    el.innerHTML = html;
  }

  // ── ARSO uradna opozorila (jasno ločeno od MeteoGasilec lastnih ocen) ────
  // Isti Worker endpoint kot generate_arso_newsjack_post.py/fetch_alerts()
  // in /nevihte/ (WX-ARSO) — klican neposredno iz brskalnika, da je stanje
  // vedno sveže, ne glede na dnevni cikel generatorja strani (opozorilo je
  // stanje, ne novica, glej CLAUDE.md "Opozorila ARSO gredo na /nevihte/").
  var ARSO_WORKER = 'https://weatherireica1.filip-eremita.workers.dev';
  var ARSO_LEVEL = {
    red: { emoji: '🔴', label: 'rdeče' },
    orange: { emoji: '🟠', label: 'oranžno' },
    yellow: { emoji: '🟡', label: 'rumeno' },
  };

  function fetchArsoAlerts(region) {
    region = region || 'SLOVENIA_NORTH-EAST';
    return fetch(ARSO_WORKER + '/arso-warning?region=' + region)
      .then(function (r) { return r.json(); })
      .then(function (d) { return { alerts: (d && d.alerts) || [], issued: d && d.issued }; });
  }

  // Izriše v `el` in vrne Promise z {alerts,issued} (ali `null`, glej spodaj) —
  // klicatelj ga lahko uporabi za dopolnitev briefinga (glej buildBriefing
  // `arsoAlerts`).
  //
  // `el` ob klicu praviloma že vsebuje strežniško izrisan zadnji znan posnetek
  // (glej arso_widget_html() v generate_gasilec_page.py) — ne več prazen
  // "Preverjam …" placeholder. Če živi klic uspe, ta posnetek vedno povozimo s
  // sveže podatki. Če spodleti, GA NE IZBRIŠEMO: stran je varnostno-kritična in
  // star-a-znan status je boljši od izgubljenega konteksta ali napačno-pomirjujočega
  // "vir ni na voljo" čez dober posnetek. V tem primeru vrnemo `null`, da
  // klicatelj (glej gf-arso-compact zgoraj v generate_gasilec_page.py) ne povozi
  // svojega že pravilno inicializiranega seznama opozoril z null podatkom.
  function renderArsoWidget(el, opts) {
    if (!el) return Promise.resolve(null);
    opts = opts || {};
    var hadSnapshot = !!(el.textContent && el.textContent.trim());
    return fetchArsoAlerts(opts.region).then(function (res) {
      var alerts = res.alerts || [];
      if (!alerts.length) {
        el.innerHTML = '<p class="gf-note" style="margin:0">✅ ' +
          (opts.compact ? 'Ni aktivnih uradnih opozoril ARSO.' : 'Trenutno ni aktivnih uradnih opozoril ARSO za to območje.') +
          '</p>';
        return res;
      }
      var items = alerts.map(function (a) {
        var lv = ARSO_LEVEL[a.level] || { emoji: '⚠️' };
        return '<div class="gf-arso-item gf-arso-' + (a.level || 'yellow') + '">' + lv.emoji + ' <b>' +
          (a.text || a.desc || 'Opozorilo') + '</b></div>';
      }).join('');
      el.innerHTML = '<div class="gf-arso-list">' + items + '</div>';
      return res;
    }).catch(function () {
      if (!hadSnapshot) {
        el.innerHTML = '<p class="gf-note" style="margin:0">Vir trenutno ni na voljo.</p>';
      }
      return null;
    });
  }

  // ── briefing ───────────────────────────────────────────────────────────
  // data: {timeLabel, placeLabel, temp, rh, windSpeed, windGust, windFromDeg,
  //        precip3h, fwi, fwiLevel, isi, shift: detectWindShift() rezultat|null}
  function buildBriefing(data) {
    var lines = [];
    lines.push('🚒 METEOGASILEC — ' + data.timeLabel);
    lines.push('📍 ' + data.placeLabel);
    if (data.temp != null) lines.push('🌡 ' + data.temp.toFixed(1) + ' °C');
    if (data.rh != null) lines.push('💧 RH ' + Math.round(data.rh) + ' %');
    if (data.windFromDeg != null && data.windSpeed != null) {
      lines.push('🌬 ' + dirLabel(data.windFromDeg) + ' ' + Math.round(data.windSpeed) + ' km/h');
    }
    if (data.windGust != null) lines.push('💨 sunki ' + Math.round(data.windGust) + ' km/h');
    if (data.fwi != null) lines.push('🔥 FWI ' + data.fwi.toFixed(1) + ' — ' + (data.fwiLevel || '').toUpperCase());
    if (data.isi != null) lines.push('⚡ ISI ' + data.isi.toFixed(1));
    if (data.shift && data.shift.detected) {
      var shiftTime = data.shift.toTime && data.shift.toTime.length >= 16
        ? data.shift.toTime.slice(11, 16) : (data.shift.toTime || '—');
      lines.push('⚠ Ob ' + shiftTime + ' možen obrat vetra ' +
        dirLabel(data.shift.fromDir) + ' → ' + dirLabel(data.shift.toDir) +
        ' (+' + data.shift.degrees + '°)');
    }
    if (data.precip3h != null) lines.push('🌧 Padavine naslednje 3 h: ' + data.precip3h.toFixed(1) + ' mm');
    if (data.arsoAlerts && data.arsoAlerts.length) {
      lines.push('ARSO:');
      data.arsoAlerts.forEach(function (a) {
        var lv = ARSO_LEVEL[a.level] || { emoji: '⚠️' };
        lines.push(lv.emoji + ' ' + (a.text || a.desc || 'opozorilo'));
      });
    }
    lines.push('');
    lines.push('MeteoGasilec — informativni podatki, ni uradna ocena ARSO/URSZR');
    return lines.join('\n');
  }

  function wireBriefingButtons(copyBtn, shareBtn, getBriefingText) {
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        var text = getBriefingText();
        if (!text) return;
        var done = function () {
          var old = copyBtn.textContent;
          copyBtn.textContent = '✓ Kopirano';
          setTimeout(function () { copyBtn.textContent = old; }, 1800);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done).catch(function () {
            window.prompt('Kopiraj ročno:', text);
          });
        } else {
          window.prompt('Kopiraj ročno:', text);
        }
      });
    }
    if (shareBtn) {
      if (navigator.share) {
        shareBtn.hidden = false;
        shareBtn.addEventListener('click', function () {
          var text = getBriefingText();
          if (!text) return;
          navigator.share({ title: 'MeteoGasilec briefing', text: text }).catch(function () {});
        });
      } else {
        shareBtn.hidden = true;
      }
    }
  }

  global.Gasilec = {
    DIRS: GASILEC_DIRS,
    dirLabel: dirLabel,
    angleDiff: angleDiff,
    detectWindShift: detectWindShift,
    windCompassSvg: windCompassSvg,
    calcOneDayFWI: calcOneDayFWI,
    fwiClass: fwiClass,
    distanceKm: distanceKm,
    fwiSeriesFromDaily: fwiSeriesFromDaily,
    fetchArsoAlerts: fetchArsoAlerts,
    renderArsoWidget: renderArsoWidget,
    offsetLatLon: offsetLatLon,
    fetchElevationGrid: fetchElevationGrid,
    computeSlopeAspect: computeSlopeAspect,
    renderTerrainWind: renderTerrainWind,
    renderFreshness: renderFreshness,
    buildBriefing: buildBriefing,
    wireBriefingButtons: wireBriefingButtons,
  };
})(window);
