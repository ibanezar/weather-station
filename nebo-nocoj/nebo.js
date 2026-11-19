// Nebo nocoj: model brez DOM-a (izvožen za Node) + prikaz. Polarni sij (NOAA SWPC Kp) + oblačnost (Open-Meteo) + utrinki (IMO, fiksni datumi vrha).
(function (root) {
  'use strict';
  var SYN = 29.530588853, NEW0 = Date.UTC(2000, 0, 6, 18, 14); // znan mlaj
  // Osvetljenost lune 0–1 za trenutek (ms). Preprost model sinodičnega meseca (±~1 dan): dovolj za »luna moti / ne moti«.
  function moonIllum(ms) {
    var ph = (((ms - NEW0) / 864e5) % SYN + SYN) % SYN / SYN;
    return (1 - Math.cos(2 * Math.PI * ph)) / 2;
  }
  // Polarni sij nad Slovenijo (geomagnetna širina ~ 47°): vidno običajno šele pri močni nevihti (Kp ≥ 7); Kp 6 je mejno.
  var KP_LIMIT = 7, KP_EDGE = 6;
  function kpStr(k) { return String(Math.round(k * 10) / 10).replace('.', ','); }
  function kpVerdict(kp) {
    var ks = kp == null ? '' : kpStr(kp);
    if (kp == null || isNaN(kp)) return { lvl: 'none', txt: 'Podatek o Kp ni na voljo.' };
    if (kp >= KP_LIMIT) return { lvl: 'go', txt: 'Močna geomagnetna nevihta (Kp ' + ks + '): sij je pri nas možen nizko nad severnim obzorjem.' };
    if (kp >= KP_EDGE) return { lvl: 'edge', txt: 'Kp ' + ks + ' je mejno: sij je pri nas le redko viden, najprej na fotografiji.' };
    return { lvl: 'no', txt: 'Kp ' + ks + ': sij nad Slovenijo ni pričakovan.' };
  }
  // Povprečna oblačnost (0–100) v nočnih urah (ure 20–5 lokalno): hourly = [{h: lokalna ura 0–23, c: oblačnost}].
  function nightCloud(hourly) {
    var s = 0, n = 0;
    for (var i = 0; i < hourly.length; i++) { var h = hourly[i].h; if ((h >= 20 || h <= 5) && hourly[i].c != null) { s += hourly[i].c; n++; } }
    return n ? s / n : null;
  }
  function cloudVerdict(c) {
    if (c == null) return { lvl: 'none', txt: 'Napoved oblačnosti ni na voljo.' };
    if (c < 30) return { lvl: 'go', txt: 'Nebo bo v povprečju jasno (oblačnost ' + Math.round(c) + ' %).' };
    if (c < 70) return { lvl: 'edge', txt: 'Delno oblačno (oblačnost ' + Math.round(c) + ' %): luknje v oblakih so možne.' };
    return { lvl: 'no', txt: 'Pretežno oblačno (oblačnost ' + Math.round(c) + ' %): neba ne bo videti.' };
  }
  // Skupna presoja za polarni sij: oboje mora biti ugodno.
  function auroraTonight(kp, cloud) {
    var k = kpVerdict(kp), c = cloudVerdict(cloud);
    if (k.lvl === 'none' || c.lvl === 'none') return { go: false, why: 'Manjka podatek: ' + (k.lvl === 'none' ? k.txt : c.txt) };
    var go = (k.lvl === 'go') && c.lvl !== 'no';
    return { go: go, why: k.txt + ' ' + c.txt };
  }
  // Roji (IMO): vrh = [mesec, dan]; ZHR je zenitna urna frekvenca ob idealnih pogojih.
  var SHOWERS = [
    { id: 'leonidi', name: 'Leonidi', peak: [11, 17], zhr: 15 },
    { id: 'geminidi', name: 'Geminidi', peak: [12, 14], zhr: 150 },
    { id: 'ursidi', name: 'Ursidi', peak: [12, 22], zhr: 10 },
    { id: 'kvadrantidi', name: 'Kvadrantidi', peak: [1, 3], zhr: 110 }
  ];
  function nextShower(now) {
    var y = new Date(now).getUTCFullYear(), best = null;
    for (var i = 0; i < SHOWERS.length; i++) for (var dy = 0; dy <= 1; dy++) {
      var t = Date.UTC(y + dy, SHOWERS[i].peak[0] - 1, SHOWERS[i].peak[1], 22); // vrh ponoči (22 UTC ≈ 23–24 lokalno)
      if (t >= now - 864e5 * 0.5 && (!best || t < best.t)) best = { s: SHOWERS[i], t: t };
    }
    return best;
  }
  function showerMoon(t) { var m = moonIllum(t); return { illum: m, bad: m > 0.5 }; }
  // Največji napovedani Kp od zdaj −3 h do +24 h. NOAA (noaa-planetary-k-index-forecast.json) vrača SEZNAM OBJEKTOV {time_tag, kp, observed, noaa_scale}
  // (stara oblika je bil seznam seznamov z glavo); delujeta obe. Kopija _nebKpMax() v worker.js (preverja test_nebo.mjs).
  function kpMaxFrom(rows, now) {
    var mx = null;
    if (!Array.isArray(rows)) return null;
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i], t, v;
      if (Array.isArray(r)) { t = r[0]; v = r[1]; } else if (r && typeof r === 'object') { t = r.time_tag; v = r.kp; } else continue;
      var s = String(t).replace(' ', 'T'), ts = Date.parse(/Z$/.test(s) ? s : s + 'Z'), k = parseFloat(v);
      if (isNaN(ts) || isNaN(k)) continue;
      if (ts >= now - 3 * 3600e3 && ts <= now + 24 * 3600e3 && (mx == null || k > mx)) mx = k;
    }
    return mx;
  }
  var api = { kpMaxFrom: kpMaxFrom, moonIllum: moonIllum, kpVerdict: kpVerdict, nightCloud: nightCloud, cloudVerdict: cloudVerdict, auroraTonight: auroraTonight, nextShower: nextShower, showerMoon: showerMoon, SHOWERS: SHOWERS, KP_LIMIT: KP_LIMIT };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.NeboModel = api;
  if (typeof document === 'undefined') return;
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  var out = document.getElementById('nb-out');
  function get(url) { return fetch(url).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  var kp = null, cloud = null;
  var pK = get('https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json').then(function (j) {
    kp = kpMaxFrom(j, Date.now());
  }).catch(function () { kp = null; });
  var pC = get('https://api.open-meteo.com/v1/forecast?latitude=46.3258&longitude=14.9211&hourly=cloud_cover&timezone=Europe%2FLjubljana&forecast_days=2').then(function (j) {
    var h = [], now = Date.now();
    for (var i = 0; i < j.hourly.time.length; i++) {
      var t = Date.parse(j.hourly.time[i]); // brez zamika = lokalni čas brskalnika: uporabimo samo uro iz niza
      var hr = +j.hourly.time[i].slice(11, 13), day = j.hourly.time[i].slice(0, 10);
      h.push({ h: hr, c: j.hourly.cloud_cover[i], day: day });
    }
    // prva noč: ure 20–23 prvega dne in 0–5 drugega dne
    var d0 = h[0].day, sel = h.filter(function (x) { return (x.day === d0 && x.h >= 20) || (x.day !== d0 && x.h <= 5); });
    cloud = nightCloud(sel);
  }).catch(function () { cloud = null; });
  Promise.all([pK, pC]).then(function () {
    out.textContent = '';
    var a = auroraTonight(kp, cloud);
    var c = el('div', 'card');
    c.appendChild(el('div', 'clabel', 'Polarni sij nocoj'));
    c.appendChild(el('div', 'nb-big', a.go ? 'Možen' : 'Ni pričakovan'));
    c.appendChild(el('p', null, a.why));
    out.appendChild(c);
    var n = nextShower(Date.now()), c2 = el('div', 'card');
    c2.appendChild(el('div', 'clabel', 'Naslednji roj utrinkov'));
    if (n) {
      var d = new Date(n.t), mo = showerMoon(n.t);
      c2.appendChild(el('div', 'nb-big', n.s.name + ', ' + d.getUTCDate() + '. ' + (d.getUTCMonth() + 1) + '.'));
      c2.appendChild(el('p', null, 'Do ' + n.s.zhr + ' utrinkov na uro ob idealnih pogojih (ZHR, IMO); v resnici bistveno manj. Luna je ' + Math.round(mo.illum * 100) + ' % osvetljena: ' + (mo.bad ? 'moti, vidnih bo manj utrinkov.' : 'ne moti.')));
    }
    out.appendChild(c2);
  });
  // Opozorilo na telefon (Web Push): strežnik shrani samo naslovnico naročnine, kljukici (roji, sij) in stanje po večerih.
  (function () {
    var box = document.getElementById('nb-alarm'); if (!box) return;
    var API = 'https://weatherireica1.filip-eremita.workers.dev', AK = 'wx-nebo-alarm';
    var cRoji = document.getElementById('nb-al-roji'), cSij = document.getElementById('nb-al-sij'), onB = document.getElementById('nb-al-on'),
        offB = document.getElementById('nb-al-off'), msg = document.getElementById('nb-al-msg'), ios = document.getElementById('nb-al-ios');
    var standalone = (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true;
    var isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    var st = null; try { st = JSON.parse(localStorage.getItem(AK) || 'null'); } catch (e) { st = null; }
    if (st) { cRoji.checked = !!st.roji; cSij.checked = !!st.sij; }
    function say(t) { msg.textContent = t || ''; }
    function show() {
      offB.hidden = !st; onB.textContent = st ? 'Shrani izbiro' : 'Vklopi opozorilo';
      say(st ? 'Opozorilo je vklopljeno: ' + [st.roji ? 'roji utrinkov' : '', st.sij ? 'polarni sij' : ''].filter(Boolean).join(', ') + '.' : '');
    }
    if (isIOS && !standalone) { box.hidden = false; ios.hidden = false; onB.disabled = true; return; }
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return;
    box.hidden = false; show();
    function b64(s) { var p = '='.repeat((4 - s.length % 4) % 4), b = (s + p).replace(/-/g, '+').replace(/_/g, '/'), r = atob(b), o = new Uint8Array(r.length); for (var i = 0; i < r.length; i++) o[i] = r.charCodeAt(i); return o; }
    function post(path, body) { return fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status)); return j; }); }); }
    function getSub() { return navigator.serviceWorker.register('/sw.js').then(function () { return navigator.serviceWorker.ready; }).then(function (reg) { return reg.pushManager.getSubscription().then(function (sub) { return { reg: reg, sub: sub }; }); }); }
    onB.addEventListener('click', function () {
      if (!cRoji.checked && !cSij.checked) { say('Izberite vsaj eno obvestilo.'); return; }
      if (Notification.permission === 'denied') { say('Obvestila so za to stran v brskalniku blokirana. Dovolite jih v nastavitvah strani.'); return; }
      Notification.requestPermission().then(function (p) {
        if (p !== 'granted') { say('Brez dovoljenja za obvestila opozorilo ne more delovati.'); return; }
        onB.disabled = true;
        return getSub().then(function (x) {
          if (x.sub) return x.sub;
          return fetch(API + '/push/vapid').then(function (r) { return r.json(); }).then(function (v) { return x.reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64(v.publicKey) }); });
        }).then(function (sub) { return post('/push/subscribe', { site: 'nebo', subscription: sub.toJSON(), roji: cRoji.checked, sij: cSij.checked }); })
          .then(function (r) { st = { roji: r.roji, sij: r.sij }; try { localStorage.setItem(AK, JSON.stringify(st)); } catch (e) {} show(); })
          .catch(function (e) { say('Ni uspelo: ' + (e && e.message ? e.message : 'poskusite znova čez nekaj minut') + '.'); })
          .then(function () { onB.disabled = false; });
      });
    });
    offB.addEventListener('click', function () {
      offB.disabled = true;
      getSub().then(function (x) { return x.sub ? post('/push/unsubscribe', { site: 'nebo', endpoint: x.sub.endpoint }) : null; })
        .then(function () { st = null; try { localStorage.removeItem(AK); } catch (e) {} show(); say('Opozorilo je izklopljeno, naslovnica in izbira sta izbrisani s strežnika.'); })
        .catch(function (e) { say('Ni uspelo: ' + (e && e.message ? e.message : 'poskusite znova') + '.'); }).then(function () { offB.disabled = false; });
    });
  })();
})(typeof window !== 'undefined' ? window : globalThis);
