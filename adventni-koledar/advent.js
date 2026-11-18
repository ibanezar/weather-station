// Adventni koledar: model brez DOM-a (izvožen za Node) + prikaz.
(function (root) {
  'use strict';
  // Lokalni datum v Ljubljani kot {y,m,d}.
  function ljDate(now) {
    var p = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Ljubljana', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now || new Date()).split('-');
    return { y: +p[0], m: +p[1], d: +p[2] };
  }
  // Odprta vrata: do katere številke so odprta (0 = nobena, 24 = vsa).
  function openUpTo(dt, forced) {
    if (forced != null && forced >= 0) return Math.min(24, forced);
    if (dt.m === 1) return 24;
    if (dt.m < 12) return 0;
    if (dt.m === 12) return Math.min(24, dt.d);
    return 24;
  }
  var api = { ljDate: ljDate, openUpTo: openUpTo };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.AdventModel = api;
  if (typeof document === 'undefined') return;
  var data = JSON.parse(document.getElementById('adv-data').textContent);
  var q = /[?&]dan=(\d+)/.exec(location.search);
  var upto = openUpTo(ljDate(), q ? +q[1] : null);
  var list = document.getElementById('adv'), out = document.getElementById('adv-out');
  for (var i = 1; i <= 24; i++) {
    var li = document.createElement('li'), b = document.createElement('button');
    b.type = 'button'; b.textContent = i; b.dataset.d = i;
    b.setAttribute('aria-pressed', 'false');
    if (i > upto) { b.disabled = true; b.setAttribute('aria-label', 'Vrata ' + i + ', zaklenjena'); }
    else b.setAttribute('aria-label', 'Odpri vrata ' + i);
    li.appendChild(b); list.appendChild(li);
  }
  list.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b || b.disabled) return;
    var d = data[b.dataset.d];
    Array.prototype.forEach.call(list.querySelectorAll('button'), function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
    out.textContent = '';
    var t = document.createElement('div'); t.className = 'clabel'; t.textContent = d.t;
    var h = document.createElement('div'); h.className = 'adv-big'; h.textContent = d.h;
    var p = document.createElement('p'); p.textContent = d.p;
    out.appendChild(t); out.appendChild(h); out.appendChild(p);
  });
  if (upto === 0) out.querySelector('p').textContent = 'Prva vrata se odprejo 1. decembra.';
})(typeof window !== 'undefined' ? window : globalThis);
