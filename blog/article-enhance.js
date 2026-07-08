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

  // ── 3) Naslovi: id-ji + deljive 🔗 povezave + kazalo (TOC) ──
  var heads = Array.prototype.slice.call(article.querySelectorAll("h2"));
  var used = {};
  heads.forEach(function (h) {
    var id = h.id || slugify(h.textContent);
    if (!id) return;
    if (used[id]) id = id + "-" + (used[id]++); else used[id] = 1;
    h.id = id;
    // deljiva povezava do razdelka
    var link = document.createElement("button");
    link.type = "button";
    link.className = "h-anchor";
    link.setAttribute("aria-label", "Kopiraj povezavo do razdelka");
    link.title = "Kopiraj povezavo do razdelka";
    link.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>';
    link.addEventListener("click", function () {
      var u = location.origin + location.pathname + "#" + h.id;
      history.replaceState(null, "", "#" + h.id);
      var done = function () { link.classList.add("copied"); setTimeout(function () { link.classList.remove("copied"); }, 1500); };
      if (navigator.clipboard) navigator.clipboard.writeText(u).then(done, done); else done();
    });
    h.appendChild(link);
  });

  if (heads.length >= 3) {
    var items = heads.map(function (h) {
      // besedilo naslova brez gumba
      var txt = (h.childNodes[0] && h.childNodes[0].nodeType === 3) ? h.textContent.replace(/\s*$/, "") : h.textContent;
      return '<li><a href="#' + h.id + '">' + txt + '</a></li>';
    });
    var toc = document.createElement("details");
    toc.className = "post-toc";
    toc.open = true;
    toc.innerHTML = '<summary>Kazalo</summary><ul>' + items.join("") + '</ul>';
    var anchor = article.querySelector(".lead") || article.querySelector(".post-meta");
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(toc, anchor.nextSibling);
    else article.insertBefore(toc, article.firstChild);
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

  // ── 3a) Lepljivi sidebar (samo širok zaslon; CSS skrije na mobilcu) ──
  if (heads.length >= 3) {
    var aside = document.createElement("aside");
    aside.className = "blog-sidebar";
    aside.innerHTML =
      '<div class="side-block side-live" hidden>' +
        '<div class="side-title">Trenutno · IREICA1</div>' +
        '<div class="side-live-body"></div>' +
      '</div>' +
      '<div class="side-block">' +
        '<div class="side-title">Na tej strani</div>' +
        '<nav class="side-toc">' +
          heads.map(function (h) {
            var txt = (h.childNodes[0] && h.childNodes[0].nodeType === 3) ? h.textContent.replace(/\s*$/, "") : h.textContent;
            return '<a href="#' + h.id + '" data-id="' + h.id + '">' + txt + '</a>';
          }).join("") +
        '</nav>' +
      '</div>' +
      '<div class="side-block side-recent" hidden>' +
        '<div class="side-title">Novejši članki</div>' +
        '<div class="side-list"></div>' +
      '</div>' +
      '<div class="side-block side-actions">' +
        '<div class="side-title">Prijava na novičke</div>' +
        '<form class="side-sub-form" id="side-sub-form" autocomplete="off">' +
          '<input class="side-sub-input" id="side-sub-email" type="email" required maxlength="120" placeholder="tvoj@email.si" aria-label="E-naslov">' +
          '<input class="sub-hp" type="text" name="website" id="side-sub-hp" tabindex="-1" autocomplete="off" aria-hidden="true">' +
          '<button class="side-sub" id="side-sub-btn" type="submit">📬 Prijava</button>' +
        '</form>' +
        '<p class="side-sub-msg" id="side-sub-msg" aria-live="polite"></p>' +
        '<a class="side-back" href="/blog/">← Vsi članki</a>' +
        '<a class="side-back" href="/blog/rss.xml">📡 RSS</a>' +
      '</div>';
    var wrap = document.querySelector(".wrap");
    if (wrap) wrap.insertBefore(aside, article.nextSibling);
    else document.body.appendChild(aside);
    document.body.classList.add("has-blog-sidebar");

    // mehko drsenje iz sidebara
    aside.querySelector(".side-toc").addEventListener("click", function (e) {
      var a = e.target.closest("a[href^='#']");
      if (!a) return;
      var el = document.getElementById(a.getAttribute("href").slice(1));
      if (!el) return;
      e.preventDefault();
      window.scrollTo({ top: el.getBoundingClientRect().top + window.pageYOffset - 12, behavior: "smooth" });
      history.replaceState(null, "", a.getAttribute("href"));
    });
    // vgrajen obrazec za prijavo (isti Cloudflare Worker kot .subscribe-box)
    (function () {
      var PROXY = "https://weatherireica1.filip-eremita.workers.dev";
      var form  = aside.querySelector("#side-sub-form");
      var email = aside.querySelector("#side-sub-email");
      var btn   = aside.querySelector("#side-sub-btn");
      var msg   = aside.querySelector("#side-sub-msg");
      function setMsg(t, err) { msg.textContent = t || ""; msg.className = "side-sub-msg" + (err ? " err" : " ok"); }
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        if (aside.querySelector("#side-sub-hp").value) return; // bot
        var val = email.value.trim();
        if (!val) { setMsg("Vpiši e-naslov.", true); return; }
        btn.disabled = true; btn.textContent = "Pošiljam…"; setMsg("");
        fetch(PROXY + "/blog-subscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: val, website: "" })
        })
          .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
          .then(function (res) {
            if (!res.ok || res.j.error) { setMsg(res.j.error || "Napaka pri prijavi.", true); return; }
            if (res.j.already) { setMsg("Ta e-naslov je že naročen. 🙂"); }
            else { setMsg("Skoraj gotovo! Preveri e-pošto in potrdi naročnino."); form.reset(); }
          })
          .catch(function () { setMsg("Napaka v povezavi. Poskusi znova.", true); })
          .then(function () { btn.disabled = false; btn.textContent = "📬 Prijava"; });
      });
    })();

    // trenutne meritve postaje IREICA1 (isti proxy kot ostale žive kartice)
    (function () {
      var PROXY = "https://weatherireica1.filip-eremita.workers.dev";
      var block = aside.querySelector(".side-live");
      var body  = aside.querySelector(".side-live-body");
      function num(x, d) { return x == null ? "—" : x.toFixed(d == null ? 1 : d).replace(".", ","); }
      fetch(PROXY + "/wu-station?id=IREICA1")
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var obs = data.observations && data.observations[0];
          if (!obs) return;
          var m = obs.metric || {};
          var local = obs.obsTimeLocal || "";
          var hhmm = local.slice(11, 16);
          body.innerHTML =
            '<div class="side-live-temp">' + num(m.temp, 1) + '<span>°C</span></div>' +
            '<div class="side-live-grid">' +
              '<span>💧 ' + num(obs.humidity, 0) + ' %</span>' +
              '<span>💨 ' + num(m.windSpeed, 0) + ' km/h</span>' +
              (m.precipTotal != null ? '<span>🌧 ' + num(m.precipTotal, 1) + ' mm</span>' : '') +
              (m.pressure != null ? '<span>⏱ ' + num(m.pressure, 0) + ' hPa</span>' : '') +
            '</div>' +
            (hhmm ? '<div class="side-live-time">ob ' + hhmm + '</div>' : '');
          block.hidden = false;
        })
        .catch(function () { /* žive meritve so postranske, brez napake na strani */ });
    })();

    // scrollspy — poudari trenutni razdelek
    var spyLinks = Array.prototype.slice.call(aside.querySelectorAll(".side-toc a"));
    var spyTicking = false;
    function spy() {
      var y = window.pageYOffset + 130, cur = heads[0].id;
      for (var i = 0; i < heads.length; i++) {
        if (heads[i].getBoundingClientRect().top + window.pageYOffset <= y) cur = heads[i].id;
      }
      spyLinks.forEach(function (a) { a.classList.toggle("active", a.getAttribute("data-id") === cur); });
      spyTicking = false;
    }
    window.addEventListener("scroll", function () {
      if (!spyTicking) { window.requestAnimationFrame(spy); spyTicking = true; }
    }, { passive: true });
    spy();
  }

  // ── 3b) Gumb "na vrh" ──────────────────────────────────────
  var toTop = document.createElement("button");
  toTop.type = "button";
  toTop.className = "to-top";
  toTop.setAttribute("aria-label", "Nazaj na vrh");
  toTop.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 15l-6-6-6 6"/></svg>';
  toTop.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
  document.body.appendChild(toTop);
  window.addEventListener("scroll", function () {
    toTop.classList.toggle("show", window.pageYOffset > 700);
  }, { passive: true });

  // ── 3c) Avtorjev okvirček (na koncu članka) ────────────────
  var authorBox = document.createElement("div");
  authorBox.className = "author-box";
  authorBox.innerHTML =
    '<div class="author-avatar">FE</div>' +
    '<div class="author-info">' +
      '<span class="author-name">Filip Eremita</span>' +
      '<span class="author-bio">Upravljalec meteorološke postaje IREICA1 v Rečici ob Savinji. ' +
      '<a href="/o-postaji.html">Več o postaji →</a></span>' +
    '</div>';
  var backLink = article.querySelector(".back-link");
  if (backLink && backLink.parentNode) backLink.parentNode.insertBefore(authorBox, backLink);
  else article.appendChild(authorBox);

  // ── 4) Sorodni članki ──────────────────────────────────────
  if (!SLUG) return;

  // ── 4) Sorodni članki ──────────────────────────────────────
  // Prednostni vir: blog/related.json (TF-IDF podobnost dejanskega besedila,
  // izračunana ob objavi — glej tools/compute_related_posts.py). Če datoteka
  // manjka ali nima vnosa za ta članek, se uporabi obstoječe ujemanje po
  // skupnih tagih kot rezerva.
  if (!SLUG) return;
  Promise.all([
    fetch("/blog.json", { cache: "force-cache" }).then(function (r) { return r.json(); }),
    fetch("/blog/related.json", { cache: "force-cache" }).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; })
  ])
    .then(function (results) {
      var posts = results[0], relatedMap = results[1] || {};
      // Sidebar: "Novejši članki" (neodvisno od tagov)
      var recentBlock = document.querySelector(".blog-sidebar .side-recent");
      if (recentBlock) {
        var recent = posts
          .filter(function (p) { return (p.slug || "").toLowerCase() !== SLUG; })
          .sort(function (a, b) { return a.date < b.date ? 1 : -1; })
          .slice(0, 4);
        if (recent.length) {
          recentBlock.querySelector(".side-list").innerHTML = recent.map(function (p) {
            return '<a class="side-post" href="' + (p.url || ("/blog/" + p.slug + ".html")) + '">' +
              '<span class="side-post-t">' + p.title + '</span>' +
              '<span class="side-post-d">' + fmtDate(p.date) + '</span></a>';
          }).join("");
          recentBlock.hidden = false;
        }
      }

      var me = null;
      posts.forEach(function (p) { if ((p.slug || "").toLowerCase() === SLUG) me = p; });
      if (!me) return;
      var myTags = (me.tags || []).map(function (t) { return String(t).toLowerCase(); });

      // "Teme:" — povezave na kategorijske strani (le tagi z ≥2 objavama = imajo stran)
      if (myTags.length) {
        var freq = {};
        posts.forEach(function (p) {
          (p.tags || []).forEach(function (t) { t = String(t).toLowerCase(); freq[t] = (freq[t] || 0) + 1; });
        });
        var linkable = (me.tags || []).filter(function (t) { return freq[String(t).toLowerCase()] >= 2; });
        if (linkable.length) {
          var trow = document.createElement("div");
          trow.className = "post-topics";
          trow.innerHTML = '<span class="pt-label">Teme:</span> ' + linkable.map(function (t) {
            return '<a class="pt-tag" href="/blog/tema/' + slugify(String(t)) + '/">' + String(t).toLowerCase() + '</a>';
          }).join("");
          var ab = article.querySelector(".author-box"), bl = article.querySelector(".back-link");
          if (ab) article.insertBefore(trow, ab);
          else if (bl) article.insertBefore(trow, bl);
          else article.appendChild(trow);
        }
      }

      var byslug = {};
      posts.forEach(function (p) { byslug[(p.slug || "").toLowerCase()] = p; });

      var scored = [];
      var relSlugs = relatedMap[SLUG] || [];
      relSlugs.forEach(function (s) {
        var p = byslug[String(s).toLowerCase()];
        if (p) scored.push({ p: p });
      });

      if (!scored.length) {
        // rezerva: ujemanje po skupnih tagih (če related.json manjka/prazen)
        scored = posts
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
      }

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
