/* ═══════════════════════════════════════════════════════════
   Seznam bloga — vse nadgradnje kartic na enem mestu:
   • iskalnik + filtriranje po tagih (iz blog.json, skrčeno na top N + "več")
   • povprečna ocena + značka "Priljubljeno" (bulk /blog-comments)
   • število komentarjev, število všečkov (bulk /like) + značka "novo"
   • tematska emoji značka na vsaki kartici (iz tagov, brez odvisnosti od
     angažma-podatkov, da seznam ni prazen/bogi tudi brez ocen/komentarjev)
   • razvrščanje: najnovejše / najbolje ocenjeno / največ komentarjev / všečkov
   Progresivna nadgradnja — statične kartice ostanejo (SEO).
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  var PROXY = "https://weatherireica1.filip-eremita.workers.dev";
  var NEW_DAYS = 14;
  var TAGS_VISIBLE = 8;

  // Tematska emoji značka na kartici — prvi ujemajoč se tag zmaga (vrstni
  // red spodaj = prioriteta). Ne zahteva zunanjih podatkov, zato je na
  // seznamu vedno nekaj vizualnega, tudi brez ocen/komentarjev/všečkov.
  var TOPIC_EMOJI = [
    ["rekord", "🏆"], ["poplav", "🌊"], ["vodostaj", "🌊"], ["sneg", "❄️"], ["smucisce", "❄️"],
    ["golte", "🏔️"], ["megla", "🌫️"], ["inverzij", "🌫️"], ["neviht", "⛈️"], ["toca", "⛈️"],
    ["hudournik", "⛈️"], ["arcus", "⛈️"], ["mraz", "🥶"], ["hladn", "🥶"], ["susa", "🏜️"],
    ["vrocin", "🔥"], ["pozar", "🔥"], ["dez", "🌧️"], ["padavin", "🌧️"], ["naliv", "🌧️"],
    ["veter", "💨"], ["pritisk", "💨"], ["zracni-tlak", "💨"], ["gobe", "🍄"], ["hmelj", "🌾"],
    ["agrometeo", "🌾"], ["kakovost-zraka", "🌬️"], ["ozon", "🌬️"], ["padalci", "🪂"],
    ["vodna-bilanca", "💧"], ["evapotranspiracij", "💧"], ["zgodovina", "📜"], ["arhiv", "📜"],
    ["trend", "📈"], ["ogrevanj", "📈"], ["podnebj", "📈"], ["klima", "📈"], ["temperatur", "🌡️"],
    ["tropska-noc", "🌡️"], ["pomlad", "🌱"], ["povzetek", "📋"]
  ];
  function topicEmoji(tags) {
    var normed = tags.map(norm);
    for (var i = 0; i < TOPIC_EMOJI.length; i++) {
      for (var j = 0; j < normed.length; j++) {
        if (normed[j].indexOf(TOPIC_EMOJI[i][0]) !== -1) return TOPIC_EMOJI[i][1];
      }
    }
    return "🌤️";
  }

  var list = document.querySelector(".post-list");
  if (!list) return;
  var cards = Array.prototype.slice.call(list.querySelectorAll(".post-card[href]"));
  if (!cards.length) return;

  function norm(s) {
    return (s || "").toLowerCase()
      .replace(/č/g, "c").replace(/š/g, "s").replace(/ž/g, "z").replace(/ć/g, "c").replace(/đ/g, "d");
  }
  function slugOf(a) {
    var m = (a.getAttribute("href") || "").match(/([a-z0-9][a-z0-9-]*)\.html(?:[#?].*)?$/i);
    return m ? m[1].toLowerCase() : "";
  }
  function starHtml(n) {
    var o = ""; for (var i = 1; i <= 5; i++) o += '<span class="pr-star' + (i <= n ? " on" : "") + '">★</span>'; return o;
  }
  function pl(n, one, two, few, many) {
    var m = n % 100; if (m === 1) return one; if (m === 2) return two; if (m === 3 || m === 4) return few; return many;
  }

  // per-card podatki
  var data = {}; // slug → { li, body, date, tags, avg, ratingCount, commentCount, likes, order }
  cards.forEach(function (a, i) {
    var slug = slugOf(a); if (!slug) return;
    var li = a.closest("li") || a;
    var title = (a.querySelector("h2") || {}).textContent || "";
    var summary = (a.querySelector("p") || {}).textContent || "";
    data[slug] = { a: a, li: li, body: a.querySelector(".post-card-body") || a,
      hay: norm(title + " " + summary), tags: [], date: "", avg: null, ratingCount: 0,
      commentCount: 0, likes: 0, order: i };
  });
  var slugs = Object.keys(data);
  if (!slugs.length) return;

  // ── filtrska + razvrščevalna vrstica ──
  var bar = document.createElement("div");
  bar.className = "blog-filter";
  bar.innerHTML =
    '<div class="bf-top">' +
      '<div class="bf-search">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>' +
        '<input type="search" id="bf-input" placeholder="Išči po člankih…" aria-label="Išči po člankih">' +
      '</div>' +
      '<label class="bf-sort"><span>Razvrsti:</span>' +
        '<select id="bf-sort" aria-label="Razvrsti članke">' +
          '<option value="new">Najnovejše</option>' +
          '<option value="rating">Najbolje ocenjeno</option>' +
          '<option value="comments">Največ komentarjev</option>' +
          '<option value="likes">Največ všečkov</option>' +
        '</select>' +
      '</label>' +
    '</div>' +
    '<div class="bf-tags" id="bf-tags" role="group" aria-label="Filtriraj po temi"></div>' +
    '<p class="bf-empty" id="bf-empty" hidden>Ni zadetkov za tvoje iskanje.</p>';
  list.parentNode.insertBefore(bar, list);

  var input = bar.querySelector("#bf-input");
  var tagWrap = bar.querySelector("#bf-tags");
  var emptyEl = bar.querySelector("#bf-empty");
  var sortSel = bar.querySelector("#bf-sort");
  var activeTag = null, query = "";

  function apply() {
    var q = norm(query.trim()), shown = 0;
    slugs.forEach(function (s) {
      var d = data[s];
      var okTag = !activeTag || d.tags.indexOf(activeTag) !== -1;
      var okQ = !q || (d.hay + " " + norm(d.tags.join(" "))).indexOf(q) !== -1;
      var show = okTag && okQ;
      d.li.style.display = show ? "" : "none";
      if (show) shown++;
    });
    emptyEl.hidden = shown !== 0;
  }
  function sortBy(mode) {
    var arr = slugs.slice();
    arr.sort(function (a, b) {
      var x = data[a], y = data[b];
      if (mode === "rating") return (y.avg || -1) - (x.avg || -1) || y.ratingCount - x.ratingCount || x.order - y.order;
      if (mode === "comments") return y.commentCount - x.commentCount || x.order - y.order;
      if (mode === "likes") return y.likes - x.likes || x.order - y.order;
      return x.order - y.order; // new = izvirni vrstni red (najnovejše prvo)
    });
    arr.forEach(function (s) { list.appendChild(data[s].li); });
  }
  function setTag(tag) {
    activeTag = (activeTag === tag) ? null : tag;
    Array.prototype.forEach.call(tagWrap.children, function (b) {
      b.classList.toggle("on", b.dataset.tag === activeTag || (activeTag === null && b.dataset.tag === ""));
    });
    apply();
  }
  input.addEventListener("input", function () { query = input.value; apply(); });
  sortSel.addEventListener("change", function () { sortBy(sortSel.value); });

  // predizpolni iskanje iz ?q= (npr. s 404 strani)
  try {
    var pq = new URLSearchParams(location.search).get("q");
    if (pq) { input.value = pq; query = pq; apply(); input.focus(); }
  } catch (_) {}

  function renderMeta(slug) {
    var d = data[slug], parts = [];
    if (d.ratingCount) {
      parts.push('<span class="post-rating"><span class="pr-avg">' + d.avg.toFixed(1) + '</span>' +
        '<span class="pr-stars">' + starHtml(Math.round(d.avg)) + '</span>' +
        '<span class="pr-count">' + d.ratingCount + ' ' + pl(d.ratingCount, "ocena", "oceni", "ocene", "ocen") + '</span></span>');
    }
    if (d.commentCount) {
      parts.push('<span class="post-comments">💬 ' + d.commentCount + ' ' +
        pl(d.commentCount, "komentar", "komentarja", "komentarji", "komentarjev") + '</span>');
    }
    if (d.likes) {
      parts.push('<span class="post-likes">☀️ ' + d.likes + '</span>');
    }
    if (parts.length) {
      var row = document.createElement("div");
      row.className = "post-meta-row";
      row.innerHTML = parts.join("");
      d.body.appendChild(row);
    }
    if (d.avg >= 4.5 && d.ratingCount >= 3) {
      var pop = document.createElement("span"); pop.className = "post-pop"; pop.textContent = "★ Priljubljeno";
      d.body.appendChild(pop);
    }
  }
  function markNew(slug) {
    var d = data[slug]; if (!d.date) return;
    var age = (Date.now() - new Date(d.date).getTime()) / 86400000;
    if (age >= 0 && age <= NEW_DAYS) {
      var card = d.a, dateEl = card.querySelector(".date");
      var b = document.createElement("span"); b.className = "post-new"; b.textContent = "novo";
      if (dateEl) dateEl.insertBefore(b, dateEl.firstChild); else d.body.insertBefore(b, d.body.firstChild);
    }
  }

  // ── podatki: blog.json (tagi+datumi) + bulk ocene/komentarji/všečki ──
  Promise.all([
    fetch("/blog.json", { cache: "force-cache" }).then(function (r) { return r.json(); }).catch(function () { return []; }),
    fetch(PROXY + "/blog-comments?slugs=" + encodeURIComponent(slugs.join(","))).then(function (r) { return r.json(); }).catch(function () { return {}; }),
    fetch(PROXY + "/like?slugs=" + encodeURIComponent(slugs.join(","))).then(function (r) { return r.json(); }).catch(function () { return {}; })
  ]).then(function (res) {
    var posts = res[0] || [], bulk = res[1] || {}, likeBulk = res[2] || {};
    var ratings = bulk.ratings || {}, comments = bulk.comments || {}, likes = likeBulk.likes || {};
    var freq = {};
    posts.forEach(function (p) {
      var slug = (p.slug || "").toLowerCase();
      if (!data[slug]) return;
      var tags = (p.tags || []).map(function (t) { return String(t).toLowerCase(); });
      data[slug].tags = tags;
      data[slug].date = p.date || "";
      tags.forEach(function (t) { freq[t] = (freq[t] || 0) + 1; });
    });
    slugs.forEach(function (s) {
      var r = ratings[s];
      if (r) { data[s].avg = r.avg; data[s].ratingCount = r.count || 0; }
      data[s].commentCount = comments[s] || 0;
      data[s].likes = likes[s] || 0;
    });

    // tag-značke + emoji tema + meta + novo
    slugs.forEach(function (s) {
      var d = data[s], tags = d.tags;
      if (tags.length) {
        var wrap = document.createElement("div");
        wrap.className = "card-tags";
        wrap.innerHTML = tags.slice(0, 4).map(function (t) { return '<span class="card-tag">' + t + '</span>'; }).join("");
        d.body.appendChild(wrap);
      }
      var emoji = document.createElement("span");
      emoji.className = "card-emoji";
      emoji.setAttribute("aria-hidden", "true");
      emoji.textContent = topicEmoji(tags);
      var thumb = d.a.querySelector(".post-thumb");
      if (thumb) thumb.insertAdjacentElement("afterend", emoji); else d.a.insertBefore(emoji, d.a.firstChild);
      renderMeta(s);
      markNew(s);
    });

    // filtrska vrstica z najpogostejšimi tagi — skrčena na TAGS_VISIBLE + "Več"
    var top = Object.keys(freq).filter(function (t) { return freq[t] >= 2; })
      .sort(function (a, b) { return freq[b] - freq[a] || a.localeCompare(b); });
    var allBtn = document.createElement("button");
    allBtn.type = "button"; allBtn.className = "bf-tag on"; allBtn.dataset.tag = ""; allBtn.textContent = "Vse";
    allBtn.addEventListener("click", function () { setTag(null); });
    tagWrap.appendChild(allBtn);
    top.forEach(function (t, i) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "bf-tag"; b.dataset.tag = t;
      if (i >= TAGS_VISIBLE) b.hidden = true;
      b.innerHTML = t + ' <span class="bf-count">' + freq[t] + '</span>';
      b.addEventListener("click", function () { setTag(t); });
      tagWrap.appendChild(b);
    });
    if (top.length > TAGS_VISIBLE) {
      var moreBtn = document.createElement("button");
      moreBtn.type = "button"; moreBtn.className = "bf-tag bf-more";
      moreBtn.textContent = "+" + (top.length - TAGS_VISIBLE) + " več";
      moreBtn.addEventListener("click", function () {
        var expanded = moreBtn.dataset.expanded === "1";
        Array.prototype.slice.call(tagWrap.querySelectorAll('.bf-tag[data-tag]:not([data-tag=""])')).slice(TAGS_VISIBLE).forEach(function (b) {
          b.hidden = expanded;
        });
        moreBtn.dataset.expanded = expanded ? "0" : "1";
        moreBtn.textContent = expanded ? "+" + (top.length - TAGS_VISIBLE) + " več" : "Manj ▲";
      });
      tagWrap.appendChild(moreBtn);
    }

    buildSidebar(top, freq);
  });

  function tslug(t) {
    return String(t).toLowerCase().replace(/č/g, "c").replace(/š/g, "s").replace(/ž/g, "z")
      .replace(/ć/g, "c").replace(/đ/g, "d").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }
  function esc(s) { return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

  function buildSidebar(top, freq) {
    var aside = document.createElement("aside");
    aside.className = "blog-sidebar";
    var html = "";

    // Kategorije (tagi z lastno stranjo = ≥2 objavama)
    if (top.length) {
      html += '<div class="side-block"><div class="side-title">Kategorije</div><div class="side-cats">' +
        top.slice(0, 12).map(function (t) {
          return '<a class="side-cat" href="/blog/tema/' + tslug(t) + '/">' + esc(t) + ' <span>' + freq[t] + '</span></a>';
        }).join("") + '</div></div>';
    }

    // Najbolje ocenjeni
    var rated = slugs.filter(function (s) { return data[s].ratingCount > 0; })
      .sort(function (a, b) { return data[b].avg - data[a].avg || data[b].ratingCount - data[a].ratingCount; })
      .slice(0, 4);
    if (rated.length) {
      html += '<div class="side-block"><div class="side-title">Najbolje ocenjeni</div><div class="side-list">' +
        rated.map(function (s) {
          var title = (data[s].a.querySelector("h2") || {}).textContent || s;
          return '<a class="side-post" href="' + data[s].a.getAttribute("href") + '"><span class="side-post-t">' + esc(title) + '</span>' +
            '<span class="side-post-r">★ ' + data[s].avg.toFixed(1) + '</span></a>';
        }).join("") + '</div></div>';
    }

    // Prijava + RSS
    html += '<div class="side-block side-actions">' +
      '<button type="button" class="side-sub" id="side-sub">📬 Prijava na novičke</button>' +
      '<a class="side-back" href="/blog/rss.xml">📡 RSS vir</a>' +
    '</div>';

    aside.innerHTML = html;
    (document.querySelector(".wrap") || document.body).appendChild(aside);
    document.body.classList.add("has-blog-sidebar");

    var sb = aside.querySelector("#side-sub");
    if (sb) sb.addEventListener("click", function () {
      var box = document.querySelector(".subscribe-box");
      if (box) { box.scrollIntoView({ behavior: "smooth", block: "center" });
        var inp = box.querySelector("input"); if (inp) setTimeout(function () { inp.focus(); }, 500); }
    });
  }
})();
