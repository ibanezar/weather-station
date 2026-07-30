/* ═══════════════════════════════════════════════════════════
   Vrstica za deljenje pod člankom — edini vir.

   Doslej je bila vrstica vpisana v HTML in je obstajala v dveh
   različicah: z ikonami in brez, pri čemer tiste z ikonami ni izpisoval
   noben generator. Objave petih generatorjev so jo imele ali ne, odvisno
   od tega, kdaj so nastale. Zdaj jo izriše ta datoteka in nihče drug:
   če v HTML najde staro vrstico, jo zamenja, sicer jo vstavi.

   Vključi: <script src="/blog/share-bar.js" defer></script>
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var article = document.querySelector("article");
  if (!article) return;

  var canon = document.querySelector('link[rel="canonical"]');
  var ogTitle = document.querySelector('meta[property="og:title"]');
  var ogDesc = document.querySelector('meta[property="og:description"]')
    || document.querySelector('meta[name="description"]');

  var URL_ = (canon && canon.href) || location.href;
  var TITLE = (ogTitle && ogTitle.content) || document.title;
  var TEXT = (ogDesc && ogDesc.content) || TITLE;
  var enc = encodeURIComponent;

  var IKONE = {
    wa: '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.124.555 4.122 1.528 5.855L.044 23.956l6.247-1.463A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.797 9.797 0 01-5.007-1.373l-.36-.214-3.706.869.936-3.619-.234-.371A9.793 9.793 0 012.182 12C2.182 6.57 6.57 2.182 12 2.182S21.818 6.57 21.818 12 17.43 21.818 12 21.818z"/>',
    x: '<path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>',
    fb: '<path d="M24 12.073C24 5.404 18.627 0 12 0S0 5.404 0 12.073C0 18.1 4.388 23.094 10.125 24v-8.437H7.078v-3.49h3.047V9.41c0-3.025 1.791-4.697 4.533-4.697 1.312 0 2.686.236 2.686.236v2.97h-1.513c-1.491 0-1.956.93-1.956 1.887v2.267h3.328l-.532 3.49h-2.796V24C19.612 23.094 24 18.1 24 12.073z"/>'
  };

  function svgPolno(d) {
    return '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">' + d + "</svg> ";
  }
  function svgCrta(d) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"'
      + ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d + "</svg> ";
  }

  function povezava(cls, href, oznaka, napis, ikona) {
    var a = document.createElement("a");
    a.className = "share-btn " + cls;
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener";
    a.setAttribute("aria-label", oznaka);
    a.innerHTML = ikona;
    a.appendChild(document.createTextNode(napis));
    return a;
  }

  var bar = document.createElement("div");
  bar.className = "share-bar";
  bar.id = "share-bar";

  var lbl = document.createElement("span");
  lbl.className = "share-label";
  lbl.textContent = "Deli";
  bar.appendChild(lbl);

  bar.appendChild(povezava("wa", "https://wa.me/?text=" + enc(TEXT + " " + URL_),
    "Deli na WhatsApp", "WhatsApp", svgPolno(IKONE.wa)));
  bar.appendChild(povezava("x", "https://x.com/intent/tweet?text=" + enc(TEXT) + "&url=" + enc(URL_),
    "Deli na X", "X", svgPolno(IKONE.x)));
  bar.appendChild(povezava("fb", "https://www.facebook.com/sharer/sharer.php?u=" + enc(URL_),
    "Deli na Facebooku", "Facebook", svgPolno(IKONE.fb)));

  // ── Instagram ──────────────────────────────────────────────
  // Instagram kot edino od teh omrežij NIMA naslova za deljenje povezave
  // (Facebook ima sharer.php, X intent/tweet, WhatsApp wa.me). Njihova
  // platforma deljenja s spleta ne podpira, zato okna s pripravljeno
  // objavo ni mogoče odpreti. Delujeta samo dve poti: sistemski delilnik
  // na telefonu, kjer je Instagram med cilji, in kopiranje povezave, ki
  // jo uporabnik prilepi v zgodbo, opis profila ali sporočilo — v samo
  // objavo Instagram povezav ne vzame.
  var ig = document.createElement("button");
  ig.className = "share-btn ig";
  ig.setAttribute("aria-label", "Deli na Instagramu");
  ig.title = navigator.share
    ? "Odpre sistemski delilnik, kjer je Instagram med cilji"
    : "Instagram deljenja povezav s spleta ne podpira — povezavo kopiraj in prilepi";
  ig.innerHTML = svgCrta('<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/>'
    + '<circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/>');
  var igNapis = document.createElement("span");
  igNapis.textContent = "Instagram";
  ig.appendChild(igNapis);
  var igVrni = null;
  ig.addEventListener("click", function () {
    if (navigator.share) {
      navigator.share({ title: TITLE, text: TEXT, url: URL_ }).catch(function () {});
      return;
    }
    clearTimeout(igVrni);
    var povej = function (t) {
      igNapis.textContent = t;
      igVrni = setTimeout(function () { igNapis.textContent = "Instagram"; }, 2600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(URL_)
        .then(function () { povej("Povezava kopirana"); })
        .catch(function () { povej("Kopiranje ni uspelo"); });
    } else {
      povej("Kopiraj iz naslovne vrstice");
    }
  });
  bar.appendChild(ig);

  // ── Kopiraj ────────────────────────────────────────────────
  var kop = document.createElement("button");
  kop.className = "share-btn copy";
  kop.setAttribute("aria-label", "Kopiraj povezavo");
  kop.innerHTML = svgCrta('<rect x="9" y="9" width="13" height="13" rx="2"/>'
    + '<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>');
  var kopNapis = document.createElement("span");
  kopNapis.textContent = "Kopiraj";
  kop.appendChild(kopNapis);
  var kopVrni = null;
  kop.addEventListener("click", function () {
    clearTimeout(kopVrni);
    var povej = function (t) {
      kopNapis.textContent = t;
      kopVrni = setTimeout(function () { kopNapis.textContent = "Kopiraj"; }, 2000);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(URL_)
        .then(function () { povej("Kopirano!"); })
        .catch(function () { povej("Ni uspelo"); });
    } else {
      povej("Ni na voljo");
    }
  });
  bar.appendChild(kop);

  // ── Sistemski delilnik (samo kjer obstaja) ─────────────────
  if (navigator.share) {
    var nat = document.createElement("button");
    nat.className = "share-btn native";
    nat.setAttribute("aria-label", "Deli");
    nat.innerHTML = svgCrta('<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/>'
      + '<circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>'
      + '<line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>');
    nat.appendChild(document.createTextNode("Deli"));
    nat.addEventListener("click", function () {
      navigator.share({ title: TITLE, text: TEXT, url: URL_ }).catch(function () {});
    });
    bar.appendChild(nat);
  }

  // Staro vrstico zamenjamo na mestu, da ostane tam, kamor jo je postavil
  // pisec članka; kjer je ni, gre pred povezavo nazaj na blog.
  var stara = document.querySelector(".share-bar");
  if (stara && stara.parentNode) {
    stara.parentNode.replaceChild(bar, stara);
    return;
  }
  var nazaj = article.querySelector(".back-link");
  if (nazaj && nazaj.parentNode === article) article.insertBefore(bar, nazaj);
  else article.appendChild(bar);
})();
