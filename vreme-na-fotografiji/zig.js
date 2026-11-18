// Vremenski žig na fotografiji: model brez DOM-a (izvožen za Node) + prikaz. Fotografija se obdela samo v brskalniku (canvas), nič se ne naloži.
(function (root) {
  'use strict';
  function pad(x) { return (x < 10 ? '0' : '') + x; }
  function f1(x) { return (Math.round(x * 10) / 10).toFixed(1).replace('.', ',').replace('-', '−'); }
  // Dan iz vdelanega niza {start, t, n, p}: vrne {t, n, p} ali null (zunaj niza ali manjkajoča polja).
  function dayOf(data, iso) {
    var i = Math.round((Date.parse(iso + 'T00:00:00Z') - Date.parse(data.start + 'T00:00:00Z')) / 864e5);
    if (i < 0 || i >= data.t.length || data.t[i] == null || data.n[i] == null || data.p[i] == null) return null;
    return { t: data.t[i], n: data.n[i], p: data.p[i] };
  }
  // Vrstice žiga. Za datum brez meritve vrne null (žiga ne izmišljamo).
  function lines(data, iso) {
    var d = dayOf(data, iso); if (!d) return null;
    var p = iso.split('-');
    return [
      +p[2] + '. ' + +p[1] + '. ' + p[0] + ' · Rečica ob Savinji',
      f1(d.n) + ' do ' + f1(d.t) + ' °C' + (d.p >= 0.2 ? ' · ' + f1(d.p) + ' mm' : ' · brez padavin'),
      'IREICA1 · meteorec.si'
    ];
  }
  // Velikost pisave in odmik glede na širino slike (min 14 px, da je žig berljiv tudi na majhni sliki).
  function metrics(w) { var fs = Math.max(14, Math.round(w / 28)); return { fs: fs, pad: Math.round(fs * 0.9), lh: Math.round(fs * 1.35) }; }
  var api = { dayOf: dayOf, lines: lines, metrics: metrics };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ZigModel = api;
  if (typeof document === 'undefined') return;
  var data = JSON.parse(document.getElementById('zg-data').textContent);
  var file = document.getElementById('zg-file'), dat = document.getElementById('zg-datum'), cv = document.getElementById('zg-cv'), msg = document.getElementById('zg-msg'), dl = document.getElementById('zg-dl');
  var img = null;
  function draw() {
    if (!img) return;
    var L = lines(data, dat.value);
    var MAXW = 2000, sc = Math.min(1, MAXW / img.naturalWidth);
    cv.width = Math.round(img.naturalWidth * sc); cv.height = Math.round(img.naturalHeight * sc);
    var c = cv.getContext('2d'); c.drawImage(img, 0, 0, cv.width, cv.height);
    if (!L) { msg.textContent = 'Za ta datum postaja nima popolne meritve (merimo od ' + (+data.start.slice(8, 10)) + '. ' + (+data.start.slice(5, 7)) + '. ' + data.start.slice(0, 4) + '). Žiga ne izmišljam.'; dl.hidden = true; return; }
    msg.textContent = ''; dl.hidden = false;
    var m = metrics(cv.width), h = L.length * m.lh + m.pad;
    c.fillStyle = 'rgba(0,0,0,.55)'; c.fillRect(0, cv.height - h - m.pad, cv.width, h + m.pad);
    c.fillStyle = '#fff'; c.textBaseline = 'top';
    L.forEach(function (s, i) { c.font = (i === 1 ? '700 ' : '400 ') + m.fs + 'px system-ui, sans-serif'; c.fillText(s, m.pad, cv.height - h - m.pad + m.pad / 2 + i * m.lh); });
  }
  file.addEventListener('change', function () {
    var f = file.files && file.files[0]; if (!f) return;
    var u = URL.createObjectURL(f), im = new Image();
    im.onload = function () { img = im; draw(); URL.revokeObjectURL(u); };
    im.onerror = function () { msg.textContent = 'Te datoteke ni mogoče prebrati kot sliko.'; };
    im.src = u;
  });
  dat.addEventListener('input', draw);
  dl.addEventListener('click', function () { cv.toBlob(function (b) { var a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'vreme-' + dat.value + '.jpg'; a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000); }, 'image/jpeg', 0.92); });
})(typeof window !== 'undefined' ? window : globalThis);
