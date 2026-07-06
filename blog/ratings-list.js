/* ═══════════════════════════════════════════════════════════
   Prikaz povprečne ocene na seznamu blogov.
   Za vsako .post-card izlušči slug iz href-a, z enim bulk
   zahtevkom pridobi ocene in vstavi značko (★ povprečje · N ocen).
   Vključi na /blog/index.html: <script src="/blog/ratings-list.js" defer></script>
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  var PROXY = "https://weatherireica1.filip-eremita.workers.dev";

  var cards = Array.prototype.slice.call(document.querySelectorAll(".post-card[href]"));
  if (!cards.length) return;

  var map = {}; // slug → card
  cards.forEach(function (a) {
    var href = a.getAttribute("href") || "";
    var m = href.match(/([a-z0-9][a-z0-9-]*)\.html(?:[#?].*)?$/i);
    if (m) map[m[1].toLowerCase()] = a;
  });
  var slugs = Object.keys(map);
  if (!slugs.length) return;

  function stars(n) {
    var out = "";
    for (var i = 1; i <= 5; i++) out += '<span class="pr-star' + (i <= n ? " on" : "") + '">★</span>';
    return out;
  }
  function plural(n) {
    var m100 = n % 100;
    if (m100 === 1) return "ocena";
    if (m100 === 2) return "oceni";
    if (m100 === 3 || m100 === 4) return "ocene";
    return "ocen";
  }

  fetch(PROXY + "/blog-comments?slugs=" + encodeURIComponent(slugs.join(",")))
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var ratings = (d && d.ratings) || {};
      slugs.forEach(function (slug) {
        var r = ratings[slug];
        if (!r || !r.count) return;
        var card = map[slug];
        var body = card.querySelector(".post-card-body") || card;
        var el = document.createElement("div");
        el.className = "post-rating";
        el.innerHTML =
          '<span class="pr-avg">' + r.avg.toFixed(1) + '</span>' +
          '<span class="pr-stars">' + stars(Math.round(r.avg)) + '</span>' +
          '<span class="pr-count">' + r.count + ' ' + plural(r.count) + '</span>';
        body.appendChild(el);

        // "priljubljeno" za članke z visoko in dovolj številčno oceno
        if (r.avg >= 4.5 && r.count >= 3) {
          var pop = document.createElement("div");
          pop.innerHTML = '<span class="post-pop">★ Priljubljeno</span>';
          body.appendChild(pop.firstChild);
        }
      });
    })
    .catch(function () { /* tiho — ocene so postranske */ });
})();
