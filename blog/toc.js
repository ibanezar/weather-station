/* Lepljivo kazalo ob levem robu članka (samo široki zasloni, CSS ga sicer skrije).
   Izpelje se iz <h2 id> v <article>; brez JS ali pod 2 razdelkoma ni kazala. */
(function () {
  var wrap = document.querySelector('.wrap');
  var heads = document.querySelectorAll('article h2[id]:not(.related-title)');
  if (!wrap || heads.length < 3) return;
  var nav = document.createElement('nav');
  nav.className = 'side-toc';
  nav.setAttribute('aria-label', 'Kazalo vsebine');
  var inner = document.createElement('div');
  inner.className = 'side-toc-in';
  var title = document.createElement('p');
  title.textContent = 'V članku';
  inner.appendChild(title);
  var links = {};
  heads.forEach(function (h) {
    var a = document.createElement('a');
    a.href = '#' + h.id;
    a.textContent = h.textContent;
    inner.appendChild(a);
    links[h.id] = a;
  });
  nav.appendChild(inner);
  wrap.appendChild(nav);
  var current = null, queued = false;
  function mark() {
    queued = false;
    var line = window.innerHeight * 0.3, hit = null;
    heads.forEach(function (h) { if (h.getBoundingClientRect().top <= line) hit = h; });
    var next = hit ? links[hit.id] : null;
    if (next === current) return;
    if (current) current.classList.remove('on');
    if (next) next.classList.add('on');
    current = next;
  }
  window.addEventListener('scroll', function () {
    if (!queued) { queued = true; requestAnimationFrame(mark); }
  }, { passive: true });
  mark();
})();
