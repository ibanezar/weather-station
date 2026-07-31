/* ─────────────────────────────────────────────────────────────
   Meteorec blog — števec ogledov članka
   • Majhno okence takoj pod meta vrstico (datum · avtor), v istem
     vrstičnem ovoju .top-engage kot všeček in povprečna ocena.
   • Skupni števec teče prek Cloudflare Workerja (/views), enako
     kot všečki (/like).
   • Ena naprava šteje en ogled na 12 ur na članek: znotraj tega
     okna se pošlje navaden GET namesto POST. To hkrati drži
     število zapisov v KV nizko.
   • Če Worker ni dosegljiv, se okence sploh ne prikaže — prazen
     ali izmišljen števec je slabši od nobenega.
   ───────────────────────────────────────────────────────────── */
(function () {
  "use strict";

  var PROXY = "https://weatherireica1.filip-eremita.workers.dev";
  var WINDOW_MS = 12 * 60 * 60 * 1000; // isti bralec šteje enkrat na 12 h

  var article = document.querySelector("article");
  if (!article) return;

  // slug = ime datoteke brez končnice (npr. /blog/poplave-2023.html → poplave-2023)
  var slug = (location.pathname.split("/").pop() || "").replace(/\.html?$/i, "");
  if (!/^[a-z0-9-]{1,120}$/.test(slug)) return;

  // ── štetje enkrat na 12 h ───────────────────────────────────
  var storeKey = "meteorec_view_" + slug;
  var fresh = true; // true → ta ogled se šteje (POST)
  try {
    var last = parseInt(localStorage.getItem(storeKey) || "0", 10);
    if (last && Date.now() - last < WINDOW_MS) fresh = false;
  } catch (e) { /* zasebni način — štejemo, kot da je nov ogled */ }

  // ── izris ───────────────────────────────────────────────────
  var EYE =
    '<svg viewBox="0 0 24 24" aria-hidden="true">' +
    '<path d="M1.8 12S5.4 5.5 12 5.5 22.2 12 22.2 12 18.6 18.5 12 18.5 1.8 12 1.8 12Z"/>' +
    '<circle cx="12" cy="12" r="3.2"/></svg>';

  var el = null;

  // Slovenske oblike po CLDR: odloča ostanek pri deljenju s 100
  // (1 → ogled, 2 → ogleda, 3–4 → ogledi, sicer ogledov; 21 in 22 → ogledov).
  function plural(n, one, two, few, many) {
    var mod100 = n % 100;
    if (mod100 === 1) return one;
    if (mod100 === 2) return two;
    if (mod100 === 3 || mod100 === 4) return few;
    return many;
  }

  // 1234 → "1.234" (slovenski ločilnik tisočic)
  function fmt(n) {
    try { return n.toLocaleString("sl-SI"); } catch (e) { return String(n); }
  }

  function render(count) {
    if (typeof count !== "number" || count < 1) return;
    if (!el) {
      // .top-engage postavi likes.js takoj za .post-meta; če ga (še) ni,
      // ga ustvarimo sami, da okence ne pristane na napačnem mestu.
      var wrap = document.getElementById("top-engage");
      if (!wrap) {
        var anchor = article.querySelector(".post-meta") || article.querySelector(".lead");
        if (!anchor || !anchor.parentNode) return;
        wrap = document.createElement("div");
        wrap.className = "top-engage";
        wrap.id = "top-engage";
        anchor.parentNode.insertBefore(wrap, anchor.nextSibling);
      }
      el = document.createElement("span");
      el.className = "view-chip";
      el.title = "Število ogledov tega članka";
      wrap.appendChild(el);
    }
    el.innerHTML = EYE +
      '<span class="vc-num">' + fmt(count) + '</span>' +
      '<span class="vc-label">' + plural(count, "ogled", "ogleda", "ogledi", "ogledov") + '</span>';
  }

  // ── klic Workerja ───────────────────────────────────────────
  // Nov ogled: POST (šteje). Znotraj 12-urnega okna: GET (samo prebere).
  fetch(PROXY + "/views?slug=" + encodeURIComponent(slug), { method: fresh ? "POST" : "GET" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) {
      if (!d || typeof d.count !== "number") return;
      if (fresh) {
        try { localStorage.setItem(storeKey, String(Date.now())); } catch (e) {}
      }
      render(d.count);
    })
    .catch(function () { /* offline — okenca preprosto ni */ });
})();
