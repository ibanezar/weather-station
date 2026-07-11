/* ─────────────────────────────────────────────────────────────
   Meteorec blog — sistem všečkov (sončki) na začetku in koncu posta
   • Skupni globalni števec preko Cloudflare Workerja (/like).
   • Stanje "všečkano" se hrani lokalno (localStorage), da posamezna
     naprava všečka samo enkrat; klik znova odvzame všeček.
   • Če Worker ni dosegljiv, widget deluje offline (lokalno stanje).
   ───────────────────────────────────────────────────────────── */
(function () {
  "use strict";

  var PROXY = "https://weatherireica1.filip-eremita.workers.dev";

  var article = document.querySelector("article");
  if (!article) return;

  // slug = ime datoteke brez končnice (npr. /blog/poplave-2023.html → poplave-2023)
  var slug = (location.pathname.split("/").pop() || "").replace(/\.html?$/i, "");
  if (!slug) return;

  var storeKey = "meteorec_like_" + slug;
  var liked = false;
  try { liked = localStorage.getItem(storeKey) === "1"; } catch (e) {}

  var SUN =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="5"/>' +
    '<line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>' +
    '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>' +
    '<line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>' +
    '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';

  var widgets = []; // { root, btn, countEl }

  function makeWidget(place) {
    var box = document.createElement("div");
    box.className = "like-box";
    box.setAttribute("data-place", place);

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "like-btn";
    btn.setAttribute("aria-pressed", liked ? "true" : "false");
    btn.setAttribute("aria-label", "Všeč mi je ta članek");
    btn.innerHTML = SUN +
      '<span class="like-text">Všeč mi je</span>' +
      '<span class="like-count" aria-hidden="true">·</span>';

    btn.addEventListener("click", onClick);
    box.appendChild(btn);

    var hint = document.createElement("span");
    hint.className = "like-hint";
    box.appendChild(hint);

    var w = { root: box, btn: btn, countEl: btn.querySelector(".like-count"), hint: hint };
    widgets.push(w);
    return box;
  }

  function render(count) {
    widgets.forEach(function (w) {
      if (typeof count === "number") {
        w.countEl.textContent = count;
        w.countEl.setAttribute("aria-hidden", "false");
      }
      w.btn.classList.toggle("is-liked", liked);
      w.btn.setAttribute("aria-pressed", liked ? "true" : "false");
      w.hint.textContent = liked ? "Hvala! ☀️" : "";
    });
  }

  var current = null; // zadnji znani skupni števec

  function onClick() {
    var wasLiked = liked;
    liked = !liked;
    try { localStorage.setItem(storeKey, liked ? "1" : "0"); } catch (e) {}

    // optimistična posodobitev + animacija sončka
    if (typeof current === "number") {
      current = Math.max(0, current + (liked ? 1 : -1));
    }
    render(current);
    if (liked) burst();

    // pošlji Workerju (delta), a ne zruši widgeta, če ni dosegljiv
    var delta = liked ? 1 : -1;
    fetch(PROXY + "/like?slug=" + encodeURIComponent(slug) + "&delta=" + delta, { method: "POST" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d && typeof d.count === "number") { current = d.count; render(current); } })
      .catch(function () { /* offline — obdržimo lokalno stanje */ });
  }

  function burst() {
    widgets.forEach(function (w) {
      w.btn.classList.remove("pop");
      // reflow, da se animacija sproži znova
      void w.btn.offsetWidth;
      w.btn.classList.add("pop");
    });
  }

  // ── vrivanje widgetov ──────────────────────────────────────
  // Zgoraj: takoj za .post-meta (nad uvodnim odstavkom), v skupnem
  // vrstičnem ovoju, kamor comments.js dopiše še povprečno oceno.
  var topAnchor = article.querySelector(".post-meta") || article.querySelector(".lead");
  var topWrap = document.createElement("div");
  topWrap.className = "top-engage";
  topWrap.id = "top-engage";
  topWrap.appendChild(makeWidget("top"));
  if (topAnchor && topAnchor.parentNode) {
    topAnchor.parentNode.insertBefore(topWrap, topAnchor.nextSibling);
  } else {
    article.insertBefore(topWrap, article.firstChild);
  }

  // Spodaj: tik pred povezavo "Nazaj na blog", sicer na konec članka.
  var bottomAnchor = article.querySelector(".back-link");
  if (bottomAnchor) {
    article.insertBefore(makeWidget("bottom"), bottomAnchor);
  } else {
    article.appendChild(makeWidget("bottom"));
  }

  render(); // začetni izris (brez števila)

  // ── začetni skupni števec ───────────────────────────────────
  fetch(PROXY + "/like?slug=" + encodeURIComponent(slug))
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) { if (d && typeof d.count === "number") { current = d.count; render(current); } })
    .catch(function () { /* offline — pusti prazen števec */ });
})();
