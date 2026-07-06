/* ═══════════════════════════════════════════════════════════
   Nadgradnja blog članka:
   • bralni napredek (črta na vrhu)
   • bralni čas (v .post-meta)
   • kazalo (TOC) iz naslovov h2
   • sorodni članki (iz skupnih tagov v blog.json)
   Slug se izpelje iz poti. Vključi: <script src="/blog/article-enhance.js" defer></script>
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var article = document.querySelector("article");
  if (!article) return;

  var m = location.pathname.match(/\/blog\/([a-z0-9][a-z0-9-]*)\.html$/i);
  var SLUG = m ? m[1].toLowerCase() : "";

  function slugify(s) {
    return (s || "").toLowerCase()
      .replace(/č/g, "c").replace(/š/g, "s").replace(/ž/g, "z")
      .replace(/ć/g, "c").replace(/đ/g, "d")
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
  }

  // ── 1) Bralni čas ──────────────────────────────────────────
  var words = (article.textContent || "").trim().split(/\s+/).length;
  var mins = Math.max(1, Math.round(words / 200)); // ~200 besed/min
  var meta = article.querySelector(".post-meta");
  if (meta) {
    var rt = document.createElement("span");
    rt.className = "post-readtime";
    rt.innerHTML = ' · <span aria-hidden="true">⏱</span> ' + mins + ' min branja';
    meta.appendChild(rt);
  }

  // ── 2) Bralni napredek ─────────────────────────────────────
  var bar = document.createElement("div");
  bar.className = "read-progress";
  bar.setAttribute("aria-hidden", "true");
  var fill = document.createElement("div");
  fill.className = "read-progress-fill";
  bar.appendChild(fill);
  document.body.appendChild(bar);

  var ticking = false;
  function updateProgress() {
    var rect = article.getBoundingClientRect();
    var vh = window.innerHeight || document.documentElement.clientHeight;
    var total = rect.height - vh;
    var passed = -rect.top;
    var pct = total > 0 ? Math.min(1, Math.max(0, passed / total)) : 0;
    fill.style.width = (pct * 100).toFixed(1) + "%";
    ticking = false;
  }
  function onScroll() {
    if (!ticking) { window.requestAnimationFrame(updateProgress); ticking = true; }
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll, { passive: true });
  updateProgress();

  // ── 3) Kazalo (TOC) ────────────────────────────────────────
  var heads = Array.prototype.slice.call(article.querySelectorAll("h2"));
  if (heads.length >= 3) {
    var used = {};
    var items = heads.map(function (h) {
      var id = h.id || slugify(h.textContent);
      if (!id) return null;
      if (used[id]) id = id + "-" + (used[id]++); else used[id] = 1;
      h.id = id;
      return '<li><a href="#' + id + '">' + h.textContent + '</a></li>';
    }).filter(Boolean);

    var toc = document.createElement("details");
    toc.className = "post-toc";
    toc.open = true;
    toc.innerHTML = '<summary>Kazalo</summary><ul>' + items.join("") + '</ul>';

    var anchor = article.querySelector(".lead") || article.querySelector(".post-meta");
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(toc, anchor.nextSibling);
    else article.insertBefore(toc, article.firstChild);

    // mehko drsenje z odmikom za fiksno progres črto
    toc.addEventListener("click", function (e) {
      var a = e.target.closest("a[href^='#']");
      if (!a) return;
      var el = document.getElementById(a.getAttribute("href").slice(1));
      if (!el) return;
      e.preventDefault();
      window.scrollTo({ top: el.getBoundingClientRect().top + window.pageYOffset - 12, behavior: "smooth" });
      history.replaceState(null, "", a.getAttribute("href"));
    });
  }

  // ── 4) Sorodni članki ──────────────────────────────────────
  if (!SLUG) return;
  fetch("/blog.json", { cache: "force-cache" })
    .then(function (r) { return r.json(); })
    .then(function (posts) {
      var me = null;
      posts.forEach(function (p) { if ((p.slug || "").toLowerCase() === SLUG) me = p; });
      if (!me) return;
      var myTags = (me.tags || []).map(function (t) { return String(t).toLowerCase(); });
      if (!myTags.length) return;

      var scored = posts
        .filter(function (p) { return (p.slug || "").toLowerCase() !== SLUG; })
        .map(function (p) {
          var tags = (p.tags || []).map(function (t) { return String(t).toLowerCase(); });
          var shared = tags.filter(function (t) { return myTags.indexOf(t) !== -1; }).length;
          return { p: p, shared: shared };
        })
        .filter(function (x) { return x.shared > 0; })
        .sort(function (a, b) {
          return b.shared - a.shared || (a.p.date < b.p.date ? 1 : -1);
        })
        .slice(0, 3);

      if (!scored.length) return;

      function fmtDate(d) {
        try {
          return new Date(d).toLocaleDateString("sl-SI", { day: "numeric", month: "long", year: "numeric" });
        } catch (_) { return d || ""; }
      }

      var sec = document.createElement("section");
      sec.className = "related-posts";
      sec.innerHTML =
        '<h2 class="related-title">Sorodni članki</h2>' +
        '<div class="related-grid">' +
          scored.map(function (x) {
            var p = x.p;
            return '<a class="related-card" href="' + (p.url || ("/blog/" + p.slug + ".html")) + '">' +
              '<span class="related-date">' + fmtDate(p.date) + '</span>' +
              '<span class="related-h">' + p.title + '</span>' +
              (p.summary ? '<span class="related-sum">' + p.summary.slice(0, 120) + (p.summary.length > 120 ? "…" : "") + '</span>' : '') +
            '</a>';
          }).join("") +
        '</div>';

      var komentarji = document.getElementById("komentarji");
      var foot = document.querySelector(".site-foot");
      if (komentarji && komentarji.parentNode) komentarji.parentNode.insertBefore(sec, komentarji);
      else if (foot && foot.parentNode) foot.parentNode.insertBefore(sec, foot);
      else article.appendChild(sec);
    })
    .catch(function () { /* sorodni članki so postranski */ });
})();
