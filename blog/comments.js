/* ═══════════════════════════════════════════════════════════
   Blog komentarji + ocene — samostojni widget
   Vključi na koncu članka z:  <script src="/blog/comments.js" defer></script>
   Slug se samodejno izpelje iz poti (/blog/<slug>.html).
   Backend: Cloudflare Worker, pot /blog-comments (shramba v R2).
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var PROXY = "https://weatherireica1.filip-eremita.workers.dev";

  // Slug iz /blog/<slug>.html
  var m = location.pathname.match(/\/blog\/([a-z0-9][a-z0-9-]*)\.html$/i);
  if (!m) return;
  var SLUG = m[1].toLowerCase();

  var STORE_KEY = "meteorec_comment_author";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function timeAgo(iso) {
    var t = new Date(iso).getTime();
    if (isNaN(t)) return "";
    var s = Math.floor((Date.now() - t) / 1000);
    if (s < 60) return "pravkar";
    var mn = Math.floor(s / 60); if (mn < 60) return mn + " min nazaj";
    var h = Math.floor(mn / 60); if (h < 24) return "pred " + h + " h";
    var d = Math.floor(h / 24); if (d < 30) return "pred " + d + " dnevi";
    return new Date(iso).toLocaleDateString("sl-SI");
  }

  function stars(n, filled) {
    var out = "";
    for (var i = 1; i <= 5; i++) {
      out += '<span class="cmt-star' + (i <= (filled || n) ? " on" : "") + '">★</span>';
    }
    return out;
  }

  // ── Zgradi DOM ────────────────────────────────────────────
  var host = document.createElement("section");
  host.className = "cmt-section";
  host.id = "komentarji";
  host.innerHTML =
    '<h2 class="cmt-title">Komentarji</h2>' +
    '<div class="cmt-rating-summary" id="cmt-summary"></div>' +
    '<form class="cmt-form" id="cmt-form" autocomplete="off">' +
      '<div class="cmt-rate-row">' +
        '<span class="cmt-rate-label">Tvoja ocena članka:</span>' +
        '<span class="cmt-stars-input" id="cmt-stars-input" role="radiogroup" aria-label="Ocena članka">' +
          [1,2,3,4,5].map(function (i) {
            return '<button type="button" class="cmt-star-btn" data-val="' + i + '" aria-label="' + i + ' od 5">★</button>';
          }).join("") +
        '</span>' +
        '<button type="button" class="cmt-rate-clear" id="cmt-rate-clear" title="Počisti oceno" hidden>×</button>' +
      '</div>' +
      '<input class="cmt-input" id="cmt-author" type="text" maxlength="60" placeholder="Ime (neobvezno)">' +
      // Honeypot proti botom — skrito pred uporabniki
      '<input class="cmt-hp" type="text" name="website" id="cmt-hp" tabindex="-1" autocomplete="off" aria-hidden="true">' +
      '<textarea class="cmt-input cmt-textarea" id="cmt-text" maxlength="1500" rows="3" placeholder="Napiši komentar…"></textarea>' +
      '<div class="cmt-form-foot">' +
        '<span class="cmt-msg" id="cmt-msg" aria-live="polite"></span>' +
        '<button class="cmt-submit" id="cmt-submit" type="submit">Objavi</button>' +
      '</div>' +
    '</form>' +
    '<div class="cmt-list" id="cmt-list"><p class="cmt-empty">Nalagam komentarje…</p></div>';

  // Vstavi pred footer, sicer na konec .wrap/body
  var foot = document.querySelector(".site-foot");
  if (foot && foot.parentNode) {
    foot.parentNode.insertBefore(host, foot);
  } else {
    (document.querySelector(".wrap") || document.body).appendChild(host);
  }

  var chosenRating = 0;
  var starsInput  = host.querySelector("#cmt-stars-input");
  var clearBtn    = host.querySelector("#cmt-rate-clear");
  var starBtns    = Array.prototype.slice.call(host.querySelectorAll(".cmt-star-btn"));
  var authorEl    = host.querySelector("#cmt-author");
  var textEl      = host.querySelector("#cmt-text");
  var msgEl       = host.querySelector("#cmt-msg");
  var submitEl    = host.querySelector("#cmt-submit");
  var listEl      = host.querySelector("#cmt-list");
  var summaryEl   = host.querySelector("#cmt-summary");

  try { authorEl.value = localStorage.getItem(STORE_KEY) || ""; } catch (_) {}

  function paintStars(hover) {
    var upto = hover || chosenRating;
    starBtns.forEach(function (b) {
      b.classList.toggle("on", parseInt(b.dataset.val) <= upto);
    });
    clearBtn.hidden = chosenRating === 0;
  }
  starBtns.forEach(function (b) {
    b.addEventListener("mouseenter", function () { paintStars(parseInt(b.dataset.val)); });
    b.addEventListener("click", function () {
      chosenRating = parseInt(b.dataset.val);
      paintStars();
    });
  });
  starsInput.addEventListener("mouseleave", function () { paintStars(); });
  clearBtn.addEventListener("click", function () { chosenRating = 0; paintStars(); });

  function setMsg(text, isErr) {
    msgEl.textContent = text || "";
    msgEl.className = "cmt-msg" + (isErr ? " err" : "");
  }

  function renderSummary(rating) {
    if (rating && rating.count > 0) {
      summaryEl.innerHTML =
        '<span class="cmt-avg">' + rating.avg.toFixed(1) + '</span>' +
        '<span class="cmt-avg-stars">' + stars(Math.round(rating.avg)) + '</span>' +
        '<span class="cmt-avg-count">' + rating.count + ' ' + plural(rating.count, "ocena", "oceni", "ocene", "ocen") + '</span>';
      summaryEl.style.display = "";
      injectRatingSchema(rating);
    } else {
      summaryEl.style.display = "none";
    }
  }

  // Strukturirani podatki (schema.org aggregateRating) — vidni tudi
  // iskalnikom/orodjem; ocene so na strani dejansko prikazane.
  function injectRatingSchema(rating) {
    var old = document.getElementById("cmt-rating-schema");
    if (old) old.remove();
    var canon = document.querySelector('link[rel="canonical"]');
    var url = (canon && canon.href) || location.href;
    var title = (document.querySelector('meta[property="og:title"]') || {}).content
      || document.title.replace(/\s*\|.*$/, "");
    var data = {
      "@context": "https://schema.org",
      "@type": "BlogPosting",
      "@id": url + "#article",
      "headline": title,
      "url": url,
      "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": Number(rating.avg.toFixed(2)),
        "ratingCount": rating.count,
        "bestRating": 5,
        "worstRating": 1
      }
    };
    var s = document.createElement("script");
    s.type = "application/ld+json";
    s.id = "cmt-rating-schema";
    s.textContent = JSON.stringify(data);
    document.head.appendChild(s);
  }

  function plural(n, one, two, few, many) {
    var mod100 = n % 100, mod10 = n % 10;
    if (mod100 === 1) return one;
    if (mod100 === 2) return two;
    if (mod100 === 3 || mod100 === 4) return few;
    return many;
  }

  function renderList(comments) {
    if (!comments || !comments.length) {
      listEl.innerHTML = '<p class="cmt-empty">Še ni komentarjev. Bodi prvi!</p>';
      return;
    }
    listEl.innerHTML = comments.map(function (c) {
      return '<div class="cmt-item">' +
        '<div class="cmt-item-head">' +
          '<span class="cmt-author">' + esc(c.author || "Anonimno") + '</span>' +
          (c.rating ? '<span class="cmt-item-stars">' + stars(c.rating) + '</span>' : '') +
          '<span class="cmt-time">' + esc(timeAgo(c.ts)) + '</span>' +
        '</div>' +
        (c.comment ? '<div class="cmt-body">' + esc(c.comment).replace(/\n/g, "<br>") + '</div>' : '') +
      '</div>';
    }).join("");
  }

  function load() {
    fetch(PROXY + "/blog-comments?slug=" + encodeURIComponent(SLUG), { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        renderSummary(d.rating);
        renderList(d.comments);
      })
      .catch(function () {
        listEl.innerHTML = '<p class="cmt-empty">Komentarjev trenutno ni mogoče naložiti.</p>';
      });
  }

  host.querySelector("#cmt-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var comment = textEl.value.trim();
    var author  = authorEl.value.trim();
    if (!comment && !chosenRating) {
      setMsg("Napiši komentar ali oddaj oceno.", true);
      return;
    }
    if (host.querySelector("#cmt-hp").value) return; // bot
    setMsg("");
    submitEl.disabled = true;
    submitEl.textContent = "Objavljam…";

    fetch(PROXY + "/blog-comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        slug: SLUG,
        comment: comment,
        author: author,
        rating: chosenRating || null,
        website: ""
      })
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok || res.j.error) {
          setMsg(res.j.error || "Napaka pri objavi.", true);
          return;
        }
        try { if (author) localStorage.setItem(STORE_KEY, author); } catch (_) {}
        textEl.value = "";
        chosenRating = 0;
        paintStars();
        setMsg("Hvala za tvoj prispevek!");
        if (res.j.rating) renderSummary(res.j.rating);
        load();
      })
      .catch(function () {
        setMsg("Napaka v povezavi. Poskusi znova.", true);
      })
      .then(function () {
        submitEl.disabled = false;
        submitEl.textContent = "Objavi";
      });
  });

  load();
})();
