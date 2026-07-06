/* ═══════════════════════════════════════════════════════════
   Seznam bloga — filtriranje po tagih + iskalnik.
   Progresivna nadgradnja: statične kartice ostanejo (SEO), JS
   doda iskalno vrstico, tag-značke in filtriranje obstoječih .post-card.
   Tagi se preberejo iz /blog.json (slug → tags).
   Vključi na /blog/index.html: <script src="/blog/list-enhance.js" defer></script>
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var list = document.querySelector(".post-list");
  if (!list) return;
  var cards = Array.prototype.slice.call(list.querySelectorAll(".post-card"));
  if (!cards.length) return;

  // šumniki → osnovne črke, za iskanje neobčutljivo na diakritiko
  function norm(s) {
    return (s || "").toLowerCase()
      .replace(/č/g, "c").replace(/š/g, "s").replace(/ž/g, "z")
      .replace(/ć/g, "c").replace(/đ/g, "d");
  }

  // slug iz href
  function slugOf(a) {
    var m = (a.getAttribute("href") || "").match(/([a-z0-9][a-z0-9-]*)\.html/i);
    return m ? m[1].toLowerCase() : "";
  }

  // zgradi iskalno/filtrsko vrstico
  var bar = document.createElement("div");
  bar.className = "blog-filter";
  bar.innerHTML =
    '<div class="bf-search">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>' +
      '<input type="search" id="bf-input" placeholder="Išči po člankih…" aria-label="Išči po člankih">' +
    '</div>' +
    '<div class="bf-tags" id="bf-tags" role="group" aria-label="Filtriraj po temi"></div>' +
    '<p class="bf-empty" id="bf-empty" hidden>Ni zadetkov za tvoje iskanje.</p>';
  list.parentNode.insertBefore(bar, list);

  var input   = bar.querySelector("#bf-input");
  var tagWrap = bar.querySelector("#bf-tags");
  var emptyEl = bar.querySelector("#bf-empty");

  var activeTag = null;
  var query = "";
  var tagsBySlug = {};

  // haystack za iskanje (naslov + povzetek iz DOM) po kartici
  cards.forEach(function (a) {
    var li = a.closest("li") || a;
    var title = (a.querySelector("h2") || {}).textContent || "";
    var summary = (a.querySelector("p") || {}).textContent || "";
    a._hay = norm(title + " " + summary);
    a._li = li;
  });

  function apply() {
    var q = norm(query.trim());
    var shown = 0;
    cards.forEach(function (a) {
      var tags = tagsBySlug[slugOf(a)] || [];
      var okTag = !activeTag || tags.indexOf(activeTag) !== -1;
      var hay = a._hay + " " + norm(tags.join(" "));
      var okQ = !q || hay.indexOf(q) !== -1;
      var show = okTag && okQ;
      a._li.style.display = show ? "" : "none";
      if (show) shown++;
    });
    emptyEl.hidden = shown !== 0;
  }

  function setTag(tag) {
    activeTag = (activeTag === tag) ? null : tag;
    Array.prototype.forEach.call(tagWrap.children, function (b) {
      b.classList.toggle("on", b.dataset.tag === activeTag || (activeTag === null && b.dataset.tag === ""));
    });
    apply();
  }

  input.addEventListener("input", function () { query = input.value; apply(); });

  // naloži tage iz blog.json in dogradi značke
  fetch("/blog.json", { cache: "force-cache" })
    .then(function (r) { return r.json(); })
    .then(function (posts) {
      var freq = {};
      posts.forEach(function (p) {
        var slug = (p.slug || "").toLowerCase();
        var tags = (p.tags || []).map(function (t) { return String(t).toLowerCase(); });
        tagsBySlug[slug] = tags;
        tags.forEach(function (t) { freq[t] = (freq[t] || 0) + 1; });
      });

      // tag-značke v vsako kartico
      cards.forEach(function (a) {
        var tags = tagsBySlug[slugOf(a)];
        if (!tags || !tags.length) return;
        var body = a.querySelector(".post-card-body") || a;
        var wrap = document.createElement("div");
        wrap.className = "card-tags";
        wrap.innerHTML = tags.slice(0, 4).map(function (t) {
          return '<span class="card-tag">' + t + '</span>';
        }).join("");
        body.appendChild(wrap);
      });

      // filtrska vrstica: "Vse" + tagi po pogostosti (samo tisti z >=2 pojavitvama)
      var top = Object.keys(freq)
        .filter(function (t) { return freq[t] >= 2; })
        .sort(function (a, b) { return freq[b] - freq[a] || a.localeCompare(b); });

      var allBtn = document.createElement("button");
      allBtn.type = "button"; allBtn.className = "bf-tag on"; allBtn.dataset.tag = "";
      allBtn.textContent = "Vse";
      allBtn.addEventListener("click", function () { setTag(null); });
      tagWrap.appendChild(allBtn);

      top.forEach(function (t) {
        var b = document.createElement("button");
        b.type = "button"; b.className = "bf-tag"; b.dataset.tag = t;
        b.innerHTML = t + ' <span class="bf-count">' + freq[t] + '</span>';
        b.addEventListener("click", function () { setTag(t); });
        tagWrap.appendChild(b);
      });
    })
    .catch(function () { /* brez tagov iskalnik še vedno deluje po besedilu */ });
})();
