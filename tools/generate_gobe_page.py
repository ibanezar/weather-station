#!/usr/bin/env python3
"""
tools/generate_gobe_page.py — Gobarska napoved: freemium sales + forecast page

Renders /gobarska-napoved/index.html: a server-rendered mushroom-foraging
landing page for Zgornja Savinjska dolina built on the species-level model
(tools/gobe_model.py) and the 50-species local database (species_rules.yaml).

Layout:
  * FREE (public, crawlable): today's overall index, today's index per forest,
    the 50-species reference table with edibility + dangerous doubles, the
    monthly calendar, the terrain map and FAQ. Strong SEO + mycological
    credibility, all static HTML.
  * PREMIUM (gated): the forward-looking 7-day, per-species, per-location
    forecast with plain-language explanations. Rendered as a locked placeholder;
    the real content is fetched client-side from the Worker /premium/forecast
    endpoint only when a valid access token is present.

Positioning: the index is an "indeks ugodnosti pogojev" (favourability index),
never a promise of finds — scientifically honest and it protects against angry
subscribers.

Usage:
  python3 tools/generate_gobe_page.py
"""
import datetime as _dt
import json as _json_mod
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers
import gobe_model as gm           # noqa: E402 — species model + DB loader

ROOT = seo.ROOT
TODAY = seo.TODAY

# Cloudflare Worker base (paywall API). Same host as the rest of the site proxy.
WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"

# Paddle.js overlay checkout — fill in after creating the products (docs/premium-setup.md).
# The client-side token is safe to expose publicly. Price IDs must match wrangler.toml.
# TODO: nastavi Paddle vrednosti; dokler je token prazen, gumbi varno padejo na #pricing.
PADDLE_ENV = "production"            # "sandbox" za testiranje, "production" za v živo
PADDLE_CLIENT_TOKEN = ""             # TODO: odjemalski žeton iz Paddle (Developer Tools → Authentication)
PADDLE_PRICE_MONTHLY = "pri_REPLACE_MONTHLY"  # TODO: enako kot v wrangler.toml
PADDLE_PRICE_SEASON = "pri_REPLACE_SEASON"    # TODO: enako kot v wrangler.toml

PRICE_MONTHLY = "3,99 €"
PRICE_SEASON = "24,99 €"

MES_FULL = ["januarju", "februarju", "marcu", "aprilu", "maju", "juniju",
            "juliju", "avgustu", "septembru", "oktobru", "novembru", "decembru"]
DAN_KRATKO = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]

# Edibility → (badge label, CSS colour class)
EDIB_STYLE = {
    "užitna":          ("Užitna", "e-ok"),
    "pogojno užitna":  ("Pogojno užitna", "e-cond"),
    "neužitna":        ("Neužitna", "e-none"),
    "strupena":        ("Strupena", "e-tox"),
    "zelo strupena":   ("Zelo strupena", "e-tox2"),
    "smrtno strupena": ("Smrtno strupena", "e-death"),
    "zaščitena":       ("Zaščitena", "e-prot"),
}


def edib_badge(edibility):
    label, cls = EDIB_STYLE.get((edibility or "").lower().strip(), (edibility or "?", "e-none"))
    return f'<span class="gp-badge {cls}">{seo.esc(label) if hasattr(seo, "esc") else label}</span>'


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


import collections as _collections
import re as _re
import unicodedata as _ud

_DOUBLE_PAT = _re.compile(r"^(.+?)\s*\(([^)]+)\)\s*[–-]\s*(.+)$")


def _slug(name):
    s = _ud.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return _re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()


def parse_double(text):
    """'<Ime> (<Latin>) – <opis>' -> (name, latin, [bullets]); None if the
    text doesn't follow that pattern (still shown as a plain info line)."""
    m = _DOUBLE_PAT.match(text or "")
    if not m:
        return None
    name, latin, desc = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    bullets = [b.strip().rstrip(".") for b in _re.split(r";", desc) if b.strip()][:3]
    return name, latin, bullets


def double_danger(text):
    """Danger tier of the *double* (not the edible species itself), for
    sorting/badging — worst-case wording wins if multiple appear."""
    t = (text or "").lower()
    if "smrtno strupen" in t:
        return "smrtno strupena"
    if "zelo strupen" in t:
        return "zelo strupena"
    if "strupen" in t:
        return "strupena"
    if "zaščiten" in t:
        return "zaščitena"
    if "neužit" in t:
        return "neužitna"
    # "prav tako užitna" — dvojnica, ki ni nevarna, je pogosta pri parih znotraj
    # istega rodu. Mora se preverjati za "neužit", ki vsebuje isti koren.
    if "užitn" in t or "užiten" in t:
        return "užitna"
    # Brez besede o užitnosti ne trdimo ničesar; prej je privzeto vrnilo
    # "neužitna" in stran je užitnim dvojnicam pripisala neužitnost.
    return None


# Užitnost → ključ filtra. Strupene stopnje se združijo v enega, ker nabiralca
# pri brskanju zanima »ne jej«, ne pa katera od treh stopenj.
EDIB_FILTER = {
    "užitna": "uzitna",
    "pogojno užitna": "pogojno",
    "neužitna": "neuzitna",
    "strupena": "strupena",
    "zelo strupena": "strupena",
    "smrtno strupena": "strupena",
    "zaščitena": "zascitena",
}
FILTER_LABELS = [("uzitna", "Užitne"), ("pogojno", "Pogojno užitne"),
                 ("strupena", "Strupene"), ("neuzitna", "Neužitne"),
                 ("zascitena", "Zaščitene")]

# Baza vrst je razbita na podstrani po užitnosti. Ena stran s 300 karticami je
# 416 kB in za iskalnik en sam cilj; po skupinah je vsaka desetinka tega in ima
# svoj naslov ("užitne gobe", "strupene gobe"), po katerem jo ljudje iščejo.
# (pot pod /baza-vrst/, ključ filtra, ime v navigaciji, naslov strani, opis)
BAZA_CATS = [
    ("", None, "Vse",
     "Baza {n} vrst gob — užitnost in nevarne dvojnice",
     "Referenčna baza {n} vrst gob Zgornje Savinjske doline: užitnost, sezona in nevarne dvojnice."),
    ("uzitne", "uzitna", "Užitne",
     "Užitne gobe Zgornje Savinjske doline — {n} vrst",
     "{n} užitnih vrst gob doline: sezona, rastišče in nevarne dvojnice za vsako."),
    ("pogojno-uzitne", "pogojno", "Pogojno užitne",
     "Pogojno užitne gobe — {n} vrst in kako jih pripraviti",
     "{n} pogojno užitnih vrst: surove so strupene ali težko prebavljive, z opozorili na dvojnice."),
    ("strupene", "strupena", "Strupene",
     "Strupene gobe Slovenije — {n} vrst s fotografijami",
     "{n} strupenih vrst gob, ki jih je mogoče zamenjati z užitnimi — s ključno razliko za varno ločevanje."),
    ("neuzitne", "neuzitna", "Neužitne",
     "Neužitne gobe — {n} vrst iz baze doline",
     "{n} neužitnih vrst: niso strupene, a na krožnik ne sodijo. Pogosto dvojnice užitnih vrst."),
]


def format_season_range(start, end):
    """'MM.DD' raw storage → localized Slovenian display, e.g.
    '09.01'/'11.30' → '1. 9.–30. 11.'. Display only — cross-year wraparound
    (e.g. '10.01'/'01.31') is handled by gobe_model.in_season(), not here."""
    def fmt(md):
        m, d = md.split(".")
        return f"{int(d)}. {int(m)}."
    return f"{fmt(start)}–{fmt(end)}"


def species_section_html(subset, all_species, current=""):
    """Orodna vrstica (iskanje + povezave na kategorije + filter sezone) in
    mreža kartic za dano podmnožico vrst.

    Kartice so v HTML vse, prikaže pa se jih naenkrat le prvih nekaj (SP_JS).
    Med kategorijami se hodi po povezavah, ne s filtrom v JS — vsaka skupina
    ima svoj URL in naslov, tako da jo iskalnik lahko pokaže neposredno."""
    now_month = TODAY.month
    cards = []
    for s in sorted(subset, key=lambda x: (not x.get("gets_index"), x["name_sl"])):
        se = s["season"]
        season_txt = format_season_range(se["start"], se["end"])
        edib = (s.get("edibility") or "").lower().strip()
        cls = EDIB_STYLE.get(edib, (None, "e-none"))[1]
        # Podatki za filtriranje in iskanje na strani; iskalni niz je že
        # normaliziran, da JS ne ponavlja odstranjevanja šumnikov ob vsakem tipku.
        data_attrs = (f'data-m="{",".join(str(m) for m in sorted(season_months(s)))}" '
                      f'data-q="{_esc(_search_key(s["name_sl"] + " " + s["name_lat"]))}"')
        dbl = s.get("doubles")
        dbl_html = (f'<div class="gp-sp-dbl"><b>Dvojnica:</b> {_esc(dbl)}</div>' if dbl else "")
        # Vrste iz razširjenega seznama so sestavljene iz literature, ne
        # preverjene na terenu v dolini — to mora biti na kartici vidno, ker
        # gre tudi za podatek o užitnosti.
        unver_html = ("" if s.get("verified", True) else
                      '<div class="gp-sp-unver" title="Vnos iz razširjenega seznama; '
                      'podatki so iz literature in niso terensko preverjeni">◌ ni terensko preverjeno</div>')
        cards.append(f'''    <div class="gp-sp-card" {data_attrs}>
      <div class="gp-sp-top {cls}">
        <img src="/gobarska-napoved/img/vrste/{s['id']}.jpg" alt="{_esc(s['name_sl'])}" loading="lazy"
          onerror="this.parentElement.classList.add('ph');this.remove()">
        <span class="gp-sp-emoji">🍄</span>
      </div>
      <div class="gp-sp-body">
        <div class="gp-sp-name">{_esc(s["name_sl"])}</div>
        <div class="gp-sp-lat">{_esc(s["name_lat"])}</div>
        <div class="gp-sp-row">{edib_badge(s.get("edibility"))}<span class="gp-sp-season">📅 {season_txt}</span></div>
        {unver_html}
        {dbl_html}
      </div>
    </div>''')

    by_filter = _collections.Counter(
        EDIB_FILTER.get((s.get("edibility") or "").lower().strip(), "drugo") for s in all_species)
    links = []
    for path, key, label, _t, _d in BAZA_CATS:
        n = len(all_species) if key is None else by_filter[key]
        if not n:
            continue
        href = "/gobarska-napoved/baza-vrst/" + (f"{path}/" if path else "")
        on = " on" if path == current else ""
        links.append(f'      <a class="gp-sp-chip{on}" href="{href}">{_esc(label)} ({n})</a>')

    n_season = sum(1 for s in subset if now_month in season_months(s))
    season_chip = (f'      <button type="button" class="gp-sp-chip" id="gp-sp-season" '
                   f'data-f="sezona">V sezoni zdaj ({n_season})</button>' if n_season else "")
    return (
        '  <div class="gp-sp-tools">\n'
        '    <input type="search" id="gp-sp-q" class="gp-sp-search" placeholder="Poišči vrsto — slovensko ali latinsko ime"\n'
        '      autocomplete="off" aria-label="Iskanje po vrstah">\n'
        '    <nav class="gp-sp-chips" aria-label="Skupine po užitnosti">\n' + "\n".join(links) + "\n    </nav>\n"
        + (f'    <div class="gp-sp-chips">\n{season_chip}\n    </div>\n' if season_chip else "")
        + '    <p class="gp-sp-count" id="gp-sp-count" hidden></p>\n'
        "  </div>\n"
        '  <div class="gp-sp-grid" id="gp-sp-grid">\n' + "\n".join(cards) + "\n  </div>\n"
        '  <div class="gp-sp-more"><button type="button" id="gp-sp-more" hidden>Pokaži več vrst</button></div>')


def _search_key(s):
    """Iskalni niz brez šumnikov in ločil — da 'jurcek' najde 'Jurček'."""
    s = _ud.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    return _re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def season_months(sp):
    """Set of 1-12 month numbers the species' season window covers."""
    out = set()
    for m in range(1, 13):
        # 15th of the month as representative day
        if gm.in_season(_dt.date(2025, m, 15), sp["season"]):
            out.add(m)
    return out


# ── page CSS (scoped, appended in <head>) ─────────────────────────────────────

# Sub-brand swap: gobarska-napoved/ and its subpages show "MeteoGobar" with its
# own mushroom mark instead of the site-wide Meteorec logo/name. Done via a tiny
# synchronous script (runs immediately after the shared header markup is
# parsed) rather than touching generate_seo_pages.py's shared HEADER template —
# every other generated page keeps the plain Meteorec header untouched.
BRAND_SWAP = '''<script>(function(){
  var img=document.querySelector(".site-head .brand-logo");
  var nm=document.querySelector(".site-head .brand-name");
  if(img){img.src="/gobarska-napoved/logo-gobar.svg";img.alt="MeteoGobar";}
  if(nm){nm.innerHTML="Meteo<em>Gobar</em>";}
})();</script>'''

PAGE_CSS = """<style>
/* [hidden] loses to any class setting its own `display` at equal specificity
   (author CSS always beats the UA stylesheet) — e.g. .gp-cta{display:inline-block}
   would otherwise keep a `hidden`-toggled CTA button visible. Force it. */
[hidden]{display:none!important}
/* ── Cross-page transitions (View Transitions API) — opts these 6
   gobarska-napoved/ pages into a native crossfade+slide when navigating
   between them (hub ↔ zemljevid/koledar/trend/baza-vrst/dvojnice). Purely
   progressive enhancement: unsupported browsers (or prefers-reduced-motion)
   just navigate normally, no JS involved either way. Named so the top bar
   and bottom nav — present on every one of these pages — morph in place
   instead of cross-fading with the rest of the content. */
@view-transition{navigation:auto}
@media (prefers-reduced-motion:no-preference){
  ::view-transition-old(root){animation:gp-vt-out .18s ease-out both}
  ::view-transition-new(root){animation:gp-vt-in .22s ease-out both}
  @keyframes gp-vt-out{to{opacity:0;transform:translateY(-6px)}}
  @keyframes gp-vt-in{from{opacity:0;transform:translateY(6px)}}
}
.gp-topbar{view-transition-name:gp-topbar}
.gp-bottomnav{view-transition-name:gp-bottomnav}
/* Earthy sub-theme for this landing page only — scoped to .wrap so it never
   leaks into the shared header/footer markup used by other generated pages.
   CSS custom properties resolve by inheritance (nearest ancestor that sets
   them), so this wins regardless of stylesheet load order. */
/* Set on body (the shared ancestor of both #bg's ambient blobs and .wrap's
   content) so the whole page — including the drifting background glows,
   which were still blue/purple/cyan — moves to a warm brown/green earthy
   palette. Complementary pairing: warm amber-brown base + forest-green
   accent sit roughly opposite on the wheel, so they read as "forest at
   dusk" instead of clashing. */
body{
  --blue:#6fae55; --cyan:#c17f3e; --muted:#a9a08c;
  --bg:#0b0906;
  --card-bg:rgba(19,15,11,.94);
  --stn-bg:rgba(111,174,85,.16); --stn-border:rgba(111,174,85,.45);
  --fc-today-bg:rgba(193,127,62,.14); --fc-today-border:rgba(193,127,62,.35);
  --blob-1:rgba(201,150,80,.20); --blob-2:rgba(111,174,85,.16);
  --blob-3:rgba(140,168,90,.13); --blob-4:rgba(180,110,70,.11);
  /* Bottom nav's own rendered height (icon+label+padding, measured ~3.65rem)
     with a little headroom — single source of truth shared by the nav's
     own box and the page's bottom padding compensation below, so the two
     can't drift apart. */
  --gp-bnh:4rem;
}
.gp-hero{position:relative;overflow:hidden;border:1px solid var(--card-border);border-radius:18px;
  padding:1.6rem;margin:.6rem 0 1.4rem;box-shadow:var(--card-shadow);
  background:linear-gradient(200deg,rgba(8,14,7,.45) 0%,rgba(6,10,6,.72) 55%,rgba(6,10,6,.92) 100%),
    url('/og/bg/gobe-inverzija.jpg') center 35%/cover}
.gp-hero-top{display:flex;align-items:center;gap:1.4rem;flex-wrap:wrap}
.gp-gauge-wrap{position:relative;width:132px;height:132px;flex:0 0 auto}
/* No width/height attrs on the <svg> itself — those are fixed pixel values
   that ignore .gp-gauge-wrap's own size, so the ring silently overflowed its
   104px mobile box (still rendering at its old 132px intrinsic size) while
   the number, correctly scoped via inset:0, stayed centered on the real
   (smaller) box. Filling 100% here keeps the ring locked to whatever size
   the wrapper actually is at every breakpoint. */
.gp-ring{display:block;width:100%;height:100%}
.gp-ring-bg{fill:none;stroke:rgba(255,255,255,.10);stroke-width:11}
.gp-ring-fg{fill:none;stroke-width:11;stroke-linecap:round;transform:rotate(-90deg);transform-origin:64px 64px}
/* % stacked under the number (not beside it) — any side-by-side arrangement
   is lopsided one way or the other, since % only adds width on one side.
   Stacking both lines and centering each independently sidesteps that. */
.gp-gauge-num{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;line-height:1}
.gp-gauge-num .num{font-size:2.7rem;font-weight:800;color:var(--text)}
.gp-gauge-num small{display:block;margin-top:.15rem;font-size:.85rem;color:var(--muted);font-weight:600}
.gp-hero-body{flex:1;min-width:250px}
.gp-hero-kicker{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.gp-hero-lvl{font-size:1.9rem;font-weight:800;line-height:1.1;margin:.1rem 0 .55rem}
.gp-hero-best{font-size:.95rem;color:var(--text);margin-bottom:.75rem}
.gp-hero-best-pct{display:inline-block;font-weight:700;font-size:.8rem;padding:.05rem .45rem;
  border-radius:6px;margin-left:.25rem;font-variant-numeric:tabular-nums}
.gp-hero-topsp{font-size:.95rem;color:var(--text);margin-bottom:.75rem}
.gp-hero-trend{display:flex;align-items:center;gap:.6rem;margin:-.25rem 0 .55rem}
.gp-hero-delta{font-size:.82rem;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums}
.gp-hero-spark .gp-spark{width:84px;height:22px}
/* Thumb-friendly action row right under the gauge — "glanceable" actions
   (share, map, notify) instead of making the user read/scroll for them. */
.gp-action-chips{display:flex;flex-wrap:wrap;gap:.6rem;margin-top:1rem}
.gp-chip-action{display:inline-flex;align-items:center;gap:.4rem;min-height:2.75rem;
  padding:.5rem 1.1rem;border-radius:22px;background:var(--badge-bg);border:1px solid var(--card-border);
  color:var(--text);font:inherit;font-size:.88rem;font-weight:600;text-decoration:none;cursor:pointer}
.gp-chip-action:hover{border-color:var(--blue)}
.gp-hero-note{color:var(--muted);font-size:.85rem;line-height:1.55;margin-top:1rem;
  border-top:1px solid rgba(255,255,255,.09);padding-top:.85rem}
.gp-hero-sub{color:var(--muted);font-size:.9rem;margin-top:.35rem;line-height:1.55}
.gp-h2{margin-top:2.6rem;margin-bottom:.9rem;padding-bottom:.4rem;border-bottom:1px solid var(--border);
  font-size:1.35rem;scroll-margin-top:4rem}
.gp-h2 + .archive-intro,.gp-h2 + .post-meta{margin-top:-.3rem}
.gp-cta{display:inline-flex;align-items:center;justify-content:center;min-height:2.75rem;
  background:var(--blue);color:#04070e;font:inherit;
  font-weight:700;padding:.6rem 1.2rem;border-radius:10px;text-decoration:none;margin-top:.4rem;
  border:0;cursor:pointer;line-height:1.2}
.gp-cta-lg{padding:.7rem 1.4rem;font-size:1rem}
.gp-cta.alt{background:transparent;color:var(--blue);border:1px solid var(--blue)}
.gp-map-open-link{display:inline-flex;margin-bottom:.7rem;font-size:.85rem;min-height:2.3rem;padding:.45rem 1rem}
.gp-forests{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.6rem;margin:.6rem 0 1.2rem}
/* Compact two-column row: name/terrain/species stack on the left, a single
   glanceable colour-coded percentage disc on the right — so scanning the
   whole list for "where's it worth going" doesn't require reading every
   line, the disc colour + number says it at a glance. */
/* min-width:0 overrides the grid item's default min-width:auto — without it,
   a grid track sizing itself off #content still respects this item's
   intrinsic content width (the nowrap name/species text), which silently
   blows the row past its column/viewport instead of letting the ellipsis
   truncation below actually engage. */
.gp-forest{background:var(--fc-bg);border:1px solid var(--fc-border);border-radius:12px;padding:.6rem .8rem;
  display:flex;align-items:center;justify-content:space-between;gap:.7rem;min-width:0}
.gp-forest-info{flex:1;min-width:0;display:flex;flex-direction:column;gap:.15rem}
.gp-forest-nm{font-weight:700;font-size:1.02rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gp-forest-sp{font-size:.8rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* Small per-species photo instead of a generic 🍄 in front of every name —
   same graceful onerror→emoji fallback as the bigger photo spots (baza-vrst
   cards, "Zakaj?" explain cards) for species without a photo yet. */
.gp-sp-ic{width:1.15rem;height:1.15rem;border-radius:50%;object-fit:cover;flex:0 0 auto;
  vertical-align:-.2rem;margin-right:.3rem;background:var(--badge-bg)}
.gp-forest-prot{opacity:.6}
.gp-terr{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.gp-forest-pct{flex:0 0 auto;min-width:3.5rem;border-radius:14px;padding:.4rem .5rem;display:flex;
  flex-direction:column;align-items:center;justify-content:center;box-shadow:0 2px 10px rgba(0,0,0,.25)}
.gp-forest-pct .n{font-size:.92rem;font-weight:800;line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap}
.gp-forest-pct .lvl{font-size:.48rem;font-weight:700;letter-spacing:.01em;line-height:1.1;margin-top:.15rem;
  text-align:center;text-transform:uppercase;opacity:.9}
/* Dynamic badge tiers — separate classes (not inline colour) so each growth
   level reads as light tinted background + a darker, same-hue text, matching
   the site's other tier badges (.e-ok etc.) instead of a solid disc. */
.gp-pct-hi{background:#d1fae5;color:#065f46}
.gp-pct-mid{background:#ffedd5;color:#7c2d12}
.gp-pct-low{background:#fed7aa;color:#7c2d12}
.gp-pct-none{background:#fee2e2;color:#7f1d1d}
/* ── Premium "today per forest" rows (render() in PAGE_JS) — richer than the
   free list: top-3 species (not 1), soil moisture, best-day-this-week and a
   7-day trend line, all from data the model already computes per location.
   Own grid (single column, not the free auto-fill card grid) since each row
   is now much taller. ── */
.gp-forests-premium{display:grid;grid-template-columns:1fr;gap:.6rem;margin:.6rem 0 1.2rem}
/* Column layout (overrides the base .gp-forest row-flex): header split
   (name/terrain left, big % badge right), then one full-width split row per
   species (photo+name left, warning+% right, both edge-anchored), then a
   bottom split row (soil/best-day left, trend spark right). padding-right
   leaves a permanent empty channel on the right so the floating SOS button
   (fixed near the top-right on mobile) never lands on top of a number —
   it only ever passes over blank card padding as the page scrolls. */
.gp-forest-premium{display:flex;flex-direction:column;justify-content:flex-start;
  align-items:stretch;gap:.7rem;padding-right:3.4rem;cursor:pointer;transition:border-color .15s,transform .15s}
.gp-forest-premium:hover,.gp-forest-premium:focus-visible{border-color:var(--blue);transform:translateY(-1px)}
.gp-forest-more{display:flex;align-items:center;gap:.3rem;font-size:.76rem;font-weight:600;
  color:var(--blue);margin-top:-.2rem}
.gp-forest-top{display:flex;align-items:flex-start;justify-content:space-between;gap:.7rem}
.gp-forest-namewrap{flex:1;min-width:0;display:flex;flex-direction:column;gap:.15rem}
.gp-forest-sp3{display:flex;flex-direction:column;gap:.65rem}
/* gp-fsp- (not gp-sp-) prefix on purpose — .gp-sp-row/.gp-sp-name are
   already used (with different rules) by the /baza-vrst/ species cards
   further down; reusing those names here silently lost this block to
   the later, unrelated cascade (that's why species names rendered bold —
   they were picking up the card title's font-weight:700 by accident). */
.gp-fsp-row{display:flex;align-items:center;justify-content:space-between;gap:.6rem}
.gp-fsp-left{display:flex;align-items:center;gap:.6rem;min-width:0;flex:1}
/* Squircle, not a circle — a round crop throws away too much of the photo;
   40-48px (2.75rem) keeps the mushroom recognisable. */
.gp-sp-avatar{width:2.75rem;height:2.75rem;border-radius:12px;object-fit:cover;
  flex:0 0 auto;background:var(--badge-bg)}
/* Plain weight and a touch smaller than .gp-forest-nm above it, so the area
   name reads as the row's heading and the species underneath it as detail. */
.gp-fsp-name{font-weight:400;font-size:.85rem;color:var(--text);line-height:1.3;overflow-wrap:break-word}
.gp-sp-right{flex:0 0 4.6rem;white-space:nowrap;font-size:.85rem;font-weight:700;
  color:var(--text);text-align:right}
.gp-sp-warn{cursor:help;margin-right:.1rem}
.gp-forest-bottom{display:flex;align-items:center;justify-content:space-between;gap:.6rem;flex-wrap:wrap}
.gp-forest-meta{display:flex;flex-wrap:wrap;gap:.15rem 1rem;font-size:.72rem;color:var(--muted)}
.gp-forest-spark{flex:0 0 auto;width:5.5rem}
.gp-forest-spark .gp-spark{width:100%;height:1.6rem}
.gp-lock{position:relative;border:1px dashed var(--card-border);border-radius:16px;
  padding:1.3rem;margin:.6rem 0 1rem;background:linear-gradient(180deg,rgba(77,159,248,.06),transparent)}
.gp-lock h3{margin:.1rem 0 .3rem}
.gp-skel{filter:blur(4px);opacity:.5;pointer-events:none;user-select:none;margin:.7rem 0;display:grid;gap:.5rem}
/* ── Pre-launch gate: everything below the header is blurred/disabled for
   anyone without a verified access token — the "coming soon" cover above it
   is the only interactive thing a non-subscriber sees. Lifted client-side
   (PAGE_JS) the moment /premium/verify succeeds, same trigger the existing
   paywall reveal already uses. ── */
.gp-cs-card{position:relative;border:1px solid var(--card-border);border-radius:16px;
  padding:1.4rem 1.5rem;margin:1rem 0 1.6rem;background:var(--card-bg);text-align:center}
.gp-cs-card h2{margin:.3rem 0 .5rem;font-size:1.35rem}
.gp-cs-card p{color:var(--muted);font-size:.92rem;line-height:1.6;max-width:36rem;margin:0 auto .9rem}
.gp-cs-card .gp-login{justify-content:center;max-width:24rem;margin:0 auto}
.gp-cs-blur{filter:blur(6px);opacity:.55;pointer-events:none;user-select:none}

/* ── Loading skeleton — shown to premium users the instant a token is
   found, while /premium/forecast is still in flight, so they never see
   the "Naroči se" upsell for content they already own. ── */
.gp-loadskel-group{display:grid;gap:.6rem;margin:.6rem 0}
.gp-loadskel{border-radius:12px;background:linear-gradient(90deg,var(--card-bg) 25%,
    rgba(255,255,255,.07) 37%,var(--card-bg) 63%);background-size:400% 100%;
  animation:gp-shimmer 1.4s ease infinite}
@keyframes gp-shimmer{0%{background-position:100% 50%}100%{background-position:0 50%}}
@media (prefers-reduced-motion:reduce){.gp-loadskel{animation:none;opacity:.7}}
.gp-skel .gp-forest{background:var(--badge-bg)}
.gp-lockbar{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-top:.8rem}
.gp-login{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.6rem}
.gp-login input{flex:1;min-width:180px;background:var(--badge-bg);border:1px solid var(--card-border);
  border-radius:9px;padding:.5rem .7rem;color:var(--text);font-size:.9rem}
.gp-login button{display:inline-flex;align-items:center;justify-content:center;min-height:2.75rem;
  background:var(--blue);color:#04070e;border:0;border-radius:9px;
  padding:.5rem 1rem;font-weight:700;cursor:pointer}
.gp-msg{font-size:.85rem;color:var(--muted);margin-top:.4rem;min-height:1.1em}
.gp-pricing{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.8rem;margin:.8rem 0}
.gp-plan{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:1.1rem;
  display:flex;flex-direction:column;gap:.5rem;box-shadow:var(--card-shadow)}
.gp-plan.best{border-color:var(--blue);box-shadow:0 0 0 1px var(--blue),var(--card-shadow)}
.gp-plan .p-price{font-size:1.9rem;font-weight:800}
.gp-plan .p-price small{font-size:.85rem;color:var(--muted);font-weight:600}
.gp-plan ul{margin:.2rem 0;padding-left:1.1rem;color:var(--muted);font-size:.88rem;line-height:1.7}
.gp-tag{display:inline-block;font-size:.7rem;font-weight:700;color:var(--blue);
  border:1px solid var(--blue);border-radius:6px;padding:.05rem .4rem;align-self:flex-start}
.gp-badge{display:inline-block;font-size:.72rem;font-weight:700;padding:.08rem .45rem;border-radius:6px;white-space:nowrap}
.e-ok{background:rgba(52,211,153,.15);color:var(--green)}
.e-cond{background:rgba(245,158,11,.15);color:var(--amber)}
.e-none{background:var(--badge-bg);color:var(--muted)}
.e-tox,.e-tox2{background:rgba(248,113,113,.16);color:#f87171}
.e-death{background:rgba(248,113,113,.28);color:#fecaca;font-weight:800}
.e-prot{background:rgba(167,139,250,.18);color:var(--purple)}
.gp-sptable{width:100%;border-collapse:collapse;font-size:.86rem}
.gp-sptable th,.gp-sptable td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--border);vertical-align:top}
.gp-sptable th{color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--bg)}
.gp-sptable tbody tr:nth-child(odd){background:rgba(255,255,255,.02)}
.gp-sptable tbody tr:hover{background:rgba(77,159,248,.06)}
.gp-sptable .lat{color:var(--muted);font-style:italic;font-size:.8rem}
.gp-scroll{max-height:560px;overflow:auto;border:1px solid var(--card-border);border-radius:12px}
.gp-dbl{color:var(--muted);font-size:.8rem}

/* ── Species cards (/baza-vrst/) — Material-style: photo (or tinted
   placeholder until one exists) on top, clean metrics below. ── */
.gp-sp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.85rem;margin:.6rem 0 1rem}
.gp-sp-card{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;overflow:hidden;
  box-shadow:var(--card-shadow);display:flex;flex-direction:column}
.gp-sp-top{position:relative;height:108px;display:flex;align-items:center;justify-content:center;
  background:rgba(255,255,255,.03)}
.gp-sp-top img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.gp-sp-top .gp-sp-emoji{display:none;font-size:2.1rem;opacity:.55}
.gp-sp-top.ph .gp-sp-emoji{display:block}
.gp-sp-top.ph.e-ok{background:linear-gradient(135deg,rgba(52,211,153,.32),rgba(52,211,153,.06))}
.gp-sp-top.ph.e-cond{background:linear-gradient(135deg,rgba(245,158,11,.32),rgba(245,158,11,.06))}
.gp-sp-top.ph.e-none{background:linear-gradient(135deg,rgba(169,160,140,.28),rgba(169,160,140,.05))}
.gp-sp-top.ph.e-tox,.gp-sp-top.ph.e-tox2{background:linear-gradient(135deg,rgba(248,113,113,.32),rgba(248,113,113,.06))}
.gp-sp-top.ph.e-death{background:linear-gradient(135deg,rgba(248,113,113,.45),rgba(248,113,113,.1))}
.gp-sp-top.ph.e-prot{background:linear-gradient(135deg,rgba(167,139,250,.32),rgba(167,139,250,.06))}
.gp-sp-body{padding:.7rem .8rem .8rem;display:flex;flex-direction:column;gap:.25rem;flex:1}
.gp-sp-name{font-weight:700;font-size:.95rem;line-height:1.25}
.gp-sp-lat{font-style:italic;color:var(--muted);font-size:.78rem;margin-bottom:.15rem}
.gp-sp-row{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-top:.1rem}
.gp-sp-season{font-size:.76rem;color:var(--muted);white-space:nowrap}
.gp-sp-dbl{font-size:.76rem;color:var(--muted);margin-top:.4rem;padding-top:.4rem;
  border-top:1px dashed var(--card-border);line-height:1.4}
.gp-sp-dbl b{color:var(--text)}
.gp-sp-unver{font-size:.7rem;color:var(--muted);opacity:.85;margin-top:.15rem;letter-spacing:.01em}
/* Orodna vrstica baze vrst: iskanje + filtri po užitnosti in sezoni. Kartic je
   300, zato se jih naenkrat izriše le prvih nekaj (glej SP_JS) — brez JS
   ostanejo vidne vse, da se pajku in obiskovalcu brez skript ne skrije nič. */
/* Odmik je višina fiksne .gp-topbar (48 px) — brez njega iskalno polje ob
   drsenju zleze podnjo in ostanejo vidni samo filtri. */
.gp-sp-tools{position:sticky;top:48px;z-index:5;padding:.6rem 0 .5rem;background:var(--bg);
  backdrop-filter:blur(6px);margin-bottom:.2rem}
.gp-sp-search{width:100%;box-sizing:border-box;padding:.6rem .8rem;border-radius:10px;
  border:1px solid var(--card-border);background:var(--card-bg);color:var(--text);font-size:.9rem}
.gp-sp-search::placeholder{color:var(--muted)}
.gp-sp-chips{display:flex;gap:.4rem;overflow-x:auto;padding:.55rem .1rem .1rem;scrollbar-width:none}
.gp-sp-chips::-webkit-scrollbar{display:none}
.gp-sp-chip{flex:0 0 auto;padding:.34rem .7rem;border-radius:999px;cursor:pointer;
  border:1px solid var(--card-border);background:var(--card-bg);color:var(--muted);
  font-size:.76rem;font-family:inherit;white-space:nowrap;text-decoration:none}
.gp-sp-chip.on{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:600}
.gp-sp-count{font-size:.75rem;color:var(--muted);margin:.4rem .1rem 0}
.gp-sp-card[hidden]{display:none}
.gp-sp-more{display:flex;justify-content:center;margin:.9rem 0 .3rem}
.gp-sp-more button{padding:.55rem 1.1rem;border-radius:10px;cursor:pointer;font-family:inherit;
  font-size:.85rem;border:1px solid var(--card-border);background:var(--card-bg);color:var(--text)}
.gp-sp-more button[hidden]{display:none}
.gp-terrmap{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.7rem;margin:.6rem 0}
.gp-terrmap .t{background:var(--card-bg);border:1px solid var(--card-border);border-left-width:4px;
  border-radius:10px;padding:.85rem 1rem;box-shadow:var(--card-shadow)}
.gp-terrmap .t-h{display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem}
.gp-terrmap .t-ic{display:inline-flex;align-items:center;justify-content:center;width:1.9rem;height:1.9rem;
  border-radius:8px;font-size:1.05rem}
.gp-terrmap .t b{color:var(--text);font-size:1rem}
.gp-matrix{width:100%;border-collapse:collapse;font-size:.8rem}
.gp-matrix th,.gp-matrix td{padding:.3rem .35rem;text-align:center;border-bottom:1px solid var(--border)}
.gp-matrix td.nm{text-align:left;white-space:nowrap}
.gp-cell{display:inline-block;min-width:2.3em;border-radius:6px;padding:.15rem .3rem;
  font-variant-numeric:tabular-nums;font-weight:700;text-align:center}
.gp-legend{display:flex;flex-wrap:wrap;gap:.9rem;font-size:.78rem;color:var(--muted);margin:.5rem 0 .9rem}
.gp-legend span{display:inline-flex;align-items:center;gap:.35rem}
.gp-legend i{width:.8rem;height:.8rem;border-radius:3px;display:inline-block}

/* Sub-headings in the JS-rendered premium block (#gp-content) are bare <h3>
   with no built-in spacing, so they sit flush against whatever scrolled
   above them. Force room. */
#gp-content h3{margin:1.7rem 0 .6rem;font-size:1.05rem}
#gp-content h3:first-child{margin-top:.4rem}
.gp-explain-h{margin-top:1.6rem}
.gp-explain-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.7rem;margin-top:.7rem}
.gp-explain-card{display:flex;gap:.7rem;align-items:flex-start;background:var(--card-bg);
  border:1px solid var(--card-border);border-radius:12px;padding:.7rem .8rem;box-shadow:var(--card-shadow)}
.gp-explain-photo{width:52px;height:52px;border-radius:50%;overflow:hidden;flex:0 0 auto;
  background:rgba(255,255,255,.05);display:flex;align-items:center;justify-content:center;font-size:1.3rem}
.gp-explain-photo img{width:100%;height:100%;object-fit:cover}
.gp-explain-body{flex:1;min-width:0}
.gp-explain-name{font-weight:700;font-size:.88rem;line-height:1.25}
.gp-explain-idx{font-weight:800;font-size:.82rem;margin-top:.1rem;font-variant-numeric:tabular-nums}
.gp-explain-more{margin-top:.35rem}
.gp-explain-more summary{font-size:.74rem;color:var(--blue);cursor:pointer;list-style:none}
.gp-explain-more summary::-webkit-details-marker{display:none}
.gp-explain-more summary::before{content:"Zakaj? ▾"}
.gp-explain-more[open] summary::before{content:"Skrij ▴"}
.gp-explain-more p{font-size:.78rem;color:var(--muted);margin:.4rem 0 0;line-height:1.55}
.gp-explain-more .dbl{display:block;margin-top:.3rem;color:var(--muted)}
/* Ekološka skupina + rastni zamik vrste — pove, katero okno dežja "Sprožilni
   dež" spodaj sploh meri (pri kukmaku drugo kot pri jurčku). */
.gp-eco{display:inline-block;margin-top:.45rem;padding:.12rem .45rem;border-radius:999px;
  background:rgba(255,255,255,.07);border:1px solid var(--card-border);
  font-size:.68rem;color:var(--muted);white-space:nowrap;max-width:100%;overflow:hidden;text-overflow:ellipsis}
/* Per-factor "why" breakdown — the model already scores each species on 6
   independent 0-100 signals (soil temp, trigger/base rain, soil moisture, air
   humidity, night-cooling trigger) and blends them into the single index;
   previously only the blended number + a prose summary were ever shown.
   Surfacing the actual bars is the real "not a black box" version of the
   same "Zakaj?" disclosure, not a new claim. */
.gp-factors{display:flex;flex-direction:column;gap:.3rem;margin-top:.55rem}
.gp-factor-row{display:flex;align-items:center;gap:.5rem}
.gp-factor-lbl{flex:0 0 6.4rem;font-size:.7rem;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gp-factor-bar{flex:1;height:6px;background:rgba(255,255,255,.08);border-radius:3px;overflow:hidden}
.gp-factor-fill{height:100%;border-radius:3px}
.gp-factor-val{flex:0 0 2.6rem;text-align:right;font-size:.7rem;color:var(--muted);
  font-variant-numeric:tabular-nums;white-space:nowrap}
.gp-disc{font-size:.82rem;color:var(--muted);border-left:3px solid var(--amber);padding:.3rem .8rem;margin:1rem 0}

/* ── Soil-moisture gauge + 7-day mini graphs (premium forecast, per gozd) ── */
.gp-soil-card{display:flex;gap:1rem;align-items:center;background:var(--card-bg);
  border:1px solid var(--card-border);border-radius:12px;padding:.8rem .9rem;margin-top:.8rem;
  box-shadow:var(--card-shadow);flex-wrap:wrap}
.gp-soil-gauge{position:relative;width:56px;height:56px;flex:0 0 auto}
.gp-soil-ring{display:block;width:100%;height:100%}
.gp-soil-ring-bg{fill:none;stroke:rgba(255,255,255,.10);stroke-width:6}
.gp-soil-ring-fg{fill:none;stroke:#5c8374;stroke-width:6;stroke-linecap:round;
  transform:rotate(-90deg);transform-origin:28px 28px}
.gp-soil-num{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:.82rem;font-weight:800;color:var(--text)}
.gp-soil-body{flex:1;min-width:200px}
.gp-soil-label{font-size:.85rem;font-weight:700}
.gp-soil-label small{font-weight:500;color:var(--muted)}
.gp-soil-trends{display:flex;flex-wrap:wrap;gap:1rem;margin-top:.5rem}
.gp-soil-trend{display:flex;flex-direction:column;gap:.2rem}
.gp-soil-trend-lbl{font-size:.7rem;color:var(--muted)}
.gp-spark{display:block;width:140px;height:32px}
.gp-spark-empty{font-size:.75rem;color:var(--muted)}

/* ── SOS floating action button ── */
.gp-sos-fab{position:fixed;right:1.1rem;bottom:1.1rem;z-index:60;width:3.1rem;height:3.1rem;border-radius:50%;
  background:#dc2626;color:#fff;border:2px solid rgba(255,255,255,.25);font-size:1.4rem;cursor:pointer;
  box-shadow:0 4px 18px rgba(220,38,38,.45);display:flex;align-items:center;justify-content:center;line-height:1}
.gp-sos-fab:hover{background:#b91c1c}
.gp-sos-panel{position:fixed;right:1.1rem;bottom:4.6rem;z-index:60;width:min(300px,calc(100vw - 2.2rem));
  background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:1rem;
  box-shadow:var(--card-shadow);display:none}
.gp-sos-panel.open{display:block}
.gp-sos-panel h4{margin:0 0 .5rem;font-size:.95rem}
.gp-sos-panel p{font-size:.8rem;color:var(--muted);margin:0 0 .7rem;line-height:1.5}
.gp-sos-call{display:flex;align-items:center;gap:.6rem;background:rgba(220,38,38,.12);border:1px solid rgba(220,38,38,.35);
  border-radius:10px;padding:.55rem .8rem;text-decoration:none;color:var(--text);font-weight:700;margin-bottom:.5rem}
.gp-sos-call small{display:block;font-weight:500;color:var(--muted);font-size:.72rem}
.gp-sos-call.alt{background:var(--badge-bg);border-color:var(--card-border)}

/* ── Dvojnik: edible-vs-double comparison cards ── */
.gp-vs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.8rem;margin:.7rem 0 1rem;clear:both}
.gp-vs-card{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:.9rem;
  box-shadow:var(--card-shadow)}
.gp-vs-pair{display:flex;align-items:center;gap:.5rem}
.gp-vs-side{flex:1;min-width:0;text-align:center}
.gp-vs-photo{width:100%;aspect-ratio:1/1;border-radius:10px;background:var(--badge-bg);
  display:flex;align-items:center;justify-content:center;font-size:1.8rem;overflow:hidden;margin-bottom:.35rem}
.gp-vs-photo img{width:100%;height:100%;object-fit:cover}
.gp-vs-name{font-size:.82rem;font-weight:700;line-height:1.25}
.gp-vs-lat{font-size:.68rem;color:var(--muted);font-style:italic}
.gp-vs-x{flex:0 0 auto;font-weight:800;color:var(--muted);font-size:.8rem;padding:0 .2rem}
.gp-vs-diff{margin:.6rem 0 0;padding-left:1.1rem;font-size:.8rem;color:var(--muted);line-height:1.55}
.gp-vs-note{background:var(--fc-bg);border:1px solid var(--fc-border);border-radius:10px;padding:.6rem .8rem;
  font-size:.83rem;color:var(--muted);margin-bottom:.5rem}
.gp-vs-note b{color:var(--text)}

/* ── AI prepoznava — photo-banner card so this flagship feature actually
   stands out instead of blending into the same plain box as every other
   form on the page. Purple/violet reads as "smart/AI" against the site's
   green-and-ochre forest palette without fighting it. ── */
.gp-ai-card{border-radius:16px;overflow:hidden;border:1px solid var(--card-border);
  margin:.6rem 0 1rem;box-shadow:var(--card-shadow);background:var(--card-bg)}
.gp-ai-banner{position:relative;height:104px;display:flex;align-items:center;gap:.7rem;
  padding:0 1.1rem;background:linear-gradient(120deg,rgba(109,40,217,.6),rgba(30,16,56,.88)),
    url('/gobarska-napoved/img/vrste/boletus_edulis.jpg') center 35%/cover}
.gp-ai-badge{position:absolute;top:.65rem;right:.85rem;background:rgba(255,255,255,.16);
  backdrop-filter:blur(6px);border:1px solid rgba(255,255,255,.3);color:#fff;font-size:.68rem;
  font-weight:800;letter-spacing:.04em;padding:.22rem .55rem;border-radius:999px}
.gp-ai-icon{position:relative;font-size:2.5rem;line-height:1;filter:drop-shadow(0 4px 10px rgba(0,0,0,.45))}
.gp-ai-icon-mush{position:absolute;right:-.55rem;bottom:-.25rem;font-size:1.2rem}
.gp-ai-banner-title{color:#fff;font-weight:800;font-size:1.15rem;text-shadow:0 2px 8px rgba(0,0,0,.4)}
.gp-ai-body{padding:1rem 1.1rem}
@media (prefers-reduced-motion:no-preference){
  .gp-ai-icon{animation:gp-ai-pulse 2.6s ease-in-out infinite}
}
@keyframes gp-ai-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.08)}}

/* ── Gobarjev dnevnik (local-only GPS+photo log) ── */
.gp-diary{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;
  padding:1rem 1.1rem;margin:.6rem 0 1rem;box-shadow:var(--card-shadow)}
.gp-diary-priv{font-size:.78rem;color:var(--muted);margin-bottom:.7rem}
.gp-diary-row{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.55rem;align-items:center}
.gp-diary-row input[type=date],.gp-diary-row input[type=text],.gp-diary textarea{
  background:var(--badge-bg);border:1px solid var(--card-border);border-radius:9px;
  padding:.5rem .7rem;color:var(--text);font-size:.88rem;font-family:inherit}
.gp-diary-row input[type=text]{flex:1;min-width:160px}
.gp-diary textarea{width:100%;min-height:4.5rem;resize:vertical;box-sizing:border-box}
.gp-diary-btn{display:inline-flex;align-items:center;min-height:2.75rem;background:var(--badge-bg);
  border:1px solid var(--card-border);color:var(--text);
  border-radius:9px;padding:.5rem .8rem;font-size:.85rem;font-weight:600;cursor:pointer}
.gp-diary-photobtn{display:inline-block}

/* ── Filter chips (Material 3 pattern) — swap the old <select> for a
   horizontally-scrollable pill row so switching locations feels like a
   native app control, not a form field. ── */
.gp-chip-row{display:flex;gap:.5rem;overflow-x:auto;padding:.15rem .05rem .6rem;margin:.5rem 0 .3rem;
  scrollbar-width:none}
.gp-chip-row::-webkit-scrollbar{display:none}
.gp-chip{flex:0 0 auto;display:flex;align-items:center;gap:.4rem;background:var(--badge-bg);
  border:1.5px solid var(--card-border);color:var(--text);border-radius:999px;padding:.5rem .9rem;
  font-size:.85rem;font-weight:600;font-family:inherit;cursor:pointer;white-space:nowrap;
  min-height:2.75rem;transition:border-color .15s ease,background .15s ease}
.gp-chip:hover{border-color:var(--blue)}
.gp-chip.active{background:rgba(111,174,85,.16);border-color:var(--blue);color:var(--blue)}
.gp-chip-pct{font-variant-numeric:tabular-nums;opacity:.85}
/* ── /koledar/ — month chips + one card panel each (chip-click swap, no
   fetch — all 12 panels are pre-rendered, only visibility toggles). ── */
.gp-cal-panel{display:none;background:var(--card-bg);border:1px solid var(--card-border);
  border-radius:14px;padding:1rem 1.1rem;box-shadow:var(--card-shadow)}
.gp-cal-panel.active{display:block}
.gp-cal-sp{display:flex;flex-wrap:wrap;gap:.5rem}
.gp-cal-tag{background:var(--badge-bg);border:1px solid var(--card-border);border-radius:999px;
  padding:.35rem .8rem;font-size:.85rem}
.gp-cal-empty{color:var(--muted);font-size:.88rem;margin:0}
.gp-d-photo-preview{width:2.6rem;height:2.6rem;border-radius:8px;object-fit:cover;display:none;vertical-align:middle}
.gp-diary-submit{margin-top:.2rem}
.gp-diary-list{display:grid;gap:.6rem;margin-top:1rem}
.gp-diary-entry{display:flex;gap:.7rem;background:var(--fc-bg);border:1px solid var(--fc-border);
  border-radius:10px;padding:.6rem .7rem}
.gp-diary-thumb{width:3.6rem;height:3.6rem;border-radius:8px;object-fit:cover;flex:0 0 auto;background:var(--badge-bg)}
.gp-diary-thumb-ph{width:3.6rem;height:3.6rem;border-radius:8px;flex:0 0 auto;background:var(--badge-bg);
  display:flex;align-items:center;justify-content:center;font-size:1.4rem}
.gp-diary-body{flex:1;min-width:0}
.gp-diary-sp{font-weight:700;font-size:.9rem}
.gp-diary-meta{font-size:.76rem;color:var(--muted)}
.gp-diary-meta a{color:var(--cyan)}
.gp-diary-notes{font-size:.82rem;color:var(--muted);margin-top:.2rem}
.gp-diary-del{flex:0 0 auto;background:none;border:0;color:var(--muted);cursor:pointer;font-size:1rem;padding:.2rem}
.gp-diary-empty{color:var(--muted);font-size:.85rem;text-align:center;padding:.8rem}

/* ── Moji alarmi (per-user custom push/email trigger rules) ── */
.gp-alert-card{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;
  padding:1rem 1.1rem;margin:.6rem 0 1rem;box-shadow:var(--card-shadow)}
.gp-alert-rows{display:flex;flex-direction:column;gap:.6rem;margin-bottom:.7rem}
.gp-alert-row{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center;background:var(--fc-bg);
  border:1px solid var(--fc-border);border-radius:10px;padding:.55rem .6rem}
.gp-alert-row select,.gp-alert-row input{background:var(--badge-bg);border:1px solid var(--card-border);
  border-radius:9px;padding:.45rem .6rem;color:var(--text);font-size:.83rem;font-family:inherit}
.gp-alert-row select.gp-alert-sp{flex:1 1 160px;min-width:140px}
.gp-alert-row select.gp-alert-loc{flex:1 1 140px;min-width:130px}
.gp-alert-elev{width:6.5rem}
.gp-alert-thr{display:flex;align-items:center;gap:.3rem}
.gp-alert-thr input{width:4rem}
.gp-alert-thr span{font-size:.8rem;color:var(--muted)}
.gp-alert-del{flex:0 0 auto;background:none;border:0;color:var(--muted);cursor:pointer;font-size:1rem;
  padding:.3rem;margin-left:auto}
.gp-alert-actions{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center}

/* ── AI prepoznava gobe (identify) ── */
.gp-id-card{background:var(--fc-bg);border:1px solid var(--fc-border);border-radius:12px;
  padding:.8rem .9rem;margin-top:.7rem}
.gp-id-head{display:flex;align-items:center;justify-content:space-between;gap:.6rem;flex-wrap:wrap}
.gp-id-name{font-weight:700;font-size:.98rem}
.gp-id-lat{font-size:.78rem;color:var(--muted);font-style:italic;margin-left:.3rem}
.gp-id-conf{font-size:.7rem;font-weight:700;padding:.08rem .45rem;border-radius:6px;white-space:nowrap}
.gp-id-conf.hi{background:rgba(52,211,153,.15);color:var(--green)}
.gp-id-conf.mid{background:rgba(245,158,11,.15);color:var(--amber)}
.gp-id-conf.lo{background:rgba(248,113,113,.16);color:#f87171}
.gp-id-reason{font-size:.85rem;color:var(--muted);margin-top:.4rem;line-height:1.55}
.gp-id-warn{font-size:.83rem;color:#fecaca;background:rgba(248,113,113,.12);border-left:3px solid #f87171;
  padding:.4rem .7rem;margin-top:.5rem;border-radius:0 8px 8px 0}
.gp-id-note{font-size:.82rem;color:var(--muted);border-left:3px solid var(--amber);padding:.3rem .8rem;margin-top:.8rem}

/* ── Sezonski trend (pretekla leta) ── */
.gp-trend-wrap{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;
  padding:1rem 1.1rem 1.2rem;margin:.6rem 0 1rem;box-shadow:var(--card-shadow)}
.gp-trend-svg{width:100%;height:auto;display:block}
.gp-trend-legend{display:flex;flex-wrap:wrap;gap:.5rem 1rem;margin-top:.6rem;font-size:.8rem;color:var(--muted)}
.gp-trend-legend span{display:inline-flex;align-items:center;gap:.35rem}
.gp-trend-legend i{width:1.1rem;height:3px;border-radius:2px;display:inline-block}
.gp-trend-best{font-size:.85rem;color:var(--muted);margin-top:.7rem;border-top:1px solid var(--border);padding-top:.6rem}
.gp-trend-best b{color:var(--text)}

/* ── Zložljive (details) sekcije ── */
.gp-collapse{border:1px solid var(--card-border);border-radius:14px;margin:.6rem 0 1rem;overflow:hidden}
.gp-collapse summary{cursor:pointer;list-style:none;padding:.8rem 1rem;font-weight:700;
  display:flex;align-items:center;justify-content:space-between;background:var(--card-bg)}
.gp-collapse summary::-webkit-details-marker{display:none}
.gp-collapse summary::after{content:"▾";color:var(--muted);transition:transform .2s ease;margin-left:.6rem}
.gp-collapse[open] summary::after{transform:rotate(180deg)}
.gp-collapse summary small{font-weight:500;color:var(--muted);margin-left:.5rem}
.gp-collapse > :not(summary){padding:0 1rem 1rem}
.gp-collapse[open] > :not(summary){padding-top:.3rem}
/* FAQ <details> otherwise rely on bare UA defaults — too short a tap target
   on mobile. Padding (not margin) grows the hit area without widening the
   row's footprint or spacing against its neighbours. */
.faq details{border-bottom:1px solid var(--border)}
.faq details:last-child{border-bottom:0}
.faq summary{cursor:pointer;min-height:2.75rem;display:flex;align-items:center;
  padding:.7rem .2rem;font-weight:600}
.faq p{margin:0 .2rem .8rem;color:var(--muted);font-size:.9rem;line-height:1.6}

/* ── Pregled zmožnosti — kartice takoj pod junaško kartico ──
   Stran ima veliko: gozdove, premium napoved, AI prepoznavo, zemljevid, bazo
   vrst, dvojnice, koledar, trend, dnevnik. Kdor pride prvič, tega ne vidi —
   razdelki so razmetani čez vso dolžino, deloma za drsnimi vrsticami in
   zloženimi <details>. Ta mreža jih pokaže naenkrat, brez drsenja.

   Vsaka kartica ima svojo ikono (dvobarvni SVG, glej _FI_*) in svoj poudarek
   (--fa), da se mreža bere kot devet različnih stvari in ne kot devet enakih
   pravokotnikov. Ikone so risane, ne emoji: ti se med platformami razlikujejo
   in se ne dajo prebarvati (isti razlog kot pri spodnji navigaciji).

   Mreža je nadomestila prejšnji hub s fotografijami, ki je stal pod cenikom —
   isti cilji, le da so zdaj na vrhu in jih je devet namesto petih. */
.gp-feat{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:.7rem;margin:.5rem 0 1.3rem}
.gp-feat-group{margin-bottom:.3rem}
.gp-feat-group-title{font-size:.92rem;font-weight:700;color:var(--muted);margin:1.1rem 0 .1rem}
.gp-feat-more{font-size:.85rem;color:var(--muted);margin:.2rem 0 1.3rem}
.gp-feat-more a{color:var(--muted)}
.gp-feat-card{position:relative;display:flex;flex-direction:column;gap:.4rem;
  padding:.95rem 1rem 1.05rem;border-radius:14px;overflow:hidden;
  background:var(--card-bg);border:1px solid var(--card-border);box-shadow:var(--card-shadow);
  text-decoration:none;color:var(--text);
  transition:border-color .15s ease,transform .15s ease}
.gp-feat-card::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--fa)}
.gp-feat-card::after{content:"";position:absolute;top:-45%;right:-30%;width:70%;height:130%;
  border-radius:50%;background:var(--fa);opacity:0;filter:blur(30px);
  transition:opacity .2s ease;pointer-events:none}
.gp-feat-card:hover{border-color:var(--fa);transform:translateY(-2px)}
.gp-feat-card:hover::after{opacity:.18}
.gp-feat-card:focus-visible{outline:2px solid var(--fa);outline-offset:2px}
.gp-feat-ic{display:inline-flex;align-items:center;justify-content:center;width:2.5rem;height:2.5rem;
  flex:0 0 auto;border-radius:12px;background:var(--fa-soft);color:var(--fa)}
.gp-feat-ic svg{width:1.55rem;height:1.55rem;display:block}
.gp-feat-title{font-weight:700;font-size:1rem;line-height:1.3}
.gp-feat-sub{font-size:.8rem;color:var(--muted);line-height:1.45}
/* Oznaka za plačljivi del — ista beseda kot na ceniku, da je razlika med
   brezplačnim in premium delom vidna že tu, ne šele ob kliku. */
.gp-feat-badge{position:absolute;top:.7rem;right:.75rem;font-size:.6rem;font-weight:700;
  letter-spacing:.06em;padding:.16rem .45rem;border-radius:999px;
  background:var(--fa-soft);color:var(--fa)}

/* Zadnja vsebina naj se ne skrije za plavajočim SOS gumbom (spodaj desno).
   body .wrap (not .wrap) so this reliably beats blog.css's own unconditional
   .wrap{padding:2rem 0 4rem}, which loads after this inline stylesheet and
   would otherwise win the tie on source order alone. Declared here, right
   before the mobile media query below, so the narrower 9.7rem/3.5rem
   mobile override (same specificity) still wins on small screens — a rule
   after this one in source order would otherwise beat it regardless of
   which media query is narrower. */
body .wrap{padding-bottom:5.5rem}

/* ── Bottom nav (mobile, app-style) — hidden on desktop, where the
   mreža .gp-feat already covers cross-page navigation ── */
.gp-bottomnav{display:none}
/* ── Top App Bar (mobile, Material 3 "small top app bar") — a NEW element
   scoped to this page only, not a rework of the shared .site-head used by
   every other generated page. It tells a user mid-scroll which of the
   gobarska-napoved/ pages they're on
   and has a 1-tap way back, without us touching the site-wide header. ── */
.gp-topbar{display:none}
@media (max-width:760px){
  /* body .wrap (not .wrap) — blog.css's own unconditional .wrap{padding:2rem 0 4rem}
     loads after this inline stylesheet and would otherwise win the tie on
     source order alone; the extra ancestor selector outranks it regardless
     of load order without touching blog.css.
     Bottom compensation = the nav's own height (--gp-bnh) + the device's
     safe-area inset, so content can always be scrolled clear of the fixed
     bar regardless of how tall that inset actually is on a given phone. */
  body .wrap{padding-bottom:calc(var(--gp-bnh) + env(safe-area-inset-bottom) + 1rem);padding-top:3.5rem}
  .gp-topbar{display:flex;position:fixed;left:0;right:0;top:0;z-index:55;height:3rem;
    align-items:center;gap:.5rem;padding:0 .5rem;background:var(--card-bg);
    backdrop-filter:blur(10px);border-bottom:1px solid var(--card-border)}
  .gp-topbar-back{flex:0 0 auto;width:2.2rem;height:2.2rem;display:flex;align-items:center;
    justify-content:center;font-size:1.4rem;color:var(--text);text-decoration:none;border-radius:50%}
  .gp-topbar-back:active{background:var(--badge-bg)}
  .gp-topbar-brand{font-size:1.2rem}
  .gp-topbar-title{flex:1;font-weight:700;font-size:.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .gp-topbar-action{flex:0 0 auto;width:2.2rem;height:2.2rem;display:flex;align-items:center;
    justify-content:center;font-size:1.1rem;text-decoration:none;border-radius:50%;background:var(--badge-bg)}
  /* z-index:70 — the highest layer on the page (topbar 55, SOS FAB/panel 60)
     so the bottom nav always stays on top of everything else, never gets
     covered by other fixed/sticky elements. */
  .gp-bottomnav{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:70;
    background:var(--card-bg);backdrop-filter:blur(10px);border-top:1px solid var(--card-border);
    padding:.35rem .2rem calc(.35rem + env(safe-area-inset-bottom))}
  .gp-bottomnav a{flex:1;min-height:2.75rem;display:flex;flex-direction:column;align-items:center;
    justify-content:center;gap:.15rem;
    padding:.3rem .2rem;color:var(--muted);text-decoration:none;font-size:.66rem;line-height:1.2;
    border-radius:10px}
  .gp-bottomnav a .ic{font-size:1.25rem;line-height:1}
  /* Custom two-tone SVG icons (see BOTTOM_NAV): stroke="currentColor" so the
     line art itself picks up the active/inactive tab colour exactly like the
     text label already did, plus a fixed var(--cyan) accent fill for the
     "duotone" half — one consistent two-colour look across the whole set. */
  .gp-bottomnav a .ic svg{width:1.35rem;height:1.35rem;display:block}
  .gp-bottomnav a.active{color:var(--blue)}
  .gp-bottomnav a.active .ic{transform:translateY(-1px)}
  /* Center "Prepoznaj" (AI) item rides above the bar as a raised, badged
     button — the same visual language camera/scan actions use in bottom
     navs, so the flagship AI feature reads as a primary action, not just
     another tab. */
  .gp-bottomnav a.hl{color:var(--text);font-weight:700}
  .gp-bottomnav a.hl .ic{width:2.5rem;height:2.5rem;border-radius:50%;
    background:linear-gradient(135deg,#a78bfa,#6d28d9);display:flex;align-items:center;
    justify-content:center;font-size:1.15rem;margin-top:-1.15rem;
    box-shadow:0 3px 12px rgba(109,40,217,.55);border:3px solid var(--bg)}
  .gp-bottomnav a.hl .ic svg{width:1.45rem;height:1.45rem}
  .gp-bottomnav a.hl.active .ic{transform:none}
  /* Bottom-right is now owned by the bottom nav; move SOS out of the hero's
     way rather than shrink its tap target to squeeze both in. Shifted a
     further 3.5rem down from its old top:5.7rem to clear the new top bar. */
  .gp-sos-fab{top:9.2rem;bottom:auto;right:.8rem;width:2.75rem;height:2.75rem;font-size:1.15rem}
  .gp-sos-panel{top:12.3rem;bottom:auto;right:.8rem}
  /* The free forest list is single-column here too (see the 560px rule
     below), so its % badge sits in that same right-hand strip the fixed
     SOS button occupies while scrolling past — same channel the premium
     rows already reserve, just scoped to mobile since the free list's
     multi-column desktop grid shouldn't lose width to a badge SOS never
     overlaps there. */
  .gp-forest{padding-right:3.4rem}
}

/* ── Interaktivni zemljevid (Leaflet, lazy-load ob kliku) ── */
.gp-map-shell{position:relative;margin:.6rem 0 1rem}
.gp-map{height:min(64vh,480px);border-radius:14px;overflow:hidden;border:1px solid var(--card-border);
  background:var(--card-bg)}
.gp-map-hint{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:.5rem;text-align:center;cursor:pointer;border-radius:14px;
  background:linear-gradient(180deg,rgba(19,15,11,.6),rgba(6,10,6,.85))}
.gp-map-hint b{font-size:1.05rem}
.gp-map-hint span{font-size:.85rem;color:var(--muted)}
.gp-map-load{background:var(--blue);color:#04070e;font-weight:700;padding:.5rem 1.1rem;border-radius:10px}
.gp-map-legend{display:flex;flex-wrap:wrap;gap:.5rem .9rem;margin:.5rem 0;font-size:.78rem;color:var(--muted);clear:both}
.gp-map-legend span{display:inline-flex;align-items:center;gap:.35rem}
.gp-map-legend i{width:.85rem;height:.85rem;border-radius:50%;display:inline-block;border:1px solid rgba(255,255,255,.4)}
.gp-species-legend-title{flex-basis:100%}
.gp-map-attr{font-size:.72rem;color:var(--muted);margin-top:.2rem}
.gp-map-attr a{color:var(--muted)}
.gp-mini-map{margin:1.4rem 0}
.gp-mini-map-grid{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0 .9rem}
.gp-mmap-chip{display:inline-flex;align-items:center;gap:.4rem;padding:.4rem .65rem;border-radius:10px;
  background:var(--card-bg);border:1px solid var(--card-border);font-size:.82rem;color:var(--text);
  text-decoration:none}
.gp-mmap-chip i{width:.7rem;height:.7rem;border-radius:50%;flex:0 0 auto}
.gp-mmap-chip .nm{font-weight:600}
.gp-mmap-chip .pct{color:var(--muted);font-size:.76rem;font-variant-numeric:tabular-nums}
.gp-mmap-chip.prot{opacity:.75}
.gp-photo-card{float:right;width:260px;margin:.1rem 0 .9rem 1.2rem;border-radius:14px;overflow:hidden;
  border:1px solid var(--card-border);box-shadow:var(--card-shadow)}
.gp-photo-card img{display:block;width:100%;height:auto}
.gp-photo-card figcaption{padding:.5rem .7rem;font-size:.72rem;color:var(--muted);background:var(--card-bg)}
@media (max-width:760px){.gp-photo-card{float:none;width:100%;margin:0 0 1rem}}
.gp-banner{position:relative;border-radius:16px;overflow:hidden;margin:.6rem 0 1.2rem;
  border:1px solid var(--card-border);box-shadow:var(--card-shadow)}
.gp-banner img{display:block;width:100%;height:min(34vw,280px);object-fit:cover}
.gp-banner figcaption{position:absolute;left:0;right:0;bottom:0;padding:.5rem .9rem;font-size:.74rem;
  color:#e9e9e9;background:linear-gradient(0deg,rgba(6,10,6,.75),transparent)}
.gp-map-pop{font-family:inherit;min-width:150px}
.gp-map-pop b{font-size:.92rem}
.gp-map-pop .terr{font-size:.72rem;color:#9a9a9a;text-transform:uppercase;letter-spacing:.04em}
.gp-map-pop .idx{font-weight:800;font-size:1.1rem}
.gp-map-pop .sp{font-size:.82rem;margin-top:.2rem}
.gp-map-pop .sp-list{list-style:none;margin:.3rem 0 0;padding:0;font-size:.8rem;line-height:1.5;
  max-height:190px;overflow-y:auto}
.gp-map-pop .sp-list li{display:flex;justify-content:space-between;gap:.6rem}
.gp-map-pop .sp-pct{color:var(--muted);font-variant-numeric:tabular-nums}
.gp-map-pop .sp-more{font-size:.72rem;color:var(--muted);margin-top:.25rem}
.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:#130f0b;color:var(--text)}
.leaflet-popup-content{margin:.6rem .8rem}

/* ── Mobilne prilagoditve ── */
@media (max-width:560px){
  .gp-h2{margin-top:2rem;font-size:1.18rem}
  /* Hero: gauge in besedilo naj bosta poravnana levo, ne razpotegnjena. */
  .gp-hero{padding:1.2rem}
  .gp-hero-top{gap:1rem}
  .gp-gauge-wrap{width:104px;height:104px}
  .gp-gauge-num .num{font-size:2.1rem}
  .gp-hero-lvl{font-size:1.55rem}
  /* Kartice v enem stolpcu z malenkost večjim razmikom, da "dihajo". */
  .gp-forests,.gp-vs-grid,.gp-terrmap{grid-template-columns:1fr;gap:.7rem}
  /* Pregled zmožnosti ostane v dveh stolpcih — dvanajst kartic v enem stolpcu
     bi bilo prav tisto drsenje, ki ga mreža odpravlja. Napovedniki na telefonu
     odpadejo (ostaneta ikona in naslov), ker so kartice s tem za polovico
     nižje; besedilo ostane v HTML-ju, skrije ga samo CSS. */
  .gp-feat{grid-template-columns:repeat(2,1fr);gap:.55rem}
  .gp-feat-card{padding:.75rem .8rem .85rem;gap:.45rem}
  .gp-feat-ic{width:2.2rem;height:2.2rem;border-radius:10px}
  .gp-feat-ic svg{width:1.4rem;height:1.4rem}
  .gp-feat-title{font-size:.88rem}
  .gp-feat-sub{display:none}
  .gp-feat-badge{top:.55rem;right:.55rem;font-size:.55rem}
  .gp-hero-note{font-size:.82rem}
  .gp-pricing{grid-template-columns:1fr}
  /* CTA gumbi naj bodo polne širine za lažji dotik. */
  .gp-lockbar .gp-cta,.gp-plan .gp-cta{width:100%;text-align:center}
  .gp-cta-lg{display:block;text-align:center}
}
</style>"""

# ── client-side paywall JS ────────────────────────────────────────────────────

PAGE_JS = """<script>
(function(){
  var API=""" + '"' + WORKER_BASE + '"' + """;
  var LS="mr_gobe_token";
  // Minimal conversion-funnel tracking — no PII (no email, token or image).
  function gaEvent(name,params){
    try{if(typeof gtag==="function")gtag("event",name,params||{});}catch(e){}
  }
  function tok(){
    try{
      var u=new URL(location.href);
      var t=u.searchParams.get("token");
      if(t){localStorage.setItem(LS,t);u.searchParams.delete("token");
        history.replaceState({},"",u.pathname+u.search+u.hash);}
      return localStorage.getItem(LS);
    }catch(e){return null;}
  }
  var lock=document.getElementById("gp-lock");
  var content=document.getElementById("gp-content");
  var statusEl=document.getElementById("gp-premium-status");
  var csWrap=document.getElementById("gp-cs-wrap");
  var csCover=document.getElementById("gp-cs-cover");
  function revealPage(){
    if(csWrap)csWrap.classList.remove("gp-cs-blur");
    if(csCover)csCover.hidden=true;
  }
  function reblurPage(){
    if(csWrap)csWrap.classList.add("gp-cs-blur");
    if(csCover)csCover.hidden=false;
  }
  var TERR_ICON={kisla:"🌲",bazicna:"⛰️",vlazna:"💧"};
  function levelColor(v){
    if(v>=55)return"#34d399";if(v>=35)return"#f59e0b";if(v>=18)return"#fb923c";return"#f87171";
  }
  function levelClass(v){
    if(v>=55)return"gp-pct-hi";if(v>=35)return"gp-pct-mid";if(v>=18)return"gp-pct-low";return"gp-pct-none";
  }
  function hexToRgb(h){h=h.replace('#','');return[parseInt(h.substr(0,2),16),parseInt(h.substr(2,2),16),parseInt(h.substr(4,2),16)];}
  // Small radial gauge for today's soil-moisture "fullness %" (same dry/full
  // normalisation the species scorer itself uses — see gobe_model.py).
  function soilRingSvg(pct){
    var p=(pct==null)?0:Math.max(0,Math.min(100,pct));
    var r=24,circ=2*Math.PI*r,off=circ*(1-p/100);
    return '<svg viewBox="0 0 56 56" class="gp-soil-ring" aria-hidden="true">'+
      '<circle cx="28" cy="28" r="'+r+'" class="gp-soil-ring-bg"/>'+
      '<circle cx="28" cy="28" r="'+r+'" class="gp-soil-ring-fg" stroke-dasharray="'+circ.toFixed(1)+'" stroke-dashoffset="'+off.toFixed(1)+'"/></svg>';
  }
  // Tiny 7-day trend line. Auto-scales to the values it's given (not a fixed
  // 0-100 domain) so small week-to-week moves stay visible instead of
  // flattening near the top/bottom of a wide fixed range.
  function sparklineSvg(vals,color){
    var w=140,h=32,pad=3,n=vals.length;
    var known=vals.filter(function(v){return v!=null;});
    if(!known.length)return'<span class="gp-spark-empty">ni podatka</span>';
    var max=Math.max.apply(null,known),min=Math.min.apply(null,known);
    if(max===min){max+=1;min-=1;}
    var pts=[];
    vals.forEach(function(v,i){
      if(v==null)return;
      var x=pad+(w-2*pad)*(n===1?0:i/(n-1));
      var y=h-pad-(h-2*pad)*((v-min)/(max-min));
      pts.push(x.toFixed(1)+','+y.toFixed(1));
    });
    return '<svg viewBox="0 0 '+w+' '+h+'" class="gp-spark" preserveAspectRatio="none">'+
      '<polyline points="'+pts.join(' ')+'" fill="none" stroke="'+color+'" stroke-width="2" '+
      'stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }
  function soilCardHtml(loc){
    var d0=loc.days[0];
    return '<div class="gp-soil-card">'+
      '<div class="gp-soil-gauge">'+soilRingSvg(d0.soil_moisture_pct)+
      '<span class="gp-soil-num">'+(d0.soil_moisture_pct==null?'—':d0.soil_moisture_pct+'%')+'</span></div>'+
      '<div class="gp-soil-body"><div class="gp-soil-label">💧 Vlaga tal danes <small>(polnost za vrste tega gozda)</small></div>'+
      '<div class="gp-soil-trends">'+
      '<div class="gp-soil-trend"><span class="gp-soil-trend-lbl">Vlaga tal · 7 dni</span>'+
      sparklineSvg(loc.days.map(function(d){return d.soil_moisture_pct;}),"#5c8374")+'</div>'+
      '<div class="gp-soil-trend"><span class="gp-soil-trend-lbl">Gobarski indeks · 7 dni</span>'+
      sparklineSvg(loc.days.map(function(d){return d.overall;}),"#c17f3e")+'</div>'+
      '</div></div></div>';
  }
  // The blended index is 6 independently-scored 0-100 signals; this renders
  // those actual bars instead of just the prose summary, inside the same
  // "Zakaj?" disclosure — the model was already computing all of this.
  // "Temperatura" brez pridevnika: pri mikoriznih vrstah in razkrojevalkah je
  // to talna, pri lesnih zračna (rastejo na lesu nad tlemi) — katera, pove
  // razlaga nad stolpci.
  var FACTOR_LABELS={temperature:"Temperatura",rain_trigger:"Sprožilni dež",rain_base:"Zaloga vode",
    soil_moisture:"Vlaga tal",humidity:"Zračna vlaga",temp_drop:"Nočna ohladitev"};
  var FACTOR_ORDER=["temperature","rain_trigger","rain_base","soil_moisture","humidity","temp_drop"];
  // Skupina in zamik povesta, KATERI dež je vrsto sploh lahko sprožil — brez
  // tega je "sprožilni dež" pri kukmaku in pri jurčku videti kot ista številka.
  var ECO_LABELS={mikorizna:"mikorizna",razkrojevalka:"razkrojevalka stelje",lesna:"lesna razkrojevalka"};
  function ecoBadgeHtml(m){
    if(!m||!m.ecology)return"";
    var lag=m.lag_days?(" · dež pred "+m.lag_days[0]+"–"+m.lag_days[1]+" dnevi"):"";
    return '<span class="gp-eco">'+esc2(ECO_LABELS[m.ecology]||m.ecology)+esc2(lag)+'</span>';
  }
  function factorBarsHtml(components){
    if(!components)return"";
    var rows=FACTOR_ORDER.filter(function(k){return components[k]!=null;});
    if(!rows.length)return"";
    return '<div class="gp-factors">'+rows.map(function(k){
      var v=components[k];
      return '<div class="gp-factor-row"><span class="gp-factor-lbl">'+FACTOR_LABELS[k]+'</span>'+
        '<div class="gp-factor-bar"><div class="gp-factor-fill" style="width:'+v+'%;background:'+levelColor(v)+'"></div></div>'+
        '<span class="gp-factor-val">'+v+' %</span></div>';
    }).join('')+'</div>';
  }
  function explainCardsHtml(day, meta){
    return day.species.slice(0,6).map(function(s){var m=meta[s.id]||{};
      var dblHtml=m.doubles?('<span class="dbl">⚠ dvojnica: '+esc2(m.doubles)+'</span>'):'';
      var factorsHtml=factorBarsHtml(s.components);
      return `<div class="gp-explain-card">
        <div class="gp-explain-photo"><img src="/gobarska-napoved/img/vrste/${s.id}.jpg" loading="lazy" alt=""
          onerror="this.replaceWith(document.createTextNode('🍄'))"></div>
        <div class="gp-explain-body">
        <div class="gp-explain-name">${esc2(m.name_sl||s.id)}</div>
        <div class="gp-explain-idx" style="color:${levelColor(s.index)}">${s.index} %</div>
        <details class="gp-explain-more"><summary></summary><p>${esc2(s.explanation)}${dblHtml}</p>${ecoBadgeHtml(m)}${factorsHtml}</details>
        </div></div>`;}).join('');
  }
  function dayLabel(day, isFirst){
    if(isFirst)return"Danes";
    var dt=new Date(day.date);
    return dt.getDate()+'.'+(dt.getMonth()+1)+'.';
  }
  // Best index anywhere in the 7-day window for this forest — null if the
  // day currently being shown (dayIdx) already is the peak, so the row
  // doesn't state the obvious.
  function bestDayText(loc, dayIdx){
    var days=loc.days,bi=0;
    for(var i=1;i<days.length;i++){if(days[i].overall>days[bi].overall)bi=i;}
    if(bi===dayIdx)return null;
    return dayLabel(days[bi],bi===0)+' · '+days[bi].overall+' %';
  }
  // Single "today per forest" row for an arbitrary day index — used both for
  // the initial render and for the day-chip re-render below, so picking a
  // different day re-ranks/re-labels every forest instead of only the one
  // location detail underneath.
  function forestRowHtml(l, dayIdx, meta, locIdx){
    var o=l.days[dayIdx];
    var pctCls=levelClass(o.overall);
    var spHtml=o.species.slice(0,3).map(function(s){
      var m=meta[s.id]||{};
      var warn=m.doubles?'<span class="gp-sp-warn" title="Nevarna dvojnica: '+esc2(m.doubles)+'">⚠️</span> ':'';
      var ic=`<img class="gp-sp-avatar" src="/gobarska-napoved/img/vrste/${s.id}.jpg" alt="" loading="lazy" `+
        `onerror="this.replaceWith(document.createTextNode('🍄'))">`;
      return '<div class="gp-fsp-row"><div class="gp-fsp-left">'+ic+
        '<span class="gp-fsp-name">'+esc2(m.name_sl||s.id)+'</span></div>'+
        '<div class="gp-sp-right">'+warn+s.index+' %</div></div>';
    }).join('');
    var peak=bestDayText(l,dayIdx);
    var peakHtml=peak?('<span>📈 najboljši dan: '+peak+'</span>')
      :(dayIdx===0?'<span>🔝 danes je vrh tedna</span>':'<span>🔝 vrh tedna</span>');
    var metaHtml=(o.soil_moisture_pct==null?'':'<span>💧 vlaga tal '+o.soil_moisture_pct+' %</span>')+peakHtml;
    return '<div class="gp-forest gp-forest-premium" data-loc-i="'+locIdx+'" tabindex="0" role="button" '+
      'aria-label="Odpri polno napoved za '+esc2(l.name)+'">'+
      '<div class="gp-forest-top"><div class="gp-forest-namewrap">'+
      '<span class="gp-forest-nm">'+(TERR_ICON[l.terrain]||"🌲")+' '+esc2(l.name)+'</span>'+
      '<span class="gp-terr">'+(l.terrain||'')+' · '+l.elev_m+' m</span></div>'+
      '<div class="gp-forest-pct '+pctCls+'"><span class="n">'+o.overall+'/100</span><span class="lvl">'+o.level+'</span></div>'+
      '</div>'+
      '<div class="gp-forest-sp3">'+spHtml+'</div>'+
      '<div class="gp-forest-bottom"><div class="gp-forest-meta">'+metaHtml+'</div>'+
      '<div class="gp-forest-spark">'+sparklineSvg(l.days.map(function(dd){return dd.overall;}),"#c17f3e")+'</div>'+
      '</div>'+
      '<div class="gp-forest-more">🍄 vseh '+o.species.length+' vrst · 🗺️ zemljevid · 7-dnevna napoved →</div>'+
      '</div>';
  }
  function forestsListHtml(locs, dayIdx, meta){
    return locs.map(function(l,i){return {l:l,i:i};})
      .sort(function(a,b){return b.l.days[dayIdx].overall-a.l.days[dayIdx].overall;})
      .map(function(o){return forestRowHtml(o.l,dayIdx,meta,o.i);}).join('');
  }
  function locDetailHtml(loc, meta){
    var html="";
    var top=loc.days[0].species.slice(0,8).map(function(s){return s.id;});
    html+='<h3>'+esc2(loc.name)+' — 7-dnevna napoved</h3>';
    html+='<a class="gp-cta alt gp-map-open-link" target="_blank" rel="noopener" '+
      'href="/gobarska-napoved/zemljevid/?loc='+encodeURIComponent(loc.name)+
      '">🗺️ Odpri lokacijo na zemljevidu</a>';
    html+='<div class="gp-chip-row gp-day-chips">';
    loc.days.forEach(function(day,i){
      html+='<button type="button" class="gp-chip'+(i===0?' active':'')+'" data-day="'+i+'">'+
        dayLabel(day,i===0)+'<span class="gp-chip-pct" style="color:'+levelColor(day.overall)+'">'+day.overall+' %</span></button>';
    });
    html+='</div>';
    html+='<div class="gp-explain-grid" id="gp-explain-grid">'+explainCardsHtml(loc.days[0], meta)+'</div>';
    html+=soilCardHtml(loc);
    html+='<details class="gp-collapse gp-matrix-toggle"><summary>Podrobna tabela vseh dni <small>(vseh 8 vrst)</small></summary>';
    html+='<div class="gp-legend"><span><i style="background:#34d399"></i>Dobra/odlična (≥55%)</span>'+
      '<span><i style="background:#f59e0b"></i>Zmerna (35–54%)</span>'+
      '<span><i style="background:#fb923c"></i>Slaba (18–34%)</span>'+
      '<span><i style="background:#f87171"></i>Brez (&lt;18%)</span></div>';
    html+='<div class="gp-scroll"><table class="gp-matrix"><thead><tr><th style="text-align:left">Vrsta</th>';
    loc.days.forEach(function(day,i){html+='<th>'+dayLabel(day,i===0)+'</th>';});
    html+='</tr></thead><tbody>';
    top.forEach(function(id){html+='<tr><td class="nm">'+(meta[id]?meta[id].name_sl:id)+'</td>';
      loc.days.forEach(function(day){var s=day.species.filter(function(x){return x.id===id;})[0];
        var v=s?s.index:0;var c=levelColor(v);var rgb=hexToRgb(c);
        var alpha=(0.12+0.55*Math.min(100,v)/100).toFixed(2);
        html+='<td><span class="gp-cell" style="background:rgba('+rgb.join(',')+','+alpha+');color:'+c+'">'+v+'</span></td>';});
      html+='</tr>';});
    html+='</tbody></table></div></details>';
    return html;
  }
  function wireDayChips(root, loc, meta){
    var row=root.querySelector(".gp-day-chips");
    var grid=root.querySelector("#gp-explain-grid");
    if(!row||!grid)return;
    row.addEventListener("click",function(e){
      var btn=e.target.closest(".gp-chip");
      if(!btn)return;
      row.querySelectorAll(".gp-chip").forEach(function(c){c.classList.remove("active");});
      btn.classList.add("active");
      grid.innerHTML=explainCardsHtml(loc.days[parseInt(btn.dataset.day,10)], meta);
    });
  }
  function render(d){
    var meta=d.species_meta||{};
    var locs=d.locations||[];
    var home=locs.filter(function(l){return l.home;})[0]||locs[0];
    var html="";
    // per-forest rows — richer than the free list: top-3 species (not just
    // the winner), soil moisture, a best-day-this-week hint and a 7-day
    // trend line, all already computed per location — this is the one part
    // of the page a paying user should see more in than the free teaser.
    // A day-chip row lets that whole ranked list be re-drawn for any of the
    // 7 days, not just today, without touching the per-location detail below.
    html+='<h3>Napoved po gozdovih</h3>';
    html+='<div class="gp-chip-row" id="gp-today-day-chips">';
    home.days.forEach(function(day,i){
      var peak=Math.max.apply(null,locs.map(function(l){return l.days[i].overall;}));
      html+='<button type="button" class="gp-chip'+(i===0?' active':'')+'" data-day="'+i+'">'+
        dayLabel(day,i===0)+'<span class="gp-chip-pct" style="color:'+levelColor(peak)+'">'+peak+' %</span></button>';
    });
    html+='</div>';
    html+='<div class="gp-forests-premium" id="gp-today-forests">'+forestsListHtml(locs,0,meta)+'</div>';
    // location picker — 7-day per-species matrix for ANY of the 16 areas, not just home
    html+='<h3>7-dnevna napoved po vrstah — izberi območje</h3>';
    html+='<div class="gp-chip-row" id="gp-loc-chips">';
    locs.forEach(function(l,i){
      var o=l.days[0];
      html+='<button type="button" class="gp-chip'+(l===home?' active':'')+'" data-i="'+i+'">'+
        esc2(l.name)+'<span class="gp-chip-pct" style="color:'+levelColor(o.overall)+'">'+o.overall+' %</span></button>';
    });
    html+='</div>';
    html+='<div id="gp-loc-detail">'+locDetailHtml(home, meta)+'</div>';
    content.innerHTML=html;
    content.hidden=false;lock.hidden=true;
    var todayDayChips=document.getElementById("gp-today-day-chips");
    var todayForests=document.getElementById("gp-today-forests");
    if(todayDayChips&&todayForests){todayDayChips.addEventListener("click",function(e){
      var btn=e.target.closest(".gp-chip");
      if(!btn)return;
      todayDayChips.querySelectorAll(".gp-chip").forEach(function(c){c.classList.remove("active");});
      btn.classList.add("active");
      btn.scrollIntoView({inline:"center",block:"nearest",behavior:"smooth"});
      todayForests.innerHTML=forestsListHtml(locs, parseInt(btn.dataset.day,10), meta);
    });}
    var chipRow=document.getElementById("gp-loc-chips");
    var detail=document.getElementById("gp-loc-detail");
    wireDayChips(detail, home, meta);
    // Shared by the region-chip row and the forest-card click below, so
    // clicking a forest card up top and picking its chip lower down land on
    // exactly the same detail view (species matrix, map link, day picker).
    function selectLoc(i, scrollTarget){
      var newLoc=locs[i];
      if(chipRow){
        chipRow.querySelectorAll(".gp-chip").forEach(function(c){c.classList.remove("active");});
        var btn=chipRow.querySelector('.gp-chip[data-i="'+i+'"]');
        if(btn)btn.scrollIntoView({inline:"center",block:"nearest",behavior:"smooth"});
        if(btn)btn.classList.add("active");
      }
      detail.innerHTML=locDetailHtml(newLoc, meta);
      wireDayChips(detail, newLoc, meta);
      (scrollTarget||detail).scrollIntoView({block:"start",behavior:"smooth"});
    }
    if(chipRow){chipRow.addEventListener("click",function(e){
      var btn=e.target.closest(".gp-chip");
      if(!btn)return;
      selectLoc(parseInt(btn.dataset.i,10));
    });}
    // Forest cards up top (the compact "Napoved po gozdovih" summary) are
    // clickable too — jumping straight to that area's full species/day
    // picker and map link below, instead of leaving the top section a
    // dead-end list and the region picker undiscovered further down.
    if(todayForests){todayForests.addEventListener("click",function(e){
      var card=e.target.closest(".gp-forest-premium");
      if(!card)return;
      selectLoc(parseInt(card.dataset.locI,10), document.getElementById("gp-loc-chips"));
    });
    todayForests.addEventListener("keydown",function(e){
      if(e.key!=="Enter"&&e.key!==" ")return;
      var card=e.target.closest(".gp-forest-premium");
      if(!card)return;
      e.preventDefault();
      selectLoc(parseInt(card.dataset.locI,10), document.getElementById("gp-loc-chips"));
    });}
  }
  // ── Moji alarmi: per-user rule editor (species/location/elevation/threshold),
  // synced via /premium/alerts. A rule with no species/location picked means
  // "katerakoli vrsta" / "katerokoli območje" — same semantics the daily
  // /premium/notify check uses server-side.
  function initAlerts(token, d){
    var wrap=document.getElementById("gp-alerts");
    var rowsEl=document.getElementById("gp-alert-rows");
    var addBtn=document.getElementById("gp-alert-add");
    var saveBtn=document.getElementById("gp-alert-save");
    var msgEl=document.getElementById("gp-alert-msg");
    if(!wrap||!rowsEl)return;
    wrap.hidden=false;
    var MAX_RULES=5;
    var speciesList=Object.keys(d.species_meta||{}).map(function(id){
      return {id:id,name:(d.species_meta[id]||{}).name_sl||id};
    }).sort(function(a,b){return a.name.localeCompare(b.name,"sl");});
    var locs=d.locations||[];
    function speciesSelectHtml(sel){
      return '<select class="gp-alert-sp"><option value=""'+(sel?"":" selected")+'>Katerakoli vrsta</option>'+
        speciesList.map(function(s){return '<option value="'+s.id+'"'+(sel===s.id?" selected":"")+'>'+esc2(s.name)+'</option>';}).join('')+
        '</select>';
    }
    function locSelectHtml(sel){
      return '<select class="gp-alert-loc"><option value=""'+(sel?"":" selected")+'>Katerokoli območje</option>'+
        locs.map(function(l){return '<option value="'+esc2(l.name)+'"'+(sel===l.name?" selected":"")+'>'+esc2(l.name)+' ('+l.elev_m+' m)</option>';}).join('')+
        '</select>';
    }
    function rowHtml(rule){
      rule=rule||{};
      return '<div class="gp-alert-row">'+speciesSelectHtml(rule.species_id||"")+locSelectHtml(rule.location||"")+
        '<input type="number" class="gp-alert-elev" placeholder="nad m n.v. (neobv.)" min="0" max="3000" value="'+
        (rule.min_elev_m!=null?rule.min_elev_m:"")+'">'+
        '<div class="gp-alert-thr"><input type="number" class="gp-alert-th" min="1" max="100" value="'+
        (rule.threshold!=null?rule.threshold:70)+'"><span>%</span></div>'+
        '<button type="button" class="gp-alert-del" aria-label="Odstrani alarm">🗑</button></div>';
    }
    function wireDeletes(){
      rowsEl.querySelectorAll(".gp-alert-del").forEach(function(btn){
        btn.onclick=function(){
          var row=btn.closest(".gp-alert-row");
          if(rowsEl.children.length>1)row.remove();
          else row.outerHTML=rowHtml(null);
          wireDeletes();
        };
      });
    }
    function renderRows(rules){
      rowsEl.innerHTML=(rules&&rules.length?rules:[{}]).map(rowHtml).join("");
      wireDeletes();
    }
    addBtn.addEventListener("click",function(){
      if(rowsEl.children.length>=MAX_RULES){msgEl.textContent="Največ "+MAX_RULES+" alarmov.";return;}
      rowsEl.insertAdjacentHTML("beforeend",rowHtml(null));
      wireDeletes();
    });
    saveBtn.addEventListener("click",function(){
      var rules=[].slice.call(rowsEl.querySelectorAll(".gp-alert-row")).map(function(row){
        var elevRaw=row.querySelector(".gp-alert-elev").value;
        var thrRaw=row.querySelector(".gp-alert-th").value;
        return {
          species_id: row.querySelector(".gp-alert-sp").value||null,
          location: row.querySelector(".gp-alert-loc").value||null,
          min_elev_m: elevRaw===""?null:Math.max(0,parseInt(elevRaw,10)||0),
          threshold: Math.max(1,Math.min(100,parseInt(thrRaw,10)||70)),
        };
      });
      msgEl.textContent="Shranjujem …";
      fetch(API+"/premium/alerts",{method:"POST",
        headers:{"Content-Type":"application/json","Authorization":"Bearer "+token},
        body:JSON.stringify({rules:rules})})
        .then(function(r){return r.json().then(function(j){return{ok:r.ok,body:j};});})
        .then(function(res){
          msgEl.textContent=res.ok?"✓ Alarmi shranjeni.":(res.body&&res.body.error?res.body.error:"Napaka pri shranjevanju.");
          if(res.ok)gaEvent("alarm_create",{count:rules.length});
        })
        .catch(function(){msgEl.textContent="Napaka pri povezavi. Poskusi znova.";});
    });
    fetch(API+"/premium/alerts?token="+encodeURIComponent(token))
      .then(function(r){return r.json();})
      .then(function(res){renderRows(res&&res.rules);})
      .catch(function(){renderRows(null);});
  }
  function initIdentify(token){
    var card=document.getElementById("gp-identify");
    var fileInput=document.getElementById("gp-id-photo");
    var preview=document.getElementById("gp-id-preview");
    var btn=document.getElementById("gp-id-btn");
    var statusEl2=document.getElementById("gp-id-status");
    var resultEl=document.getElementById("gp-id-result");
    if(!card||!fileInput||!btn)return;
    card.hidden=false;
    var pendingImg=null;
    var CONF_CLS={visoka:"hi",srednja:"mid",nizka:"lo"};
    fileInput.addEventListener("change",function(){
      var f=fileInput.files&&fileInput.files[0];
      if(!f)return;
      var img=new Image();
      var reader=new FileReader();
      reader.onload=function(e){
        img.onload=function(){
          var maxW=900,scale=Math.min(1,maxW/img.width);
          var w=Math.round(img.width*scale),h=Math.round(img.height*scale);
          var c=document.createElement("canvas");c.width=w;c.height=h;
          c.getContext("2d").drawImage(img,0,0,w,h);
          pendingImg=c.toDataURL("image/jpeg",0.78);
          preview.src=pendingImg;preview.style.display="inline-block";
          btn.disabled=false;resultEl.innerHTML="";statusEl2.textContent="";
        };
        img.src=e.target.result;
      };
      reader.readAsDataURL(f);
    });
    btn.addEventListener("click",function(){
      if(!pendingImg)return;
      gaEvent("ai_identification_start");
      btn.disabled=true;statusEl2.textContent="Analiziram fotografijo …";resultEl.innerHTML="";
      fetch(API+"/premium/identify",{method:"POST",
        headers:{"Content-Type":"application/json","Authorization":"Bearer "+token},
        body:JSON.stringify({image:pendingImg})})
        .then(function(r){return r.json().then(function(j){return{ok:r.ok,body:j};});})
        .then(function(res){
          btn.disabled=false;
          if(!res.ok){statusEl2.textContent=res.body&&res.body.error?res.body.error:"Napaka pri prepoznavi.";return;}
          statusEl2.textContent="";
          var d=res.body;
          gaEvent("ai_identification_complete",{candidates:(d.candidates||[]).length});
          var html=(d.candidates||[]).map(function(c){
            var confCls=CONF_CLS[c.confidence]||"mid";
            return '<div class="gp-id-card"><div class="gp-id-head"><span><span class="gp-id-name">'+
              esc2(c.name_sl||"?")+'</span><span class="gp-id-lat">'+esc2(c.name_lat||"")+'</span></span>'+
              '<span class="gp-id-conf '+confCls+'">zanesljivost: '+esc2(c.confidence||"?")+'</span></div>'+
              (c.edibility?'<div class="gp-id-reason"><b style="color:var(--text)">AI ocena užitnosti: '+esc2(c.edibility)+'</b></div>':'')+
              (c.reasoning?'<div class="gp-id-reason">'+esc2(c.reasoning)+'</div>':'')+
              (c.warning?'<div class="gp-id-warn">⚠ '+esc2(c.warning)+'</div>':'')+'</div>';
          }).join("");
          if(d.note)html+='<div class="gp-id-note">'+esc2(d.note)+'</div>';
          if(!html)html='<div class="gp-id-note">AI ni prepoznal gobe na fotografiji. Poskusi z bolj ostro sliko klobuka in trosovnice.</div>';
          else html+='<div class="gp-id-note">⚠ AI rezultat ni potrditev užitnosti — je le najverjetnejši '+
            'predlog iz fotografije. Gobe ne uživaj samo na podlagi tega rezultata.</div>';
          resultEl.innerHTML=html;
        })
        .catch(function(){btn.disabled=false;statusEl2.textContent="Napaka pri povezavi. Poskusi znova.";});
    });
  }
  function esc2(s){return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
  var SL_MON=["","januarja","februarja","marca","aprila","maja","junija","julija","avgusta","septembra","oktobra","novembra","decembra"];
  function fmtExpires(iso){
    try{ var d=new Date(iso); return d.getDate()+". "+SL_MON[d.getMonth()+1]+" "+d.getFullYear(); }
    catch(e){ return iso; }
  }
  var pricingWrap=document.getElementById("gp-pricing-wrap");
  var heroUnlock=document.getElementById("gp-hero-unlock");
  function hidePricing(){
    if(pricingWrap)pricingWrap.hidden=true;
    if(heroUnlock)heroUnlock.hidden=true;
  }
  function skeletonHtml(){
    var block=function(h){return '<div class="gp-loadskel" style="height:'+h+'"></div>';};
    return '<div class="gp-loadskel-group">'+block('1.4rem')+block('5.2rem')+block('5.2rem')+
      block('2.6rem')+block('9rem')+block('9rem')+'</div>';
  }
  var t=tok();
  if(t){
    // A paying user shouldn't see the pre-launch cover or the "Naroči se"
    // upsell while their own data is still in flight — reveal the page and
    // swap straight to a skeleton instead of flashing either first.
    revealPage();
    if(lock)lock.hidden=true;
    if(content){content.hidden=false;content.innerHTML=skeletonHtml();}
    fetch(API+"/premium/verify?token="+encodeURIComponent(t))
      .then(function(r){if(!r.ok)throw 0;return r.json();})
      .then(function(v){
        if(!v||!v.ok)return;
        hidePricing();
        if(statusEl){
          var planTxt=v.plan==="sezona"?"sezonska naročnina":"mesečna naročnina";
          statusEl.hidden=false;
          statusEl.textContent="✓ Premium aktiven ("+planTxt+(v.expires?", velja do "+fmtExpires(v.expires):"")+").";
        }
      })
      .catch(function(){});
    fetch(API+"/premium/forecast?token="+encodeURIComponent(t))
      .then(function(r){if(!r.ok)throw 0;return r.json();})
      .then(function(d){render(d);initIdentify(t);initAlerts(t,d);})
      .catch(function(){
        // Token turned out to be invalid/expired or the fetch genuinely
        // failed — fall back to the pre-launch cover instead of leaving the
        // skeleton spinning forever.
        if(content){content.hidden=true;content.innerHTML="";}
        if(lock)lock.hidden=false;
        reblurPage();
      });
  }
  var f=document.getElementById("gp-login");
  if(f){f.addEventListener("submit",function(e){e.preventDefault();
    var msg=document.getElementById("gp-login-msg");var em=(f.email.value||"").trim();
    if(!em){return;}msg.textContent="Pošiljam …";
    gaEvent("premium_access_request");
    fetch(API+"/premium/login",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({email:em})}).then(function(r){return r.json();})
      .then(function(x){msg.textContent=x.msg||"Če je e-naslov naročen, smo nanj poslali povezavo za dostop.";})
      .catch(function(){msg.textContent="Napaka pri pošiljanju. Poskusi znova.";});});}

  // ── Paddle.js overlay checkout ──────────────────────────────────────────
  // Config comes from window.MR_PADDLE (injected in <head>); when it or the
  // token is missing, buttons fall back to scrolling to #pricing.
  var cfg=window.MR_PADDLE||null;
  var ready=false;
  if(cfg&&cfg.token&&window.Paddle){
    try{
      if(cfg.env==="sandbox"){Paddle.Environment.set("sandbox");}
      Paddle.Initialize({token:cfg.token});
      ready=true;
    }catch(e){ready=false;}
  }
  function checkoutMsg(txt){
    var el=document.getElementById("gp-checkout-msg");
    if(el){el.textContent=txt;}
  }
  document.querySelectorAll("[data-paddle]").forEach(function(btn){
    btn.addEventListener("click",function(e){
      var plan=btn.getAttribute("data-paddle");
      var src=btn.getAttribute("data-src")||"unknown";
      gaEvent("premium_cta_click",{plan:plan,source:src});
      var priceId=cfg?cfg.prices[plan]:null;
      if(!ready||!priceId){
        // Fallback: not configured yet — go to pricing, don't break the page.
        var p=document.getElementById("pricing");
        if(p){e.preventDefault();p.scrollIntoView({behavior:"smooth"});
          checkoutMsg("Spletno plačilo bo kmalu na voljo. Za dostop lahko medtem pišeš na filip.eremita@gmail.com.");}
        return;
      }
      e.preventDefault();
      gaEvent("premium_checkout_start",{plan:plan,source:src});
      Paddle.Checkout.open({
        items:[{priceId:priceId,quantity:1}],
        customData:{plan:plan},
        settings:{displayMode:"overlay",theme:"dark",locale:"sl"},
        eventCallback:function(ev){
          if(ev&&ev.name==="checkout.completed"){
            checkoutMsg("✅ Hvala! Na tvoj e-naslov smo poslali povezavo za dostop — preveri tudi vsiljeno pošto.");
          }
        }
      });
    });
  });

  // SOS panel toggle
  var sosBtn=document.getElementById("gp-sos-btn"), sosPanel=document.getElementById("gp-sos-panel");
  if(sosBtn&&sosPanel){
    sosBtn.addEventListener("click",function(e){e.stopPropagation();sosPanel.classList.toggle("open");});
    document.addEventListener("click",function(e){
      if(sosPanel.classList.contains("open")&&!sosPanel.contains(e.target)&&e.target!==sosBtn)sosPanel.classList.remove("open");
    });
  }

  // Share chip — native share sheet where available, clipboard fallback
  var shareBtn=document.getElementById("gp-share-btn"), shareMsg=document.getElementById("gp-share-msg");
  if(shareBtn){
    shareBtn.addEventListener("click",function(){
      var pct=shareBtn.dataset.pct, lvl=shareBtn.dataset.lvl;
      var data={title:"Gobarska napoved",
        text:"Gobarski indeks danes: "+pct+" % ("+lvl+") — Zgornja Savinjska dolina",
        url:location.href};
      if(navigator.share){navigator.share(data).catch(function(){});return;}
      if(navigator.clipboard&&navigator.clipboard.writeText){
        navigator.clipboard.writeText(data.url).then(function(){
          if(shareMsg){shareMsg.textContent="Povezava kopirana.";setTimeout(function(){shareMsg.textContent="";},2500);}
        }).catch(function(){});
      }
    });
  }

})();
</script>"""

# ── Gobarjev dnevnik: local-only GPS+photo diary. Premium naročniki (token v
# localStorage) dobijo dodatno sinhronizacijo prek /premium/diary(+/photo) —
# glej DIARY_JS spodaj. Brez tokena ostane popolnoma lokalno (localStorage). ──
DIARY_JS = """<script>
(function(){
  var LS="mr_gobe_dnevnik";
  var API=""" + '"' + WORKER_BASE + '"' + """;
  var TOKKEY="mr_gobe_token";
  var form=document.getElementById("gp-diary-form");
  if(!form)return;
  var listEl=document.getElementById("gp-diary-list");
  var dateEl=document.getElementById("gp-d-date");
  var spEl=document.getElementById("gp-d-species");
  var notesEl=document.getElementById("gp-d-notes");
  var geoBtn=document.getElementById("gp-d-geo");
  var geoStatus=document.getElementById("gp-d-geo-status");
  var photoInput=document.getElementById("gp-d-photo");
  var photoPreview=document.getElementById("gp-d-photo-preview");
  var privEl=document.getElementById("gp-diary-priv");
  var syncEl=document.getElementById("gp-diary-sync");
  var pendingGeo=null, pendingPhoto=null;
  dateEl.valueAsDate=new Date();

  function token(){ try{return localStorage.getItem(TOKKEY);}catch(e){return null;} }
  function load(){ try{return JSON.parse(localStorage.getItem(LS))||[];}catch(e){return [];} }
  function save(arr){
    try{ localStorage.setItem(LS, JSON.stringify(arr)); return true; }
    catch(e){ geoStatus.textContent="Shramba brskalnika je polna — izbriši kakšno starejšo najdbo (morda ima veliko fotografijo)."; return false; }
  }

  // ── Sinhronizacija z oblakom (samo premium — token v localStorage) ──
  function syncPush(arr){
    var t=token();
    if(!t)return Promise.resolve();
    return fetch(API+"/premium/diary",{method:"POST",
      headers:{"Content-Type":"application/json","Authorization":"Bearer "+t},
      body:JSON.stringify({entries:arr})}).catch(function(){});
  }
  function uploadPhoto(dataUrl){
    var t=token();
    if(!t||!dataUrl||dataUrl.indexOf("data:")!==0)return Promise.resolve(dataUrl);
    return fetch(API+"/premium/diary/photo",{method:"POST",
      headers:{"Content-Type":"application/json","Authorization":"Bearer "+t},
      body:JSON.stringify({image:dataUrl})})
      .then(function(r){return r.ok?r.json():null;})
      .then(function(j){return j&&j.url?j.url:dataUrl;})
      .catch(function(){return dataUrl;});
  }

  geoBtn.addEventListener("click",function(){
    if(!navigator.geolocation){ geoStatus.textContent="Brskalnik ne podpira lokacije."; return; }
    geoStatus.textContent="Iščem lokacijo …";
    navigator.geolocation.getCurrentPosition(function(pos){
      pendingGeo={lat:pos.coords.latitude, lon:pos.coords.longitude};
      geoStatus.textContent="📍 "+pendingGeo.lat.toFixed(4)+", "+pendingGeo.lon.toFixed(4)+" zabeleženo";
    },function(err){
      geoStatus.textContent="Lokacije ni bilo mogoče pridobiti ("+(err&&err.message?err.message:"zavrnjeno")+").";
    },{enableHighAccuracy:true,timeout:10000});
  });

  photoInput.addEventListener("change",function(){
    var f=photoInput.files&&photoInput.files[0];
    if(!f)return;
    var img=new Image();
    var reader=new FileReader();
    reader.onload=function(e){
      img.onload=function(){
        var maxW=700, scale=Math.min(1,maxW/img.width);
        var w=Math.round(img.width*scale), h=Math.round(img.height*scale);
        var c=document.createElement("canvas"); c.width=w; c.height=h;
        c.getContext("2d").drawImage(img,0,0,w,h);
        pendingPhoto=c.toDataURL("image/jpeg",0.72);
        photoPreview.src=pendingPhoto; photoPreview.style.display="inline-block";
      };
      img.src=e.target.result;
    };
    reader.readAsDataURL(f);
  });

  function mapLink(g){ return g?("https://www.google.com/maps?q="+g.lat+","+g.lon):null; }
  function esc(s){ return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
  function photoSrc(p){
    if(!p)return null;
    if(p.indexOf("/premium/diary/img/")===0){
      var t=token();
      return API+p+(t?"?token="+encodeURIComponent(t):"");
    }
    return p;
  }

  function render(){
    var arr=load();
    if(!arr.length){ listEl.innerHTML='<div class="gp-diary-empty">Tvoj dnevnik je prazen — dodaj prvo najdbo zgoraj.</div>'; return; }
    listEl.innerHTML=arr.map(function(e,i){
      var src=photoSrc(e.photo);
      var thumb=src?('<img class="gp-diary-thumb" src="'+src+'" alt="">')
                        :'<div class="gp-diary-thumb-ph">🍄</div>';
      var loc=e.lat!=null?('<a href="'+mapLink(e)+'" target="_blank" rel="noopener">📍 '+e.lat.toFixed(4)+', '+e.lon.toFixed(4)+'</a>'):'';
      return '<div class="gp-diary-entry">'+thumb+
        '<div class="gp-diary-body"><div class="gp-diary-sp">'+esc(e.species||"Neznana vrsta")+'</div>'+
        '<div class="gp-diary-meta">'+esc(e.date||"")+(loc?' · '+loc:'')+'</div>'+
        (e.notes?('<div class="gp-diary-notes">'+esc(e.notes)+'</div>'):'')+'</div>'+
        '<button type="button" class="gp-diary-del" data-i="'+i+'" aria-label="Izbriši">🗑</button></div>';
    }).join("");
    listEl.querySelectorAll(".gp-diary-del").forEach(function(btn){
      btn.addEventListener("click",function(){
        var arr2=load(); arr2.splice(parseInt(btn.getAttribute("data-i"),10),1); save(arr2); render();
        syncPush(arr2);
      });
    });
  }

  form.addEventListener("submit",function(e){
    e.preventDefault();
    var species=spEl.value.trim(), notes=notesEl.value.trim(), date=dateEl.value;
    var geo=pendingGeo, photo=pendingPhoto;
    spEl.value=""; notesEl.value=""; dateEl.valueAsDate=new Date();
    pendingGeo=null; pendingPhoto=null; geoStatus.textContent=""; photoInput.value="";
    photoPreview.style.display="none"; photoPreview.src="";
    uploadPhoto(photo).then(function(photoRef){
      var arr=load();
      arr.unshift({
        date:date, species:species, notes:notes,
        lat:geo?geo.lat:null, lon:geo?geo.lon:null,
        photo:photoRef, ts:new Date().toISOString()
      });
      if(save(arr)){ render(); syncPush(arr); }
    });
  });

  render();

  // ── Ob nalaganju: premium naročniki dobijo dnevnik iz oblaka (vse naprave) ──
  var t=token();
  if(t){
    if(privEl)privEl.innerHTML='☁️ Najdbe se sinhronizirajo med tvojimi napravami (premium) — fotografije vidiš samo ti.';
    if(syncEl){syncEl.hidden=false; syncEl.textContent="Sinhroniziram …";}
    fetch(API+"/premium/diary?token="+encodeURIComponent(t))
      .then(function(r){return r.ok?r.json():null;})
      .then(function(j){
        var remote=j&&Array.isArray(j.entries)?j.entries:null;
        if(remote===null){ if(syncEl)syncEl.hidden=true; return; }
        if(remote.length){
          save(remote); render();
          if(syncEl){syncEl.textContent="✓ Sinhronizirano."; setTimeout(function(){syncEl.hidden=true;},4000);}
          return;
        }
        var local=load();
        if(!local.length){ if(syncEl)syncEl.hidden=true; return; }
        // Prvi sync po naročnini — prenesi obstoječe lokalne najdbe v oblak.
        Promise.all(local.map(function(e){
          return uploadPhoto(e.photo).then(function(ref){
            return {date:e.date,species:e.species,notes:e.notes,lat:e.lat,lon:e.lon,photo:ref,ts:e.ts};
          });
        })).then(function(migrated){
          save(migrated); render();
          syncPush(migrated).then(function(){
            if(syncEl){syncEl.textContent="✓ Sinhronizirano."; setTimeout(function(){syncEl.hidden=true;},4000);}
          });
        });
      })
      .catch(function(){ if(syncEl)syncEl.textContent="Sinhronizacija ni uspela — najdbe ostajajo lokalno."; });
  }
})();
</script>"""

# ── Baza vrst: iskanje, filtri in postopno prikazovanje ──────────────────────
# 300 kartic naenkrat je na telefonu preveč — v HTML so vse (pajek jih mora
# videti), naenkrat pa se izriše prvih PAGE, ostalo odpre gumb ali filter.
SP_JS = """<script>
(function(){
  var grid=document.getElementById("gp-sp-grid");
  if(!grid)return;
  var PAGE=24;
  var cards=[].slice.call(grid.querySelectorAll(".gp-sp-card"));
  var qEl=document.getElementById("gp-sp-q");
  var moreEl=document.getElementById("gp-sp-more");
  var countEl=document.getElementById("gp-sp-count");
  var seasonEl=document.getElementById("gp-sp-season");
  var month=String(new Date().getMonth()+1);
  var seasonOnly=false, query="", shown=PAGE;

  function norm(s){
    return (s||"").toLowerCase().normalize("NFKD").replace(/[\\u0300-\\u036f]/g,"")
      .replace(/[^a-z0-9 ]+/g," ").trim();
  }
  function matches(c){
    if(query && c.getAttribute("data-q").indexOf(query)<0) return false;
    if(seasonOnly && (c.getAttribute("data-m")||"").split(",").indexOf(month)<0) return false;
    return true;
  }
  function render(){
    var n=0;
    for(var i=0;i<cards.length;i++){
      var ok=matches(cards[i]);
      if(ok)n++;
      cards[i].hidden = !ok || n>shown;
    }
    moreEl.hidden = n<=shown;
    if(!moreEl.hidden) moreEl.textContent = "Pokaži več vrst ("+(n-shown)+")";
    countEl.hidden=false;
    // Rodilnik: "od ene vrste", od dveh naprej "od … vrst".
    countEl.textContent = n===0 ? "Nobena vrsta ne ustreza iskanju."
      : "Prikazanih "+Math.min(shown,n)+" od "+n+(n===1?" vrste.":" vrst.");
  }
  if(seasonEl){
    seasonEl.addEventListener("click",function(){
      seasonOnly=!seasonOnly;
      seasonEl.classList.toggle("on",seasonOnly);
      seasonEl.setAttribute("aria-pressed",seasonOnly?"true":"false");
      shown=PAGE; render();
    });
  }
  if(qEl){
    var t;
    qEl.addEventListener("input",function(){
      clearTimeout(t);
      t=setTimeout(function(){ query=norm(qEl.value); shown=PAGE; render(); },150);
    });
  }
  moreEl.addEventListener("click",function(){ shown+=PAGE*2; render(); });
  // Vrstica skupin drsi vodoravno; na strani skupine je aktivna lahko zunaj
  // vidnega dela, zato jo pripeljemo v pogled (brez premika same strani).
  var active=document.querySelector(".gp-sp-chips a.on");
  if(active && active.parentNode.scrollWidth>active.parentNode.clientWidth){
    active.parentNode.scrollLeft = active.offsetLeft - 12;
  }
  render();
})();
</script>"""

# ── Sezonski trend: SVG graf letos vs. pretekla leta (iz trend.json) ─────────
TREND_JS = """<script>
(function(){
  var wrap=document.getElementById("gp-trend");
  if(!wrap)return;
  var MONTHS=["04","05","06","07","08","09","10","11"];
  var MLBL={"04":"Apr","05":"Maj","06":"Jun","07":"Jul","08":"Avg","09":"Sep","10":"Okt","11":"Nov"};
  var SL_MONTH=["","januar","februar","marec","april","maj","junij","julij","avgust","september","oktober","november","december"];
  var PAST_COLORS=["#8c8574","#a9a08c","#7a8a72","#9c8f6e"];

  function fmtDate(iso){
    var p=iso.split("-"); var d=parseInt(p[2],10); var m=SL_MONTH[parseInt(p[1],10)];
    return d+". "+m+" "+p[0]+".";
  }

  function render(data){
    var years=Object.keys(data.years||{}).sort();
    if(!years.length){wrap.innerHTML='<div class="gp-msg">Trend še ni na voljo.</div>';return;}
    var curYear=String(new Date().getFullYear());
    var W=640,H=220,padL=32,padR=12,padT=10,padB=26;
    var plotW=W-padL-padR, plotH=H-padT-padB;
    function x(mi){return padL+plotW*(mi/(MONTHS.length-1));}
    function y(v){return padT+plotH*(1-Math.max(0,Math.min(100,v))/100);}

    var svg='<svg class="gp-trend-svg" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet">';
    // gridlines + y labels
    [0,25,50,75,100].forEach(function(v){
      svg+='<line x1="'+padL+'" y1="'+y(v)+'" x2="'+(W-padR)+'" y2="'+y(v)+'" stroke="rgba(255,255,255,.08)" stroke-width="1"/>';
      svg+='<text x="'+(padL-6)+'" y="'+(y(v)+3)+'" text-anchor="end" font-size="9" fill="var(--muted)">'+v+'</text>';
    });
    // month labels
    MONTHS.forEach(function(m,i){
      svg+='<text x="'+x(i)+'" y="'+(H-6)+'" text-anchor="middle" font-size="9" fill="var(--muted)">'+MLBL[m]+'</text>';
    });
    // past years first (so current year draws on top), then current year
    var pastIdx=0;
    years.forEach(function(yr){
      if(yr===curYear)return;
      drawLine(yr, PAST_COLORS[pastIdx%PAST_COLORS.length], 1.6, .75);
      pastIdx++;
    });
    if(years.indexOf(curYear)!==-1) drawLine(curYear, "#f59e0b", 3, 1);
    svg+='</svg>';

    function drawLine(yr, color, width, opacity){
      var ma=data.years[yr].monthly_avg||{};
      var pts=[];
      MONTHS.forEach(function(m,i){
        if(ma[m]!=null) pts.push(x(i)+","+y(ma[m]));
      });
      if(pts.length<2)return;
      svg+='<polyline points="'+pts.join(" ")+'" fill="none" stroke="'+color+'" stroke-width="'+width+
        '" stroke-opacity="'+opacity+'" stroke-linecap="round" stroke-linejoin="round"/>';
      MONTHS.forEach(function(m,i){
        if(ma[m]!=null) svg+='<circle cx="'+x(i)+'" cy="'+y(ma[m])+'" r="'+(yr===curYear?3:1.8)+'" fill="'+color+'" fill-opacity="'+opacity+'"/>';
      });
    }

    var legend='<div class="gp-trend-legend">';
    var pastIdx2=0;
    years.forEach(function(yr){
      var isCur=(yr===curYear);
      var col=isCur?"#f59e0b":PAST_COLORS[pastIdx2%PAST_COLORS.length];
      if(!isCur)pastIdx2++;
      legend+='<span><i style="background:'+col+'"></i>'+yr+(isCur?' (letos)':'')+'</span>';
    });
    legend+='</div>';

    // best-day highlight: overall best across all years + this year's own best (if different)
    var allBest=null;
    years.forEach(function(yr){
      var b=data.years[yr].best_day;
      if(b&&(!allBest||b.overall>allBest.overall))allBest={yr:yr,b:b};
    });
    var thisBest=data.years[curYear]&&data.years[curYear].best_day;
    var bestHtml='';
    if(allBest){
      bestHtml+='<div class="gp-trend-best">🏆 Najboljši dan v zadnjih '+years.length+' letih: <b>'+
        fmtDate(allBest.b.date)+'</b> — '+allBest.b.overall+' % ('+esc3(allBest.b.top||'')+')';
      if(thisBest&&allBest.yr!==curYear){
        bestHtml+='<br>🍄 Letošnji vrh do zdaj: <b>'+fmtDate(thisBest.date)+'</b> — '+thisBest.overall+
          ' % ('+esc3(thisBest.top||'')+')';
      }
      bestHtml+='</div>';
    }

    wrap.innerHTML=svg+legend+bestHtml;
  }
  function esc3(s){return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

  fetch("/gobarska-napoved/trend.json")
    .then(function(r){if(!r.ok)throw 0;return r.json();})
    .then(render)
    .catch(function(){wrap.innerHTML='<div class="gp-msg">Trend trenutno ni na voljo.</div>';});
})();
</script>"""


def paddle_head():
    """Paddle.js loader + client config injected into <head>. When the client
    token is not configured yet, injects window.MR_PADDLE=null so the buttons
    fall back to #pricing instead of breaking."""
    if not PADDLE_CLIENT_TOKEN:
        return "<script>window.MR_PADDLE=null;</script>"
    import json as _json
    cfg = _json.dumps({
        "env": PADDLE_ENV,
        "token": PADDLE_CLIENT_TOKEN,
        "prices": {"monthly": PADDLE_PRICE_MONTHLY, "season": PADDLE_PRICE_SEASON},
    })
    return ('<script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>\n'
            f"<script>window.MR_PADDLE={cfg};</script>")


# Status ramp tied to the forecast level — green (good) → amber (moderate) → red.
# The level word is always shown alongside, so colour is never the sole signal.
def level_color(pct):
    if pct >= 55: return "#34d399"   # DOBRA / ODLIČNA
    if pct >= 35: return "#f59e0b"   # ZMERNA
    if pct >= 18: return "#fb923c"   # SLABA
    return "#f87171"                  # BREZ

# Same ramp as level_color, mapped to the .gp-pct-* badge classes (gp-forest
# row disc) instead of an inline colour.
def level_class(pct):
    if pct >= 55: return "gp-pct-hi"    # DOBRA / ODLIČNA
    if pct >= 35: return "gp-pct-mid"   # ZMERNA
    if pct >= 18: return "gp-pct-low"   # SLABA
    return "gp-pct-none"                 # BREZ

# Terrain accent colour + icon (also used for the terrain cards).
# Earthy palette for this page — greens/browns, no blue (vlazna reads as
# "moist riverbank" via a mossy teal-brown + the water-drop icon, not hue).
TERRAIN_STYLE = {
    "kisla":   ("#5a8f3f", "🌲"),
    "bazicna": ("#c17f3e", "⛰️"),
    "vlazna":  ("#5c8374", "💧"),
}


def gauge_svg(pct):
    """Radial progress ring for the headline index."""
    import math
    r = 54
    circ = 2 * math.pi * r
    off = circ * (1 - max(0, min(100, pct)) / 100)
    color = level_color(pct)
    return (f'<svg viewBox="0 0 128 128" class="gp-ring" aria-hidden="true">'
            f'<circle cx="64" cy="64" r="{r}" class="gp-ring-bg"/>'
            f'<circle cx="64" cy="64" r="{r}" class="gp-ring-fg" stroke="{color}" '
            f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{off:.1f}"/></svg>')


# ── Dnevna zgodovina hero indeksa (za delto "od včeraj" + 7-dnevni sparkline) ─
# Ta datoteka je edini vir za oboje — brez nje ni preteklih dni za primerjavo,
# zato se je piše tu (isti generator, ki jo bere), namesto v ločenem workflow
# koraku. En vnos na dan; ob večkratnem zagonu istega dne (ročno testiranje,
# ponovni build) se današnji vnos prepiše, ne podvoji.
INDEX_HISTORY_PATH = os.path.join(ROOT, "gobarska-napoved", "indeks-zgodovina.json")
INDEX_HISTORY_MAX_DAYS = 30


def update_index_history(pct):
    """Append today's index to the rolling history file (kept ≤30 days) and
    return the updated list, sorted oldest→newest. Best-effort: a missing or
    corrupt file just starts fresh — this is a nice-to-have trend, not a
    system of record."""
    try:
        with open(INDEX_HISTORY_PATH, encoding="utf-8") as f:
            hist = _json_mod.load(f)
    except (OSError, ValueError):
        hist = []
    today_iso = TODAY.isoformat()
    hist = [h for h in hist if h.get("date") != today_iso]
    hist.append({"date": today_iso, "index": pct})
    hist.sort(key=lambda h: h["date"])
    hist = hist[-INDEX_HISTORY_MAX_DAYS:]
    with open(INDEX_HISTORY_PATH, "w", encoding="utf-8") as f:
        _json_mod.dump(hist, f, ensure_ascii=False, indent=0)
    return hist


def hero_sparkline_svg(vals, color):
    """Same tiny auto-scaling polyline as the client-side sparklineSvg() in
    PAGE_JS (forest rows), server-rendered here because the free-tier hero
    has no client fetch to hang a JS version off of."""
    w, h, pad = 140, 32, 3
    n = len(vals)
    known = [v for v in vals if v is not None]
    if not known:
        return ""
    lo, hi = min(known), max(known)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    pts = []
    for i, v in enumerate(vals):
        if v is None:
            continue
        x = pad + (w - 2 * pad) * (0 if n == 1 else i / (n - 1))
        y = h - pad - (h - 2 * pad) * ((v - lo) / (hi - lo))
        pts.append(f"{x:.1f},{y:.1f}")
    return (f'<svg viewBox="0 0 {w} {h}" class="gp-spark" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def hero_trend_html(pct):
    """Delta vs. yesterday + 7-day sparkline under the hero level line.
    Empty string until there's at least 2 days of history — no fabricated
    trend on day one."""
    hist = update_index_history(pct)
    if len(hist) < 2:
        return ""
    yesterday_iso = (TODAY - _dt.timedelta(days=1)).isoformat()
    yesterday = next((h["index"] for h in hist if h["date"] == yesterday_iso), None)
    delta_html = ""
    if yesterday is not None:
        delta = pct - yesterday
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        delta_html = f'<span class="gp-hero-delta">{arrow} {delta:+d} od včeraj</span>'
    spark = hero_sparkline_svg([h["index"] for h in hist[-7:]], "#c17f3e")
    spark_html = f'<span class="gp-hero-spark">{spark}</span>' if spark else ""
    if not delta_html and not spark_html:
        return ""
    return f'<div class="gp-hero-trend">{delta_html}{spark_html}</div>'


# ── Pregled zmožnosti (mreža .gp-feat pod junaško kartico) ──────────────────
# Ikone so risane, ne emoji — emoji se med platformami razlikujejo in se ne
# dajo prebarvati v poudarek kartice (isti razlog kot pri _IC_* spodaj). Vsaka
# je 24×24, obris v stroke="currentColor" (kartica ga postavi na svoj --fa),
# ploskve pa so isti currentColor z nizko prekrivnostjo — dvobarvni videz brez
# druge barve. Vsaka mora ostati prepoznavna pri ~23 px.
_FI_GOZDOVI = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M7 3.5 11.4 11H2.6L7 3.5Z" fill="currentColor" fill-opacity=".22"/>'
    '<path d="M7 3.5 11.4 11H2.6L7 3.5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>'
    '<path d="M7 8.6 12.2 17H1.8L7 8.6Z" fill="currentColor" fill-opacity=".22" stroke="currentColor" '
    'stroke-width="1.5" stroke-linejoin="round"/>'
    '<path d="M7 17v3.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    '<path d="M17.4 6.2 21.8 14h-8.8l4.4-7.8Z" fill="currentColor" fill-opacity=".16" stroke="currentColor" '
    'stroke-width="1.5" stroke-linejoin="round"/>'
    '<path d="M17.4 14v6.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    '<path d="M2 20.5h20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity=".55"/></svg>')

_FI_7DNI = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="2.6" y="14.5" width="2.4" height="6" rx=".9" fill="currentColor" fill-opacity=".3" '
    'stroke="currentColor" stroke-width="1.3"/>'
    '<rect x="7" y="11" width="2.4" height="9.5" rx=".9" fill="currentColor" fill-opacity=".3" '
    'stroke="currentColor" stroke-width="1.3"/>'
    '<rect x="11.4" y="7.2" width="2.4" height="13.3" rx=".9" fill="currentColor" fill-opacity=".3" '
    'stroke="currentColor" stroke-width="1.3"/>'
    '<rect x="15.8" y="12.4" width="2.4" height="8.1" rx=".9" fill="currentColor" fill-opacity=".3" '
    'stroke="currentColor" stroke-width="1.3"/>'
    '<path d="M2.6 4.2c1.9 2.4 4.2 3.6 6.9 3.6 3.4 0 6.4-1.9 8.9-5.6" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" opacity=".75"/>'
    '<circle cx="20.6" cy="4.6" r="1.5" fill="currentColor"/></svg>')

_FI_AI = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="10.2" cy="10.2" r="7.2" fill="currentColor" fill-opacity=".14" stroke="currentColor" '
    'stroke-width="1.6"/>'
    '<path d="M5.3 10.6c0-2.7 2.2-4.8 4.9-4.8s4.9 2.1 4.9 4.8H5.3Z" fill="currentColor"/>'
    '<path d="M8.3 10.6v2.6a1.9 1.9 0 0 0 3.8 0v-2.6" stroke="currentColor" stroke-width="1.6" '
    'stroke-linejoin="round"/>'
    '<path d="m15.6 15.6 4.6 4.6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
    '<path d="M19 2.2l.65 1.85 1.85.65-1.85.65L19 7.2l-.65-1.85-1.85-.65 1.85-.65L19 2.2Z" '
    'fill="currentColor"/></svg>')

_FI_ZEMLJEVID = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M2.8 6.4 8.6 4v13.4l-5.8 2.4V6.4Z" fill="currentColor" fill-opacity=".2" stroke="currentColor" '
    'stroke-width="1.5" stroke-linejoin="round"/>'
    '<path d="M8.6 4l5.8 2.4v13.4L8.6 17.4V4Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>'
    '<path d="m14.4 6.4 5.8-2.4v6" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" opacity=".6"/>'
    '<path d="M18.4 12c1.8 0 3.2 1.4 3.2 3.2 0 2.2-3.2 5.6-3.2 5.6s-3.2-3.4-3.2-5.6c0-1.8 1.4-3.2 3.2-3.2Z" '
    'fill="currentColor" fill-opacity=".45" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>'
    '<circle cx="18.4" cy="15.3" r="1.1" fill="currentColor"/></svg>')

_FI_BAZA = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M7 6.4c0-2.4 2-4.3 4.4-4.3s4.4 1.9 4.4 4.3H7Z" fill="currentColor"/>'
    '<path d="M9.8 6.4v2.4a1.6 1.6 0 0 0 3.2 0V6.4" stroke="currentColor" stroke-width="1.6" '
    'stroke-linejoin="round"/>'
    '<path d="M11.4 13.2C9.8 11.7 7.4 11.1 3.6 11.6v9.2c3.8-.5 6.2.1 7.8 1.6v-9.2Z" fill="currentColor" '
    'fill-opacity=".22" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>'
    '<path d="M11.4 13.2c1.6-1.5 4-2.1 7.8-1.6v9.2c-3.8-.5-6.2.1-7.8 1.6v-9.2Z" stroke="currentColor" '
    'stroke-width="1.5" stroke-linejoin="round"/></svg>')

# Dvojnici: levo obris (užitna), desno polna (strupena), vmes črtkana meja —
# par, ki se ga da ločiti tudi pri 20 px. Klicaj v trikotniku se pri tej
# velikosti zlije v packo, zato ga tu ni; nevarnost pove rdeč poudarek kartice.
_FI_DVOJNICE = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M1.4 10.4c0-2.7 2.1-4.8 4.8-4.8s4.8 2.1 4.8 4.8H1.4Z" fill="currentColor" fill-opacity=".2" '
    'stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>'
    '<path d="M4.2 10.4v4.6a2 2 0 0 0 4 0v-4.6" stroke="currentColor" stroke-width="1.5" '
    'stroke-linejoin="round"/>'
    '<path d="M13 10.4c0-2.7 2.1-4.8 4.8-4.8s4.8 2.1 4.8 4.8H13Z" fill="currentColor"/>'
    '<path d="M15.8 10.4v4.6a2 2 0 0 0 4 0v-4.6" stroke="currentColor" stroke-width="1.5" '
    'stroke-linejoin="round"/>'
    '<path d="M12 3.4v17.2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" '
    'stroke-dasharray="2 2.6" opacity=".7"/></svg>')

_FI_KOLEDAR = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="3" y="5" width="18" height="16" rx="2.6" fill="currentColor" fill-opacity=".16" '
    'stroke="currentColor" stroke-width="1.6"/>'
    '<path d="M3 9.6h18" stroke="currentColor" stroke-width="1.5"/>'
    '<path d="M7.6 2.6v3.4M16.4 2.6v3.4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>'
    '<circle cx="7.6" cy="13.2" r="1.15" fill="currentColor" opacity=".5"/>'
    '<circle cx="12" cy="13.2" r="1.15" fill="currentColor"/>'
    '<circle cx="16.4" cy="13.2" r="1.15" fill="currentColor" opacity=".5"/>'
    '<circle cx="7.6" cy="17.4" r="1.15" fill="currentColor" opacity=".5"/>'
    '<circle cx="12" cy="17.4" r="1.15" fill="currentColor" opacity=".5"/></svg>')

_FI_TREND = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M3 20.2V4.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".55"/>'
    '<path d="M3 20.2h17.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".55"/>'
    '<path d="M5.4 16.8c2.4.4 4-1 5.4-4.2 1.3-3 2.8-4.6 4.6-4.8 1.7-.2 3.2 1.2 4.6 4.2v8.2H5.4v-3.4Z" '
    'fill="currentColor" fill-opacity=".18"/>'
    '<path d="M5.4 16.8c2.4.4 4-1 5.4-4.2 1.3-3 2.8-4.6 4.6-4.8 1.7-.2 3.2 1.2 4.6 4.2" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M5.4 13.4c2.2-.2 3.6-1.4 4.8-3.6" stroke="currentColor" stroke-width="1.4" '
    'stroke-linecap="round" stroke-dasharray="2 2.4" opacity=".7"/>'
    '<circle cx="20" cy="12" r="1.6" fill="currentColor"/></svg>')

_FI_DNEVNIK = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M5.4 3.6h11.2a1.8 1.8 0 0 1 1.8 1.8v15a1.8 1.8 0 0 1-1.8 1.8H5.4V3.6Z" fill="currentColor" '
    'fill-opacity=".16" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
    '<path d="M5.4 3.6a2 2 0 0 0-2 2v13.2a2 2 0 0 0 2 2" stroke="currentColor" stroke-width="1.6" '
    'stroke-linejoin="round"/>'
    '<path d="M8.6 8.2h6.4M8.6 11.6h6.4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" '
    'opacity=".65"/>'
    '<path d="M14.6 14.4c1.6 0 2.9 1.3 2.9 2.9 0 2-2.9 5-2.9 5s-2.9-3-2.9-5c0-1.6 1.3-2.9 2.9-2.9Z" '
    'fill="currentColor" fill-opacity=".5" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>'
    '<circle cx="14.6" cy="17.2" r="1" fill="currentColor"/></svg>')


_FI_TERENI = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M2.6 7.6c2.4-1.4 4.6-2.1 6.6-2.1 2.6 0 5 .8 7.2 2.4 1.6 1.1 3.2 1.7 4.8 1.7v3.2c-1.6 0-3.2-.6-4.8-1.7'
    '-2.2-1.6-4.6-2.4-7.2-2.4-2 0-4.2.7-6.6 2.1V7.6Z" fill="currentColor" fill-opacity=".45"/>'
    '<path d="M2.6 7.6c2.4-1.4 4.6-2.1 6.6-2.1 2.6 0 5 .8 7.2 2.4 1.6 1.1 3.2 1.7 4.8 1.7" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M2.6 13.4c2.4-1.4 4.6-2.1 6.6-2.1 2.6 0 5 .8 7.2 2.4 1.6 1.1 3.2 1.7 4.8 1.7" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity=".75"/>'
    '<path d="M2.6 19.2c2.4-1.4 4.6-2.1 6.6-2.1 2.6 0 5 .8 7.2 2.4 1.6 1.1 3.2 1.7 4.8 1.7" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity=".5"/></svg>')

_FI_NASVETI = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="4" y="2.8" width="16" height="18.4" rx="2.6" fill="currentColor" fill-opacity=".14" '
    'stroke="currentColor" stroke-width="1.6"/>'
    '<path d="m7.4 8 1.5 1.5 2.6-2.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
    'stroke-linejoin="round"/>'
    '<path d="m7.4 13.4 1.5 1.5 2.6-2.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
    'stroke-linejoin="round"/>'
    '<path d="M13.6 8.2h3.2M13.6 13.6h3.2M7.4 18.4h9.4" stroke="currentColor" stroke-width="1.5" '
    'stroke-linecap="round" opacity=".7"/></svg>')

_FI_FAQ = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M3 6.4a2.6 2.6 0 0 1 2.6-2.6h12.8A2.6 2.6 0 0 1 21 6.4v8a2.6 2.6 0 0 1-2.6 2.6H9.6L5 20.8V17h-.4'
    'A1.6 1.6 0 0 1 3 15.4V6.4Z" fill="currentColor" fill-opacity=".16" stroke="currentColor" stroke-width="1.6" '
    'stroke-linejoin="round"/>'
    '<path d="M9.7 8.6a2.3 2.3 0 0 1 4.5.7c0 1.5-2.2 1.8-2.2 3.2" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round"/>'
    '<circle cx="12" cy="14.8" r="1.05" fill="currentColor"/></svg>')

_FI_METODOLOGIJA = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M4 16.4a8 8 0 0 1 16 0" fill="currentColor" fill-opacity=".14"/>'
    '<path d="M4 16.4a8 8 0 0 1 16 0" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    '<path d="M12 16.4 8.7 11.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'
    '<circle cx="12" cy="16.4" r="1.2" fill="currentColor"/>'
    '<path d="M4 16.4h1.5M18.5 16.4H20M6.2 10.6l1.1 1M17.8 10.6l-1.1 1M12 6.8v1.6" stroke="currentColor" '
    'stroke-width="1.3" stroke-linecap="round" opacity=".6"/></svg>')

_FI_ALARM = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 3.6c-3 0-5.1 2.3-5.1 5.5v2.9l-1.7 3.2c-.3.6.1 1.3.8 1.3h12'
    'c.7 0 1.1-.7.8-1.3l-1.7-3.2V9.1c0-3.2-2.1-5.5-5.1-5.5Z" fill="currentColor" fill-opacity=".16" '
    'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
    '<path d="M9.6 18.9a2.4 2.4 0 0 0 4.8 0" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    '</svg>')


# Kartice pregleda zmožnosti, grupirane v 4 skupine (glej CLAUDE.md "Glavna
# stran gobarja je pristajalna, ne zbirna" — skupinjenje je dokumentirano
# tam; nova zmožnost gre pod ustrezno skupino ali v GOBE_MORE, ne nazaj v
# ploski seznam). Naslovi in napovedniki so predloge s {…} mesti, ki jih
# napolnijo števila iz istih podatkov, iz katerih nastanejo strani — na roko
# pisana zastarijo ob vsaki razširitvi baze (kartica je nekoč oglaševala
# 51 vrst, ko jih je bilo v bazi že 300).
#
# Poudarki (--fa) so zavestno razporejeni tako, da sosednji kartici v isti
# skupini nista v istem odtenku; stran je sicer zemeljska (zelena/rjava), a
# same zelene kartice se ne bi ločile med sabo.
GOBE_CATEGORIES = [
    # (ključ, emoji, naslov skupine, [(href, ikona, poudarek, naslov, napovednik, oznaka), ...])
    ("napoved", "🍄", "Napoved", [
        ("/gobarska-napoved/danes/", _FI_GOZDOVI, "#34d399", "Danes po gozdovih",
         "Indeks za {spots} nabiralnih območij doline, vsak dan znova.", None),
        ("#premium", _FI_7DNI, "#4d9ff8", "Napoved po vrstah, 7 dni",
         "Za vsak dan in vsako območje, z razlago po komponentah.", "PREMIUM"),
    ]),
    ("kje", "🗺", "Kje nabirati", [
        ("/gobarska-napoved/zemljevid/", _FI_ZEMLJEVID, "#22d3ee", "Zemljevid območij",
         "Vseh {spots} nabiralnih območij na karti doline.", None),
        ("/gobarska-napoved/tereni/", _FI_TERENI, "#c1874e", "Geološki tereni",
         "Zakaj ista vrsta ni enako verjetna v vsakem gozdu.", None),
    ]),
    ("prepoznaj", "🔍", "Prepoznaj gobo", [
        ("#premium", _FI_AI, "#a78bfa", "AI prepoznava gobe",
         "Naložiš fotografijo, dobiš najverjetnejšo vrsto in opozorilo.", "PREMIUM"),
        ("/gobarska-napoved/baza-vrst/", _FI_BAZA, "#f59e0b", "Baza {species} vrst",
         "Užitnost, sezona, opis in fotografija za vsako vrsto.", None),
        ("/gobarska-napoved/dvojnice/", _FI_DVOJNICE, "#f87171", "Nevarne dvojnice",
         "{pairs} parov: užitna vrsta ob tisti, s katero jo zamenjajo.", None),
    ]),
    ("moje", "♡", "Moje gobe", [
        ("#premium", _FI_ALARM, "#fbbf24", "Moji alarmi",
         "E-mail, ko pogoji za tvojo vrsto ali območje postanejo ugodni.", "PREMIUM"),
        ("/gobarska-napoved/dnevnik/", _FI_DNEVNIK, "#2dd4bf", "Gobarjev dnevnik",
         "Najdbe z lokacijo in fotografijo, shranjene le v brskalniku.", None),
    ]),
]

# Manj pogosto obiskane podstrani — ena vrstica povezav pod skupinami,
# namesto lastnih kartic (bile so del istega ploskega seznama kot zgoraj).
GOBE_MORE = [
    ("/gobarska-napoved/koledar/", "Koledar"),
    ("/gobarska-napoved/trend/", "Trend"),
    ("/gobarska-napoved/metodologija/", "Metodologija"),
    ("/gobarska-napoved/nasveti/", "Nasveti"),
    ("#faq", "FAQ"),
]


def _rgba(hex_color, alpha):
    """#rrggbb → rgba(r,g,b,alpha) — mehka podlaga ikone iz istega poudarka."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def feature_cards_html(counts):
    """Kartice »kaj vse najdeš tukaj«, grupirane v 4 skupine (GOBE_CATEGORIES)
    + ena vrstica povezav za manj pogosto obiskane podstrani (GOBE_MORE).
    Glej .gp-feat / .gp-feat-group v slogu strani."""
    groups = []
    for key, emoji, label, items in GOBE_CATEGORIES:
        cards = []
        for href, icon, accent, title, sub, badge in items:
            badge_html = f'<span class="gp-feat-badge">{badge}</span>' if badge else ""
            cards.append(
                f'    <a class="gp-feat-card" href="{href}" '
                f'style="--fa:{accent};--fa-soft:{_rgba(accent, ".16")}">{badge_html}'
                f'<span class="gp-feat-ic" aria-hidden="true">{icon}</span>'
                f'<span class="gp-feat-title">{_esc(title.format(**counts))}</span>'
                f'<span class="gp-feat-sub">{_esc(sub.format(**counts))}</span></a>'
            )
        groups.append(
            f'  <div class="gp-feat-group" data-cat="{key}">\n'
            f'    <h3 class="gp-feat-group-title">{emoji} {_esc(label)}</h3>\n'
            f'    <div class="gp-feat">\n' + "\n".join(cards) + '\n    </div>\n'
            '  </div>')
    more_html = " · ".join(f'<a href="{href}">{_esc(label)}</a>' for href, label in GOBE_MORE)
    return ('  <h2 class="gp-h2" id="zmoznosti">🧭 Kaj vse najdeš tukaj</h2>\n'
            '  <p class="archive-intro">Napoved je le začetek — vsaka kartica pelje naravnost na svojo '
            'stran ali razdelek.</p>\n' + "\n".join(groups) +
            f'\n  <p class="gp-feat-more">Več: {more_html}</p>')


# Custom two-tone (duotone) SVG icon set for the bottom nav — replaces the
# emoji glyphs, which render inconsistently across platforms/fonts and can't
# be recoloured for the active/inactive tab state. Each icon: an outline in
# stroke="currentColor" (so it inherits the same colour swap the text label
# already gets via .active) plus a fixed var(--cyan) accent fill — one
# consistent two-colour look across the whole set. 24x24 viewBox throughout.
_IC_NAPOVED = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M4 11C4 6.5 7.6 3 12 3s8 3.5 8 8H4Z" fill="var(--cyan)" fill-opacity=".35"/>'
    '<path d="M4 11C4 6.5 7.6 3 12 3s8 3.5 8 8" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M9 11v5a3 3 0 0 0 6 0v-5" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    '<line x1="4" y1="11" x2="20" y2="11" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>')
_IC_ZEMLJEVID = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M3 6.5 9 4l6 2.5 6-2.5v13L15 19.5 9 17l-6 2.5v-13Z" fill="var(--cyan)" fill-opacity=".3" '
    'stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>'
    '<path d="M9 4v13M15 6.5v13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>')
_IC_AI = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="10.5" cy="10.5" r="6" fill="currentColor" fill-opacity=".2"/>'
    '<circle cx="10.5" cy="10.5" r="6" stroke="currentColor" stroke-width="1.8"/>'
    '<path d="m15 15 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>')
_IC_BAZA = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 5.5C10.3 4 7.8 3.5 4 4v14c3.8-.5 6.3 0 8 1.5V5.5Z" fill="var(--cyan)" fill-opacity=".3" '
    'stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>'
    '<path d="M12 5.5C13.7 4 16.2 3.5 20 4v14c-3.8-.5-6.3 0-8 1.5V5.5Z" fill="var(--cyan)" fill-opacity=".15" '
    'stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>')
_IC_DVOJNICE = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 3.5 21.5 20h-19L12 3.5Z" fill="var(--cyan)" fill-opacity=".3" '
    'stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>'
    '<line x1="12" y1="10" x2="12" y2="14.5" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>'
    '<circle cx="12" cy="17.2" r="1" fill="currentColor"/></svg>')

# App-style bottom nav (mobile only, see .gp-bottomnav) — 4 destinations max,
# thumb-reachable, mirroring what the eventual Android app's bottom bar will
# show. Sorodna, a ločena od mreže .gp-feat na glavni strani.
BOTTOM_NAV = [
    ("",           _IC_NAPOVED,    "Napoved",   None),
    ("zemljevid",  _IC_ZEMLJEVID,  "Zemljevid", None),
    ("ai",         _IC_AI,         "Prepoznaj", "/gobarska-napoved/#premium"),
    ("baza-vrst",  _IC_BAZA,       "Baza vrst", None),
    ("dvojnice",   _IC_DVOJNICE,   "Dvojnice",  None),
]


def bottom_nav_html(active_slug):
    rows = []
    for slug, ic, label, href_override in BOTTOM_NAV:
        href = href_override or (f"/gobarska-napoved/{slug}/" if slug else "/gobarska-napoved/")
        classes = ([] if slug != "ai" else ["hl"]) + (["active"] if slug == active_slug else [])
        cls = f' class="{" ".join(classes)}"' if classes else ""
        rows.append(f'    <a href="{href}"{cls}><span class="ic">{ic}</span>{_esc(label)}</a>')
    return '  <nav class="gp-bottomnav" aria-label="Glavna navigacija">\n' + "\n".join(rows) + "\n  </nav>"


def top_bar_html(title, back_href):
    """Mobile Top App Bar (Material 3 "small" variant) — new, page-scoped
    chrome (see .gp-topbar), not a rework of the shared .site-head. Hub page
    gets a brand mark instead of a back arrow; the 5 subpages get a 1-tap
    way back up to the hub."""
    left = (f'<a class="gp-topbar-back" href="{back_href}" aria-label="Nazaj">‹</a>' if back_href
            else '<span class="gp-topbar-back gp-topbar-brand" aria-hidden="true">🍄</span>')
    return (f'  <div class="gp-topbar">{left}'
            f'<span class="gp-topbar-title">{_esc(title)}</span>'
            f'<a class="gp-topbar-action" href="/gobarska-napoved/#premium" aria-label="AI prepoznava gobe">🔍</a></div>')


def subpage_shell(slug, title, desc, crumb_label, inner_html, extra_js="", parent=None):
    """Shared chrome for the gobarska-napoved/<slug>/ reference subpages —
    same header/footer/brand/back-link as the main page, own URL + meta.

    `parent` je (naslov, pot, tožilnik) vmesne strani; strani po kategorijah
    pod /baza-vrst/ so eno raven globlje in morajo to pokazati v drobtinicah in
    v gumbu nazaj, sicer obiskovalca vrne dve ravni previsoko. Tretji element
    je ime v tožilniku za besedilo gumba ("nazaj na bazo vrst", ne "na baza
    vrst") — sklona iz naslova ni mogoče izpeljati."""
    url = f"/gobarska-napoved/{slug}/"
    crumbs = [("Meteorec", "/"), ("Gobarska napoved", "/gobarska-napoved/")]
    if parent:
        crumbs.append(parent[:2])
    crumbs.append((crumb_label, None))
    back_href, back_label = (parent[1], parent[2]) if parent else ("/gobarska-napoved/", "gobarsko napoved")
    schema = "\n".join([
        seo.webpage_schema(url, title, desc),
        seo.crumbs_schema(crumbs),
    ])
    head_extras = schema + "\n" + PAGE_CSS
    body = f'''{BRAND_SWAP}
{top_bar_html(crumb_label, back_href)}
{seo.crumbs_html(crumbs)}
{seo.stn_badge()}
  <h1 class="page-title">{title}</h1>
{inner_html}
  <a class="back-link" href="{back_href}">← Nazaj na {_esc(back_label)}</a>
{bottom_nav_html(slug)}
{extra_js}'''
    html = seo.page_shell(f"{title} — Gobarska napoved", desc, url, head_extras, body,
                           og_image=f"{seo.SITE}/og/gobarska-napoved.jpg")
    seo.write_page(f"gobarska-napoved/{slug}/index.html", html, force=True)
    return url


def build_koledar_page(cal_data, month):
    """Chip row of 12 months + one card panel each (current month open by
    default) — replaces the old 12-row static table with a tap-to-glance
    format, consistent with the day-chips pattern used in the premium
    forecast (locDetailHtml in PAGE_JS)."""
    chips = "\n".join(
        f'    <button type="button" class="gp-chip{" active" if d["current"] else ""}" '
        f'data-m="{d["m"]}">{d["name"]}</button>'
        for d in cal_data)
    panels = "\n".join(
        f'  <div class="gp-cal-panel{" active" if d["current"] else ""}" data-m="{d["m"]}">' + (
            '<div class="gp-cal-sp">' + "".join(
                f'<span class="gp-cal-tag">🍄 {_esc(n)}</span>' for n in d["species"]) + '</div>'
            if d["species"] else
            '<p class="gp-cal-empty">Nobena od spremljanih vrst ni v sezoni ta mesec.</p>'
        ) + '</div>'
        for d in cal_data)
    cal_js = '''<script>(function(){
  var chips=document.querySelectorAll(".gp-cal-chips .gp-chip");
  var panels=document.querySelectorAll(".gp-cal-panel");
  chips.forEach(function(c){
    c.addEventListener("click",function(){
      chips.forEach(function(x){x.classList.remove("active");});
      panels.forEach(function(p){p.classList.remove("active");});
      c.classList.add("active");
      var p=document.querySelector('.gp-cal-panel[data-m="'+c.dataset.m+'"]');
      if(p)p.classList.add("active");
      c.scrollIntoView({inline:"center",block:"nearest",behavior:"smooth"});
    });
  });
  var active=document.querySelector(".gp-cal-chips .gp-chip.active");
  if(active)active.scrollIntoView({inline:"center",block:"nearest"});
})();</script>'''
    body = ('''  <figure class="gp-banner">
    <img src="/gobarska-napoved/img/foto/gozd-mah-banner.jpg" loading="lazy" width="1400" height="600"
      alt="Dve gobi v mahu, avtorski makro posnetek">
    <figcaption>📷 Avtorski makro posnetek — jesenska rast v mahu</figcaption>
  </figure>
'''
            '  <p class="post-meta">Katere užitne in pogojno užitne vrste so ta mesec v sezoni (iz lokalne baze). '
            'Izberi mesec.</p>\n'
            '  <div class="gp-chip-row gp-cal-chips">\n' + chips + '\n  </div>\n'
            + panels)
    return subpage_shell(
        "koledar", "Koledar gobarske sezone po mesecih",
        "Kateri užitni gobi so po mesecih v sezoni v Zgornji Savinjski dolini — pregled po lokalni bazi vrst.",
        "Koledar", body, extra_js=cal_js)


def build_trend_page():
    body = ('''  <figure class="gp-banner">
    <img src="/gobarska-napoved/img/foto/sluzavke-banner.jpg" loading="lazy" width="1400" height="600"
      alt="Makro posnetek sluzavk na odmrlem lesu">
    <figcaption>📷 Avtorski makro posnetek — sluzavke (Myxomycetes) na odmrli veji</figcaption>
  </figure>
'''
            '  <p class="post-meta">Mesečno povprečje gobarskega indeksa za Rečico ob Savinji, izračunano nazaj '
            '(backtest) z zgodovinskimi vremenskimi podatki (ERA5-Land) — zadnjih do 5 let. Letošnja sezona je '
            'poudarjena. Približek: uporablja podnebni arhiv namesto postajnih meritev, zato se lahko rahlo '
            'razlikuje od dnevne napovedi.</p>\n'
            '  <div id="gp-trend" class="gp-trend-wrap">\n    <div class="gp-msg">Nalagam …</div>\n  </div>')
    return subpage_shell(
        "trend", "Sezonski trend gobarskega indeksa",
        "Letošnja gobarska sezona v primerjavi s preteklimi 5 leti za Rečico ob Savinji — backtest iz ERA5-Land arhiva.",
        "Sezonski trend", body, extra_js=TREND_JS)


BAZA_INTRO = (
    '''  <figure class="gp-banner">
    <img src="/gobarska-napoved/img/foto/megla-jutro-banner.jpg" loading="lazy" width="1400" height="600"
      alt="Jutranja megla nad gozdovi Zgornje Savinjske doline">
    <figcaption>📷 Avtorski posnetek — jutranja inverzija nad gozdovi doline</figcaption>
  </figure>
'''
    '  <p class="post-meta">Referenčni pregled gob doline z oznako užitnosti in ključno razliko do nevarnih '
    'dvojnic. <strong>Nikoli ne uživaj gobe, ki je ne poznaš 100 %.</strong></p>\n'
    '  <p class="post-meta">Jedro baze je zbrano na terenu v Zgornji Savinjski dolini. Vrste z oznako '
    '<em>◌ ni terensko preverjeno</em> so dodane iz razširjenega seznama — izbrane so po dejanskih '
    'zapisih o pojavljanju v Sloveniji (GBIF), njihovi opisi pa so povzeti po literaturi in v dolini '
    'niso preverjeni. Gobarski indeks te vrste praviloma ne dobijo.</p>\n')


def build_baza_vrst_pages(species, vrste_credits_html):
    """Celotna baza na /baza-vrst/ in ena stran na skupino užitnosti pod njo.
    Vrne število zgrajenih strani."""
    made = 0
    for path, key, label, title_t, desc_t in BAZA_CATS:
        subset = ([s for s in species
                   if EDIB_FILTER.get((s.get("edibility") or "").lower().strip()) == key]
                  if key else list(species))
        if not subset:
            continue
        slug = "baza-vrst" + (f"/{path}" if path else "")
        title = title_t.format(n=len(subset))
        # Tabela virov fotografij spada na celotno bazo; na strani skupine bi
        # navajala tudi avtorje slik, ki jih ta stran ne prikaže.
        body = BAZA_INTRO + species_section_html(subset, species, current=path) + \
            ("\n" + vrste_credits_html if not path else "")
        subpage_shell(slug, title, desc_t.format(n=len(subset)),
                      "Baza vrst" if not path else label, body, extra_js=SP_JS,
                      parent=None if not path else
                      ("Baza vrst", "/gobarska-napoved/baza-vrst/", "bazo vrst"))
        made += 1
    return made


def build_dvojnice_page(vs_html, vs_count, credits_html):
    body = ('''  <figure class="gp-photo-card">
    <img src="/gobarska-napoved/img/foto/sluzavka-portret.jpg" loading="lazy" width="640" height="853"
      alt="Avtorski makro posnetek sluzavke v gozdu">
    <figcaption>📷 Avtorski makro posnetek — tudi navidez podobne gobe znajo biti povsem različne vrste</figcaption>
  </figure>
'''
            '  <p class="post-meta">Užitna vrsta ob vrsti, s katero jo je mogoče zamenjati, s ključno razliko za '
            'varno ločevanje. Dvojnica je pri večini parov strupena ali neužitna, ponekod pa prav tako užitna — '
            'oznaka pri njej pove, za kaj gre. <strong>Ob dvomu gobe nikoli ne uživaj.</strong></p>\n'
            + vs_html + "\n" + credits_html)
    return subpage_shell(
        "dvojnice", "Nevarne dvojnice gob — primerjava s fotografijami",
        f"{vs_count} primerjav užitnih vrst z nevarnimi dvojnicami, s fotografijami in ključno razliko za varno "
        "ločevanje.",
        "Nevarne dvojnice", body)


# ── Razdelki, ki so prej stali na glavni strani ─────────────────────────────
# Glavna stran je pristajalna: junaška kartica z indeksom, mreža zmožnosti,
# premium in cenik ter pogosta vprašanja. Vse ostalo ima svojo stran in se do
# nje pride prek kartice — prej je bilo vse na kupu, tudi za obiskovalca, ki
# je prišel samo pogledat, ali se danes splača v gozd.


def build_danes_page(forests_html, free):
    """Dnevni indeks po nabiralnih območjih — brezplačno jedro napovedi.
    Ker ta stran nosi vsakodnevno sveže število, je v sitemapu daily."""
    body = ('  <p class="post-meta">Gobarski indeks za nabiralna območja Zgornje Savinjske doline za '
            f'{TODAY.isoformat()}. Izračunan je iz vlage in temperature tal, kumulativnih padavin '
            '(lokalno iz postaje IREICA1), zračne vlage in nočne ohladitve — po vrstah in po geologiji '
            'terena.</p>\n'
            f'  <p class="archive-intro">Danes v Rečici ob Savinji: <strong>{free["index"]} % · '
            f'{_esc(free["level"])}</strong>. Indeks je ocena ugodnosti pogojev za rast, ne obljuba '
            'najdbe — gozd ima vedno zadnjo besedo.</p>\n'
            + forests_html)
    return subpage_shell(
        "danes", "Danes po gozdovih — gobarski indeks po območjih",
        "Gobarski indeks po nabiralnih območjih Zgornje Savinjske doline za današnji dan — Golte, Menina, "
        "Smrekovec, Dleskovška planota in okolica.",
        "Danes po gozdovih", body)


def build_tereni_page(terrain_html):
    body = ('  <p class="post-meta">Podlaga odloča, kaj raste: model za vsako vrsto upošteva afiniteto do '
            'terena, zato ista vrsta isti dan ni enako verjetna povsod po dolini.</p>\n'
            + terrain_html + '\n'
            '  <p class="archive-intro">Izjema so lesne vrste (ostrigar, panjevka, uhljevka): rastejo na lesu '
            'nad tlemi, zato zanje geologija podlage ne odloča.</p>')
    return subpage_shell(
        "tereni", "Geološki tereni Zgornje Savinjske doline",
        "Kislo vulkansko pogorje, karbonatni masivi in rečni logi — katera podlaga katerim gobam ustreza in "
        "zakaj se indeks med gozdovi razlikuje.",
        "Geološki tereni", body)


NASVETI_HTML = '''  <p class="post-meta">Kratek povzetek pravil in navad, ki jih velja poznati, preden greš
  po gobe v Zgornji Savinjski dolini.</p>
  <div class="card" style="margin:1rem 0">
    <div style="font-size:.9rem;color:var(--muted);line-height:1.9">
      ⚖️ Do <b>2 kg gob na osebo na dan</b> (Uredba o varstvu samoniklih gliv).<br>
      🧺 Gobe nosi v zračni košari, ne v vrečki — trosi se tako raznašajo.<br>
      🔪 Gobo izvij ali odreži pri dnu in mesto rahlo prekrij.<br>
      ☠️ <b>Nikoli ne uživaj gobe, ki je ne poznaš 100 %.</b> Ob dvomu vprašaj gobarsko društvo ali mikologa.<br>
      🔒 Nekatera območja doline (npr. Logarska dolina) so zavarovana — pred nabiranjem preveri veljavne
      omejitve na kraju samem, saj zavarovan status sam po sebi še ne pomeni splošne prepovedi nabiranja.
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.9rem">
      <a href="https://www.gobe.si/" target="_blank" rel="noopener" class="mtn-avk-link">🍄 Gobe.si</a>
      <a href="https://www.gobarskazveza.si/" target="_blank" rel="noopener" class="mtn-avk-link">🇸🇮 Gobarska zveza Slovenije</a>
      <a href="https://meteo.arso.gov.si/met/sl/agromet/" target="_blank" rel="noopener" class="mtn-avk-link">🌱 ARSO — agrometeorologija</a>
    </div>
  </div>
  <p class="archive-intro">Ob sumu zastrupitve pokliči <b>112</b>, za posvet o zaužiti gobi pa Center za
  zastrupitve UKC Ljubljana, <a href="tel:+38615225283">(01) 522 52 83</a> (24 ur). Vzemi s seboj vzorec
  gobe — pomaga pri določitvi vrste.</p>
  <p class="archive-intro">Preden gobo daš v košaro, preveri še <a href="/gobarska-napoved/dvojnice/">nevarne
  dvojnice</a> in njen zapis v <a href="/gobarska-napoved/baza-vrst/">bazi vrst</a>.</p>'''


def build_nasveti_page():
    return subpage_shell(
        "nasveti", "Nabiranje gob — nasveti in pravila",
        "Koliko gob smeš nabrati na dan, kje so zavarovana območja, kako gobe nositi in kam po pomoč ob "
        "sumu zastrupitve.",
        "Nasveti in pravila", NASVETI_HTML)


METODOLOGIJA_HTML = '''  <p class="post-meta">Kaj gobarski indeks pomeni, iz česa je izračunan in kje so njegove meje —
  brez razkrivanja same formule.</p>

  <h2 class="gp-h2">Kaj pomeni indeks 0–100</h2>
  <p class="archive-intro">Gobarski indeks je <strong>ocena ugodnosti vremenskih in talnih pogojev</strong> za
  rast posamezne vrste — ne verjetnost, da boš to vrsto danes res našel. Gozd ima vedno zadnjo besedo: visok
  indeks pomeni, da so pogoji ugodni, ne da je goba zajamčena.</p>

  <h2 class="gp-h2">Vhodni podatki</h2>
  <p class="archive-intro">Model za vsako lokacijo in vsako vrsto upošteva:</p>
  <ul class="archive-intro">
    <li>lokalne padavine iz postaje IREICA1 (Rečica ob Savinji) in Open-Meteo za ostala območja doline,</li>
    <li>temperaturo in vlago tal,</li>
    <li>zračno vlago,</li>
    <li>nočno ohladitev,</li>
    <li>rastni zamik vrste (glej spodaj),</li>
    <li>geologijo območja (kisla, bazična ali vlažna podlaga — razen pri lesnih vrstah, glej spodaj).</li>
  </ul>

  <h2 class="gp-h2">Rastni zamik po ekoloških skupinah</h2>
  <p class="archive-intro">Različne skupine gliv se na isti dež ne odzovejo enako hitro. Razkrojevalke stelje in
  travinja (kukmaki, tintnice, marela) tvorijo trosnjake nekaj dni po plohi, lesne razkrojevalke (ostrigar,
  panjevka, uhljevka) nekoliko pozneje, mikorizne vrste (gobani, lisičke, golobice) pa šele teden in pol do dva.
  Padavinsko okno je zato pri vsaki vrsti zamaknjeno za njen rastni zamik: dež, ki je padel včeraj, jurčku danes
  indeksa ne dvigne, kukmaku pa ga lahko.</p>

  <h2 class="gp-h2">Geologija</h2>
  <p class="archive-intro">Kislo vulkansko pogorje (npr. Smrekovec) ustreza jurčkom in žametastemu gobanu,
  karbonatni masivi (npr. Golte, Menina) pa marelam in poletnemu gobanu — zato ista vrsta isti dan ni enako
  verjetna povsod. Izjema so lesne vrste: rastejo na lesu nad tlemi, zato zanje geologija podlage ne odloča.</p>

  <h2 class="gp-h2">Omejitve modela</h2>
  <p class="archive-intro">Indeks ne zazna: mikroklime posameznega gozdnega roba, dejanske sestave in starosti
  gozda, pretekle pobiralne aktivnosti na območju, ali dejanske gobe same. Napovedne točke so <strong>širša
  območja</strong>, ne točne najdbe.</p>

  <h2 class="gp-h2">Viri podatkov</h2>
  <p class="archive-intro"><a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a> za
  vremensko napoved vseh območij, lastna postaja IREICA1 v Rečici ob Savinji za lokalne meritve padavin,
  temperature in vlage. Model se uči izključno iz teh dveh virov in izmerjene zgodovine postaje — brez notranjih
  meritev hiše (glej <a href="/zasebnost.html">politiko zasebnosti</a>).</p>

  <p class="archive-intro" style="color:var(--muted);font-size:.85rem">Zadnja večja sprememba modela:
  gobarski indeks v1.3 (avgust 2026) — glej <a href="/gobarska-napoved/dnevnik/">dnevnik</a> in
  <a href="/gobarska-napoved/trend/">sezonski trend</a> za preteklo delovanje.</p>'''


def build_metodologija_page():
    return subpage_shell(
        "metodologija", "Kako deluje gobarski indeks",
        "Kaj pomeni gobarski indeks 0–100, kateri podatki ga sestavljajo, kako model upošteva rastni zamik "
        "vrst in geologijo terena — ter kje so njegove meje.",
        "Kako deluje model", METODOLOGIJA_HTML)


def build_dnevnik_page(diary_html):
    body = ('  <p class="post-meta">Zabeleži najdbo z datumom, vrsto, lokacijo in fotografijo. Vse ostane v '
            'tvojem brskalniku; naročniki lahko dnevnik sinhronizirajo med napravami.</p>\n'
            + diary_html)
    return subpage_shell(
        "dnevnik", "Gobarjev dnevnik",
        "Zasebni dnevnik gobarskih najdb — datum, vrsta, lokacija in fotografija, shranjeni v tvojem "
        "brskalniku.",
        "Gobarjev dnevnik", body, extra_js=DIARY_JS)


# ZGS (Zavod za gozdove Slovenije) javna WFS storitev — sloj "sestoji" (gozdni
# sestoji) nosi dejansko drevesno sestavo vsakega sestoja kot delež lesne
# zaloge po skupinah drevesnih vrst (polja lzskdv11..lzskdv80, glej uradni
# šifrant ZGS "Priloge in šifranti" k Navodilom za izdelavo GGN). Uporabljeno
# samo za prikaz — brez ključa, brez omejitev (Fees/AccessConstraints: NONE).
ZGS_WFS_URL = "https://prostor.zgs.gov.si/geoserver/wfs"
ZGS_SPECIES_GROUPS = {
    "lzskdv11": ("smreka", "#2f6b3a"),
    "lzskdv21": ("jelka", "#1f7a5c"),
    "lzskdv30": ("bor", "#d97b29"),
    "lzskdv34": ("macesen", "#c9a227"),
    "lzskdv39": ("drugi iglavci", "#6b8f71"),
    "lzskdv41": ("bukev", "#a13d2c"),
    "lzskdv50": ("hrast", "#7a5230"),
    "lzskdv60": ("plemeniti listavci", "#4a7fc1"),
    "lzskdv70": ("drugi trdi listavci", "#8a6bbf"),
    "lzskdv80": ("mehki listavci", "#5fb0c9"),
}


def _simplify_ring(ring, max_points=9):
    """Decimate a polygon ring to at most max_points vertices and round
    coordinates — keeps the embedded page size sane for what is purely a
    visual composition layer, not a survey-grade boundary."""
    step = max(1, len(ring) // max_points)
    pts = ring[::step]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return [[round(lat, 4), round(lon, 4)] for lon, lat in pts]


def fetch_sestoji_near(lat, lon, delta=0.012, max_count=80, keep=25):
    """Fetch nearby ZGS forest-stand polygons and reduce each to its
    dominant tree-species group (by share of standing timber volume), for
    a real-composition overlay on the location map. Keeps only the largest
    `keep` stands (by area) simplified to a handful of vertices each — a
    public, SEO-relevant page, so embedded weight is kept in check.
    Best-effort: any network/parsing failure yields an empty list rather
    than failing the whole site build — this layer is a bonus, not
    load-bearing."""
    bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta},urn:ogc:def:crs:CRS:84"
    params = urllib.parse.urlencode({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeName": "pregledovalnik:sestoji", "outputFormat": "application/json",
        "srsName": "urn:ogc:def:crs:EPSG::4326",
        "bbox": bbox, "count": str(max_count),
    })
    url = f"{ZGS_WFS_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = _json_mod.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        print(f"  ⚠ ZGS sestoji nedosegljivi ({lat},{lon}): {e}", file=sys.stderr)
        return []

    out = []
    for feat in data.get("features", []):
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        best_key, best_val = None, 0.0
        for key in ZGS_SPECIES_GROUPS:
            try:
                val = float(props.get(key) or 0)
            except (TypeError, ValueError):
                val = 0.0
            if val > best_val:
                best_key, best_val = key, val
        if not best_key:
            continue
        name, color = ZGS_SPECIES_GROUPS[best_key]
        coords = geom.get("coordinates") or []
        if geom.get("type") == "Polygon" and coords:
            ring = coords[0]
        elif geom.get("type") == "MultiPolygon" and coords and coords[0]:
            ring = coords[0][0]
        else:
            continue
        if len(ring) < 4:
            continue
        try:
            area = float(props.get("povrsina") or 0)
        except (TypeError, ValueError):
            area = 0.0
        out.append({"sp": name, "c": color, "pts": _simplify_ring(ring), "_a": area})
    out.sort(key=lambda s: s["_a"], reverse=True)
    for s in out:
        del s["_a"]
    return out[:keep]


def build_zemljevid_page(premium, rules):
    """Interactive Leaflet map of all foraging + protected areas, coloured by
    today's index. Data is baked in (no client fetch) — Leaflet itself loads
    lazily on first click, mirroring the site's storm-map pattern."""
    meta = premium["species_meta"]
    pts = []
    # Popup lists the top 8 species per location (same depth as the location
    # detail panel on the main hub page — locDetailHtml uses the same slice)
    # instead of just 3, since a location routinely has 80+ species with a
    # nonzero index and 3 barely scratched the surface.
    MAP_POPUP_SPECIES = 8
    for loc in premium["locations"]:
        d0 = loc["days"][0]
        # species_out is sorted desc by index and always lists every indexed
        # species (many at 0 %) — only the ones with an actual positive score
        # belong in "how many species have some potential here".
        nonzero = [s for s in d0.get("species", []) if s["id"] in meta and s["index"] > 0]
        top = nonzero[:MAP_POPUP_SPECIES]
        pts.append({
            "name": loc["name"], "lat": loc["lat"], "lon": loc["lon"],
            "elev": loc["elev_m"], "terrain": loc.get("terrain"),
            "idx": d0["overall"], "lvl": d0["level"],
            "sp": [{"n": meta[s["id"]]["name_sl"], "i": s["index"]} for s in top],
            "sp_total": len(nonzero),
            "prot": False,
        })
    for loc in rules.get("locations", []):
        if loc.get("protected"):
            pts.append({
                "name": loc["name"], "lat": loc["lat"], "lon": loc["lon"],
                "elev": loc.get("elev_m"), "terrain": loc.get("terrain"),
                "idx": None, "lvl": None, "sp": [], "sp_total": 0, "prot": True,
            })
    data_js = _json_mod.dumps(pts, ensure_ascii=False)
    pick_count = sum(1 for p in pts if not p["prot"])

    # Server-rendered fallback list — same `pts` as the interactive map, so
    # there's no second source of truth to drift. Leaflet stays click-to-load
    # (see map_js below), but without it (crawlers, screen readers, JS off)
    # the area names/status were previously invisible on this page.
    fallback_rows = []
    for p in sorted(pts, key=lambda p: (p["prot"], -(p["idx"] or 0))):
        if p["prot"]:
            fallback_rows.append(
                f'''    <div class="gp-forest gp-forest-prot">
      <div class="gp-forest-info">
        <span class="gp-forest-nm">🔒 {_esc(p["name"])}</span>
        <span class="gp-terr">zaščiteno</span>
        <span class="gp-forest-sp">Preveri omejitve nabiranja</span>
      </div>
    </div>''')
        else:
            fallback_rows.append(
                f'''    <div class="gp-forest">
      <div class="gp-forest-info">
        <span class="gp-forest-nm">{_esc(p["name"])}</span>
        <span class="gp-terr">{_esc(p["terrain"] or "")} · {p["elev"]} m</span>
      </div>
      <div class="gp-forest-pct {level_class(p["idx"])}"><span class="n">{p["idx"]}/100</span><span class="lvl">{_esc(p["lvl"])}</span></div>
    </div>''')
    fallback_html = ('  <details class="gp-collapse">\n'
        '    <summary>Območja doline (seznam) <small>({pick_count})</small></summary>\n'
        '    <div class="gp-forests">\n' + "\n".join(fallback_rows) + '\n    </div>\n'
        '  </details>').format(pick_count=pick_count)

    # Real forest-stand composition (ZGS) per pickable location — only drawn
    # when a visitor arrives via ?loc= deep link (see focusName in map_js),
    # so it's fetched for all locations up front but stays inert weight
    # otherwise. Best-effort: a down/slow WFS just yields an empty list.
    sestoji_by_loc = {}
    for loc in premium["locations"]:
        stands = fetch_sestoji_near(loc["lat"], loc["lon"])
        if stands:
            sestoji_by_loc[loc["name"]] = stands
    sestoji_js = _json_mod.dumps(sestoji_by_loc, ensure_ascii=False)
    species_legend_html = "".join(
        f'<span><i style="background:{color}"></i>{name}</span>'
        for name, color in dict(ZGS_SPECIES_GROUPS.values()).items()
    )

    inner = f'''  <figure class="gp-photo-card">
    <img src="/gobarska-napoved/img/foto/gozdna-pot-dron.jpg" loading="lazy" width="640" height="853"
      alt="Dronski posnetek gozdne poti v Zgornji Savinjski dolini">
    <figcaption>📷 Avtorski dronski posnetek — gozdna pot skozi eno od nabiralnih območij</figcaption>
  </figure>
  <p class="post-meta">Vseh {pick_count} nabiralnih območij Zgornje Savinjske doline na eni karti,
  obarvanih po <strong>današnjem gobarskem indeksu</strong>. Klikni oznako za podrobnosti. Zavarovana območja
  so označena posebej — pred nabiranjem preveri veljavne omejitve na kraju samem. Oznake so
  <strong>širša območja</strong>, ne točne najdbe.</p>
  <div class="gp-map-legend">
    <span><i style="background:#34d399"></i>Dobra/odlična (≥55 %)</span>
    <span><i style="background:#f59e0b"></i>Zmerna (35–54 %)</span>
    <span><i style="background:#fb923c"></i>Slaba (18–34 %)</span>
    <span><i style="background:#f87171"></i>Brez (&lt;18 %)</span>
    <span><i style="background:#a78bfa"></i>Zaščiteno</span>
  </div>
  <div id="gp-species-legend" class="gp-map-legend" hidden>
    <b class="gp-species-legend-title">Drevesna sestava sestojev (ZGS):</b>
    {species_legend_html}
  </div>
  <div class="gp-map-shell">
    <div id="gp-map" class="gp-map" role="application" aria-label="Zemljevid nabiralnih območij"></div>
    <div id="gp-map-hint" class="gp-map-hint">
      <b>🗺️ Interaktivni zemljevid</b>
      <span>Klikni za nalaganje karte (Leaflet · OpenStreetMap / CARTO)</span>
      <span class="gp-map-load">Naloži zemljevid</span>
    </div>
  </div>
  <p class="gp-map-attr">Karta: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap</a>
  contributors, © <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>.
  Sestava sestojev: <a href="https://www.zgs.si/" target="_blank" rel="noopener">© Zavod za gozdove Slovenije</a>.
  Leaflet se naloži šele ob kliku (s storitve unpkg.com).</p>
{fallback_html}'''

    map_js = '''<script>
(function(){
  var PTS=''' + data_js + ''';
  var SESTOJI=''' + sestoji_js + ''';
  var hint=document.getElementById("gp-map-hint");
  var mapEl=document.getElementById("gp-map");
  var speciesLegend=document.getElementById("gp-species-legend");
  if(!mapEl||!hint)return;
  var loaded=false;
  function levelColor(v){
    if(v==null)return"#a78bfa";
    if(v>=55)return"#34d399";if(v>=35)return"#f59e0b";if(v>=18)return"#fb923c";return"#f87171";
  }
  function esc(s){return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
  function loadCss(href){var l=document.createElement("link");l.rel="stylesheet";l.href=href;document.head.appendChild(l);}
  function loadScript(src){return new Promise(function(res,rej){var s=document.createElement("script");s.src=src;s.onload=res;s.onerror=rej;document.head.appendChild(s);});}
  function popupHtml(p){
    var h='<div class="gp-map-pop"><b>'+esc(p.name)+'</b><br>';
    h+='<span class="terr">'+esc(p.terrain||"")+(p.elev?" · "+p.elev+" m":"")+'</span>';
    if(p.prot){
      h+='<div class="sp" style="color:#c4b5fd;margin-top:.35rem">🔒 Zavarovano območje — preveri aktualne '+
        'omejitve nabiranja na kraju samem</div>';
    }else{
      h+='<div style="margin-top:.35rem"><span class="idx" style="color:'+levelColor(p.idx)+'">'+p.idx+' / 100</span> · '+esc(p.lvl)+'</div>';
      if(p.sp&&p.sp.length){
        h+='<ul class="sp-list">'+p.sp.map(function(s){
          return'<li>🍄 '+esc(s.n)+' <span class="sp-pct">'+s.i+' %</span></li>';
        }).join('')+'</ul>';
        if(p.sp_total>p.sp.length)h+='<div class="sp-more">+'+(p.sp_total-p.sp.length)+' drugih vrst z indeksom</div>';
      }
    }
    h+='</div>';
    return h;
  }
  // Deep link from a location's forecast detail (?loc=<ime>) — zoom straight to
  // that point and open its popup instead of the default all-areas overview,
  // and skip the click-to-load gate since arriving here already is the intent.
  var focusName=null;
  try{focusName=new URLSearchParams(location.search).get("loc");}catch(e){}
  async function init(){
    if(loaded)return; loaded=true;
    hint.innerHTML='<span>Nalagam zemljevid …</span>';
    try{
      if(typeof L==="undefined"){
        loadCss("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
        await loadScript("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");
      }
      hint.style.display="none";
      var map=L.map("gp-map",{zoomControl:true,attributionControl:false,scrollWheelZoom:false}).setView([46.35,14.80],10);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {maxZoom:15,subdomains:"abcd"}).addTo(map);
      var group=[],focusMarker=null;
      PTS.forEach(function(p){
        var isFocus=focusName&&p.name===focusName;
        var m=L.circleMarker([p.lat,p.lon],{
          radius:p.prot?7:(isFocus?12:9),color:isFocus?"#fff":"#0b0906",weight:isFocus?2.5:1.5,
          fillColor:levelColor(p.idx),fillOpacity:p.prot?.55:.9
        }).addTo(map);
        m.bindPopup(popupHtml(p));
        m.bindTooltip(p.name,{direction:"top",offset:[0,-6]});
        if(isFocus)focusMarker=m;
        group.push(m);
      });
      if(focusMarker){
        map.setView(focusMarker.getLatLng(),13);
        focusMarker.openPopup();
        var stands=SESTOJI[focusName]||[];
        if(stands.length&&speciesLegend){
          stands.forEach(function(s){
            L.polygon(s.pts,{color:s.c,weight:1,fillColor:s.c,fillOpacity:.35}).addTo(map)
              .bindTooltip(s.sp,{sticky:true});
          });
          speciesLegend.hidden=false;
        }
      }else if(group.length){
        var fg=L.featureGroup(group);
        map.fitBounds(fg.getBounds().pad(0.15));
      }
      setTimeout(function(){map.invalidateSize();},60);
    }catch(e){
      hint.style.display="flex";
      hint.innerHTML='<span>Zemljevida trenutno ni mogoče naložiti.</span>';
      loaded=false;
    }
  }
  hint.addEventListener("click",init);
  if(focusName)init();
})();
</script>'''

    return subpage_shell(
        "zemljevid", "Zemljevid nabiralnih območij — Zgornja Savinjska dolina",
        f"Zemljevid {pick_count} nabiralnih območij Zgornje Savinjske doline, obarvanih po današnjem gobarskem "
        "indeksu, z označenimi zavarovanimi območji.",
        "Zemljevid", inner, extra_js=map_js)


def mini_map_preview_html(premium):
    """Compact, static (no Leaflet) area-status preview for the homepage —
    same today['overall']/level data build_zemljevid_page() uses, just a
    row of small chips instead of a full interactive map. Colour is always
    paired with the level word, never colour alone (accessibility)."""
    chips = []
    for loc in sorted(premium["locations"], key=lambda l: l["days"][0]["overall"], reverse=True):
        o = loc["days"][0]
        chips.append(
            f'    <a class="gp-mmap-chip" href="/gobarska-napoved/zemljevid/?loc={urllib.parse.quote(loc["name"])}">'
            f'<i style="background:{level_color(o["overall"])}"></i>'
            f'<span class="nm">{_esc(loc["name"])}</span>'
            f'<span class="pct">{o["overall"]}/100 · {_esc(o["level"])}</span></a>')
    for name in premium.get("protected_areas", []):
        chips.append(
            f'    <a class="gp-mmap-chip prot" href="/gobarska-napoved/zemljevid/?loc={urllib.parse.quote(name)}">'
            f'<i style="background:#a78bfa"></i>'
            f'<span class="nm">{_esc(name)}</span>'
            f'<span class="pct">Zaščiteno</span></a>')
    return ('  <div class="gp-mini-map">\n'
            '    <h2 class="gp-h2">🗺️ Danes v dolini</h2>\n'
            '    <div class="gp-mini-map-grid">\n' + "\n".join(chips) + '\n    </div>\n'
            '    <a class="gp-cta alt" href="/gobarska-napoved/zemljevid/">Odpri interaktivni zemljevid →</a>\n'
            '  </div>')


def photo_credits_html(img_dir):
    """CC BY / CC BY-SA / GFDL all require visible attribution — render the
    CREDITS.json sitting next to gobarska-napoved/img/<img_dir>/*.jpg as a
    collapsible source table."""
    credits_path = os.path.join(ROOT, "gobarska-napoved", "img", img_dir, "CREDITS.json")
    try:
        with open(credits_path, encoding="utf-8") as f:
            photo_credits = _json_mod.load(f)
    except (OSError, ValueError):
        photo_credits = {}
    credit_rows = []
    for fn in sorted(photo_credits, key=lambda k: photo_credits[k]["sl"]):
        c = photo_credits[fn]
        credit_rows.append(
            f'      <tr><td>{_esc(c["sl"])}<br><span class="lat">{_esc(c["latin"])}</span></td>'
            f'<td>{_esc(c["artist"])}</td>'
            f'<td>{_esc(c["license"])}</td>'
            f'<td><a href="{_esc(c["source_url"])}" target="_blank" rel="noopener">Wikimedia Commons</a></td></tr>')
    if not credit_rows:
        return ""
    return (
        '  <details class="gp-collapse">\n'
        f'    <summary>Viri fotografij <small>({len(credit_rows)})</small></summary>\n'
        '    <p class="archive-intro">Fotografije so iz Wikimedia Commons, objavljene pod prostimi licencami '
        '(CC BY, CC BY-SA ali javna domena). Hvala vsem fotografinjam in fotografom.</p>\n'
        '    <div class="gp-scroll" style="max-height:320px"><table class="gp-sptable"><thead><tr>'
        '<th>Vrsta</th><th>Avtor/ica</th><th>Licenca</th><th>Vir</th></tr></thead><tbody>\n'
        + "\n".join(credit_rows) + "\n    </tbody></table></div>\n"
        '  </details>')


def build_body(rules, premium, free):
    home = next((l for l in premium["locations"] if l["home"]), premium["locations"][0])
    pct = free["index"]
    lvl = free["level"]
    top_sl = free["top_species_sl"] or "—"
    best_loc = max(premium["locations"], key=lambda l: l["days"][0]["overall"])
    best_o = best_loc["days"][0]

    species = rules["species"]
    indexed = [s for s in species if s.get("gets_index")]
    month = TODAY.month

    # ── HERO (free teaser) ────────────────────────────────────────────────────
    hero_trend = hero_trend_html(pct)
    hero = f'''  <div class="gp-hero">
    <div class="gp-hero-top">
      <div class="gp-gauge-wrap">
        {gauge_svg(pct)}
        <div class="gp-gauge-num"><span class="num">{pct}</span><small>/ 100</small></div>
      </div>
      <div class="gp-hero-body">
        <div class="gp-hero-kicker">Gobarski indeks danes · Rečica ob Savinji</div>
        <div class="gp-hero-lvl" style="color:{level_color(pct)}">{lvl}</div>
        {hero_trend}
        <div class="gp-hero-best">🌲 Najugodnejši gozd danes: <strong>{_esc(best_loc["name"])}</strong>
          <span class="gp-hero-best-pct" style="background:{level_color(best_o["overall"])}22;color:{level_color(best_o["overall"])}">{best_o["overall"]} / 100 · {best_o["level"]}</span></div>
        {f'<div class="gp-hero-topsp">🍄 Najbolj obetavna vrsta: <strong>{_esc(top_sl)}</strong></div>' if top_sl != "—" else ""}
        <a class="gp-cta gp-cta-lg" href="#pricing" id="gp-hero-unlock">Odkleni 7-dnevno napoved po vrstah →</a>
      </div>
    </div>
    <div class="gp-action-chips">
      <button type="button" class="gp-chip-action" id="gp-share-btn"
        data-pct="{pct}" data-lvl="{_esc(lvl)}">📤 Deli</button>
      <a class="gp-chip-action" href="/gobarska-napoved/zemljevid/">🗺️ Zemljevid</a>
      <a class="gp-chip-action" href="#pricing">🔔 Obvesti me ob ugodnih pogojih</a>
    </div>
    <span id="gp-share-msg" class="gp-msg" style="min-height:auto"></span>
    <div class="gp-hero-note">Indeks je <strong>ocena ugodnosti pogojev</strong> za rast, ne obljuba najdbe.
    Upošteva temperaturo in vlago tal, kumulativne padavine (lokalno iz postaje IREICA1), zračno vlago in
    nočno ohladitev — po vrstah in po geologiji terena.
    <a href="/gobarska-napoved/metodologija/">Kako izračunamo indeks →</a></div>
  </div>'''

    # ── today per forest (free) — compact row: info left, % disc right ────────
    forests = ['  <div class="gp-forests">']
    for loc in sorted(premium["locations"], key=lambda l: l["days"][0]["overall"], reverse=True):
        o = loc["days"][0]
        top = o["species"][0]
        top_nm = premium["species_meta"][top["id"]]["name_sl"] if top else "—"
        top_ic = (f'<img class="gp-sp-ic" src="/gobarska-napoved/img/vrste/{top["id"]}.jpg" alt="" loading="lazy" '
                  'onerror="this.replaceWith(document.createTextNode(\'🍄 \'))">') if top else "🍄 "
        terr = loc.get("terrain", "")
        t_icon = TERRAIN_STYLE.get(terr, ("", "🌲"))[1]
        pct_cls = level_class(o["overall"])
        forests.append(
            f'''    <div class="gp-forest">
      <div class="gp-forest-info">
        <span class="gp-forest-nm">{t_icon} {_esc(loc["name"])}</span>
        <span class="gp-terr">{terr} · {loc["elev_m"]} m</span>
        <span class="gp-forest-sp">{top_ic}{_esc(top_nm)}</span>
      </div>
      <div class="gp-forest-pct {pct_cls}"><span class="n">{o["overall"]}/100</span><span class="lvl">{o["level"]}</span></div>
    </div>''')
    if premium.get("protected_areas"):
        forests.append(
            f'''    <div class="gp-forest gp-forest-prot">
      <div class="gp-forest-info">
        <span class="gp-forest-nm">🔒 {_esc(", ".join(premium["protected_areas"]))}</span>
        <span class="gp-terr">zaščiteno</span>
        <span class="gp-forest-sp">Preveri omejitve nabiranja</span>
      </div>
    </div>''')
    forests.append("  </div>")
    forests_html = "\n".join(forests)

    # ── PREMIUM locked block ────────────────────────────────────────────────
    # Placeholder rows read like real forecast lines (number + level word),
    # not manually-masked dots — the CSS blur filter on .gp-skel is what
    # actually obscures them. Values are generic decoys, not the real
    # per-species forecast, so the teaser never leaks paywalled numbers.
    _SKEL_DECOY = [(72, "DOBRA"), (58, "ZMERNA"), (81, "ODLIČNA"), (44, "ZMERNA"), (65, "DOBRA")]
    skel_rows = "\n".join(
        f'      <div class="gp-forest"><span>{_esc(premium["species_meta"][s["id"]]["name_sl"])}</span>'
        f'<b>{_SKEL_DECOY[i % len(_SKEL_DECOY)][0]} % · {_SKEL_DECOY[i % len(_SKEL_DECOY)][1]}</b></div>'
        for i, s in enumerate(home["days"][0]["species"][:5]))
    premium_block = f'''  <div id="gp-premium-status" class="gp-msg" hidden></div>
  <div id="gp-content" hidden></div>
  <div id="gp-identify" class="gp-ai-card" hidden>
    <div class="gp-ai-banner">
      <span class="gp-ai-badge">✨ AI</span>
      <span class="gp-ai-icon">🔍<span class="gp-ai-icon-mush">🍄</span></span>
      <span class="gp-ai-banner-title">AI prepoznava gobe</span>
    </div>
    <div class="gp-ai-body">
    <p class="gp-diary-priv">Naloži fotografijo najdene gobe — AI predlaga najverjetnejšo vrsto iz lokalne baze
    {len(species)} vrst, oceni zanesljivost in opozori na nevarne dvojnice. <b>To ni zamenjava za mikologa</b> — ob
    najmanjšem dvomu gobe nikoli ne uživaj.</p>
    <div class="gp-diary-row">
      <label class="gp-diary-btn gp-diary-photobtn">📷 Izberi fotografijo
        <input type="file" accept="image/*" capture="environment" id="gp-id-photo" hidden>
      </label>
      <img id="gp-id-preview" class="gp-d-photo-preview" alt="">
      <button type="button" class="gp-cta" id="gp-id-btn" disabled>Prepoznaj gobo</button>
    </div>
    <div id="gp-id-status" class="gp-msg"></div>
    <div id="gp-id-result"></div>
    </div>
  </div>
  <div id="gp-alerts" class="gp-alert-card" hidden>
    <h3 style="margin-top:0">🔔 Moji alarmi</h3>
    <p class="gp-diary-priv">Nastavi lastne pogoje (vrsta, območje, nadmorska višina, prag) — pošljemo e-mail, ko jih
    napoved doseže. Preverjeno enkrat dnevno, ob jutranji objavi nove napovedi.</p>
    <div id="gp-alert-rows" class="gp-alert-rows"></div>
    <div class="gp-alert-actions">
      <button type="button" class="gp-diary-btn" id="gp-alert-add">+ Dodaj alarm</button>
      <button type="button" class="gp-cta" id="gp-alert-save">Shrani alarme</button>
    </div>
    <div id="gp-alert-msg" class="gp-msg"></div>
  </div>
  <div id="gp-lock" class="gp-lock">
    <span class="gp-tag">🔒 PREMIUM</span>
    <h3>7-dnevna napoved po vrstah in gozdovih</h3>
    <p class="gp-hero-sub">Za vsak dan naslednjega tedna in vsako od {len(premium["locations"])} nabiralnih območij:
    indeks po posameznih vrstah, plastovita razlaga (»talna temp. optimalna, sprožilni dež pred 8–16 dnevi pod pragom,
    nočna ohladitev zaznana«) in opozorila na nevarne dvojnice. Vključuje tudi <b>🔍 AI prepoznavo gobe iz fotografije</b>.</p>
    <div class="gp-skel">
{skel_rows}
    </div>
    <div class="gp-lockbar">
      <button type="button" class="gp-cta" data-paddle="monthly" data-src="lock">Naroči se ({PRICE_MONTHLY}/mes)</button>
      <button type="button" class="gp-cta alt" data-paddle="season" data-src="lock">Sezonski dostop ({PRICE_SEASON})</button>
    </div>
  </div>'''

    # ── pricing ───────────────────────────────────────────────────────────────
    # Bullets naj vodijo z izidom ("kdaj in kam iti"), ne s funkcijo — funkcije
    # (AI prepoznava, alarmi) ostanejo navedene, a niže, kot podporo izidu.
    pricing = f'''  <div id="gp-pricing-wrap">
  <h2 id="pricing" class="gp-h2">🎟️ Vedeti, kdaj iti v gozd</h2>
  <p class="post-meta">Ne ugibaj, ali je prezgodaj po dežju. Premium spremlja vlago tal, temperaturo, dež in
  rastni zamik posamezne vrste — in pove, katera vrsta in katero območje imata danes največ možnosti.</p>
  <div class="gp-pricing">
    <div class="gp-plan">
      <span class="gp-tag">MESEČNO</span>
      <div class="p-price">{PRICE_MONTHLY}<small> / mesec</small></div>
      <ul>
        <li>Naslednjih 7 dni, ne le danes</li>
        <li>Katera vrsta ima danes najboljše pogoje, na katerem od {len(premium["locations"])} območij</li>
        <li>Razlage po komponentah in opozorila na nevarne dvojnice</li>
        <li>🔍 AI prepoznava gobe iz fotografije</li>
        <li>🔔 Alarm, ko se pogoji izboljšajo</li>
        <li>Prekliči kadarkoli</li>
      </ul>
      <button type="button" class="gp-cta" data-paddle="monthly" data-src="pricing">Naroči se</button>
    </div>
    <div class="gp-plan best">
      <span class="gp-tag">CELA SEZONA</span>
      <div class="p-price">{PRICE_SEASON}<small> / sezona</small></div>
      <ul>
        <li>Vse iz mesečnega paketa (vklj. 🔍 AI prepoznavo in 🔔 alarme)</li>
        <li>Dostop do konca sezone (30. 11.)</li>
        <li>Enkratno plačilo, brez obnavljanja</li>
        <li>Podpora lokalnemu projektu</li>
      </ul>
      <button type="button" class="gp-cta" data-paddle="season" data-src="pricing">Kupi sezono</button>
    </div>
  </div>
  <div id="gp-checkout-msg" class="gp-msg"></div>
  <p class="muted-note">Plačila varno obdeluje Paddle (prodajalec od zapisa, uredi DDV za EU). Brez ustvarjanja
  računa — po plačilu prejmeš povezavo za dostop na svoj e-naslov, ki deluje na vseh napravah.</p>
  </div>'''

    # ── monthly calendar (free) — structured data for the chip+card /koledar/
    # page (build_koledar_page); nothing on the hub page itself reads this.
    cal_data = [
        {"m": m, "name": seo.MES_NOM[m].capitalize(),
         "species": [s["name_sl"] for s in indexed if m in season_months(s)],
         "current": m == month}
        for m in range(1, 13)
    ]

    # ── species reference cards (free, SEO + credibility) ─────────────────────
    # Card top-half shows a real photo once one exists at img/vrste/<id>.jpg;
    # until then onerror swaps it for an edibility-tinted placeholder, so
    # photos can be dropped in later species-by-species with no code change
    # (same graceful-fallback trick as the /dvojnice/ comparison cards).
    #
    # ── dvojnik: side-by-side edible vs. dangerous-double comparison ──────────
    # Photos: drop matching files into gobarska-napoved/img/dvojnice/<slug>.jpg
    # (slug = species id / _slug(double name)) — the <img> quietly falls back
    # to a placeholder icon via onerror until a real photo exists, so this
    # activates automatically without further code changes.
    vs_cards, vs_notes = [], []
    danger_order = {"smrtno strupena": 0, "zelo strupena": 1, "strupena": 2, "zaščitena": 3, "neužitna": 4}
    vs_species = [s for s in indexed if s.get("doubles")]
    vs_species.sort(key=lambda s: danger_order.get(double_danger(s["doubles"]), 9))
    for s in vs_species:
        parsed = parse_double(s["doubles"])
        if not parsed:
            vs_notes.append(f'    <div class="gp-vs-note"><b>{_esc(s["name_sl"])}:</b> {_esc(s["doubles"])}</div>')
            continue
        dname, dlatin, bullets = parsed
        danger = double_danger(s["doubles"])
        badge = edib_badge(danger) if danger else ""
        e_img = f"/gobarska-napoved/img/dvojnice/{s['id']}.jpg"
        d_img = f"/gobarska-napoved/img/dvojnice/{_slug(dname)}.jpg"
        bullets_html = "".join(f"<li>{_esc(b)}</li>" for b in bullets)
        vs_cards.append(f'''    <div class="gp-vs-card">
      <div class="gp-vs-pair">
        <div class="gp-vs-side">
          <div class="gp-vs-photo"><img src="{e_img}" alt="{_esc(s["name_sl"])}" loading="lazy"
            onerror="this.replaceWith(Object.assign(document.createElement('span'),{{textContent:'🍄'}}))"></div>
          <div class="gp-vs-name">✅ {_esc(s["name_sl"])}</div>
          <div class="gp-vs-lat">{_esc(s["name_lat"])}</div>
        </div>
        <div class="gp-vs-x">VS</div>
        <div class="gp-vs-side">
          <div class="gp-vs-photo"><img src="{d_img}" alt="{_esc(dname)}" loading="lazy"
            onerror="this.replaceWith(Object.assign(document.createElement('span'),{{textContent:'☠️'}}))"></div>
          <div class="gp-vs-name">{_esc(dname)}</div>
          <div class="gp-vs-lat">{_esc(dlatin)}</div>
          {badge}
        </div>
      </div>
      <ul class="gp-vs-diff">{bullets_html}</ul>
    </div>''')
    vs_html = ('  <div class="gp-vs-grid">\n' + "\n".join(vs_cards) + "\n  </div>\n"
               + ("\n".join(vs_notes) if vs_notes else ""))

    # ── photo credits (CC BY / CC BY-SA / GFDL require visible attribution) ───
    credits_html = photo_credits_html("dvojnice")

    # Števila na karticah pregleda se izpeljejo iz istih podatkov, iz katerih
    # nastanejo strani — drugače zastarijo ob vsaki razširitvi baze.
    features_html = feature_cards_html({"spots": len(premium["locations"]),
                                        "species": len(species), "pairs": len(vs_cards)})
    vrste_credits_html = photo_credits_html("vrste")
    mini_map_html = mini_map_preview_html(premium)

    # ── terrain map (free) ────────────────────────────────────────────────────
    terr_items = []
    for t in rules.get("terrains", []):
        locs_here = [l["name"] for l in rules["locations"]
                     if l.get("terrain") == t["id"] and not l.get("protected")]
        col, icon = TERRAIN_STYLE.get(t["id"], ("#5a8f3f", "🌲"))
        terr_items.append(
            f'    <div class="t" style="border-left-color:{col}">'
            f'<div class="t-h"><span class="t-ic" style="background:{col}22">{icon}</span>'
            f'<b>{_esc(t["name_sl"])}</b></div>'
            f'<span class="gp-hero-sub">{_esc(t.get("note",""))}</span><br>'
            f'<span class="gp-terr">Napovedne točke: {_esc(", ".join(locs_here) or "—")}</span></div>')
    terrain_html = '  <div class="gp-terrmap">\n' + "\n".join(terr_items) + "\n  </div>"

    # ── FAQ (free) ────────────────────────────────────────────────────────────
    qa = [
        ("Je gobarski indeks napoved najdbe?",
         "Ne. Indeks (0–100) je ocena, kako ugodni so vremenski in talni pogoji za rast posamezne vrste — "
         "temperatura in vlaga tal, sprožilni dež v rastnem zamiku vrste, zaloga vode pred njim, zračna vlaga "
         "in nočna ohladitev, uteženo po vrsti in geologiji terena. Gozd ima vedno zadnjo besedo; visok indeks "
         "pomeni ugodne razmere, ne zajamčene gobe. Podrobno na strani »Kako deluje model«."),
        ("Katere vrste zajema premium napoved?",
         "Napoved po vrstah pokriva užitne in pogojno užitne gobe iz lokalne baze Zgornje Savinjske doline. "
         "Strupene vrste se pojavijo le kot opozorilo na nevarne dvojnice ob pripadajoči užitni vrsti."),
        ("Zakaj indeksa ne dobijo vse vrste iz baze?",
         "Baza vrst je referenčna in je precej večja od napovedi. Indeks dobijo užitne vrste, ki so v dolini "
         "res prisotne in jih je mogoče zanesljivo določiti. Vrste, ki so v bazi zaradi opozorila na dvojnico, "
         "in tiste iz razširjenega seznama, ki na terenu v dolini niso preverjene, ostanejo brez indeksa — "
         "raje manj napovedanih vrst kot napoved, ki vabi po gobo z nevarno dvojnico."),
        ("Zakaj po istem dežju vse vrste ne zrastejo hkrati?",
         "Ker se skupine gliv odzivajo z različnim zamikom, in model ga upošteva. Razkrojevalke stelje in "
         "travinja (kukmaki, tintnice, marela) tvorijo trosnjake nekaj dni po plohi, lesne razkrojevalke "
         "(ostrigar, panjevka, uhljevka) nekoliko pozneje, mikorizne vrste (gobani, lisičke, golobice) pa šele "
         "teden in pol do dva. Padavinsko okno je zato pri vsaki vrsti zamaknjeno za njen rastni zamik: dež, "
         "ki je padel včeraj, jurčku danes indeksa ne dvigne, kukmaku pa ga lahko. Skupina in zamik sta "
         "izpisana na kartici vsake vrste."),
        ("Zakaj se indeks razlikuje med gozdovi?",
         "Model upošteva geologijo: kislo vulkansko pogorje Smrekovca ustreza jurčkom in žametastemu gobanu, "
         "karbonatni masivi Golte in Menine pa marelam in poletnemu gobanu. Zato ista vrsta isti dan ni enako "
         "verjetna povsod."),
        ("Kako plačam in dostopam?",
         "Plačilo obdela Paddle. Po nakupu prejmeš na e-naslov povezavo za dostop, ki deluje na vseh napravah — "
         "brez ustvarjanja računa in gesla. Če izgubiš povezavo, jo z istim e-naslovom kadarkoli zahtevaš znova."),
        ("Koliko gob smem nabrati?",
         "V Sloveniji je dovoljeno nabrati do 2 kg gob na osebo na dan (Uredba o varstvu samoniklih gliv). "
         "Nekatera območja doline (npr. Logarska dolina) so zavarovana — zavarovan status sam po sebi ne "
         "pomeni nujno splošne prepovedi nabiranja, zato pred nabiranjem preveri veljavne omejitve na kraju "
         "samem."),
        ("Ali je to uradna napoved ARSO?",
         "Ne. Gre za samostojen model, izračunan iz podatkov Open-Meteo in meritev postaje IREICA1 v Rečici ob "
         "Savinji. Ni uradna napoved ARSO."),
    ]
    faq_html = ("  <h2 class=\"gp-h2\" id=\"faq\">❓ Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{_esc(q)}</summary><p>{_esc(a)}</p></details>' for q, a in qa
    ) + "\n  </div>")

    # ── Gobarjev dnevnik: GPS + photo diary, 100% local (localStorage only,
    # nothing sent to any server — see zasebnost.html). Species datalist for
    # the free-text input, built from the edible species already in scope.
    species_options = "".join(f'<option value="{_esc(s["name_sl"])}">' for s in indexed)
    diary_html = f'''  <div class="gp-diary">
    <p class="gp-diary-priv" id="gp-diary-priv">📱 Najdbe se shranijo <b>samo v tvojem brskalniku</b> (localStorage) — nikamor se ne
    pošljejo, nihče drug jih ne vidi. Če počistiš podatke brskalnika, se izgubijo.</p>
    <div id="gp-diary-sync" class="gp-msg" hidden></div>
    <form id="gp-diary-form">
      <div class="gp-diary-row">
        <input type="date" id="gp-d-date" required>
        <input type="text" id="gp-d-species" list="gp-d-species-list" placeholder="Vrsta (neobvezno)">
        <datalist id="gp-d-species-list">{species_options}</datalist>
      </div>
      <div class="gp-diary-row">
        <button type="button" class="gp-diary-btn" id="gp-d-geo">📍 Zabeleži lokacijo</button>
        <span id="gp-d-geo-status" class="gp-msg" style="margin:0"></span>
      </div>
      <div class="gp-diary-row">
        <label class="gp-diary-btn gp-diary-photobtn">📷 Fotografija
          <input type="file" accept="image/*" capture="environment" id="gp-d-photo" hidden>
        </label>
        <img id="gp-d-photo-preview" class="gp-d-photo-preview" alt="">
      </div>
      <div class="gp-diary-row">
        <textarea id="gp-d-notes" placeholder="Opombe — količina, mesto, opažanja …"></textarea>
      </div>
      <button type="submit" class="gp-cta gp-diary-submit">💾 Shrani najdbo</button>
    </form>
    <div id="gp-diary-list" class="gp-diary-list"></div>
  </div>'''

    coming_soon = '''  <div id="gp-cs-cover" class="gp-cs-card">
    <span class="gp-tag">🍄 KMALU</span>
    <h2>MeteoGobar prihaja kmalu</h2>
    <p>Gobarska napoved za Zgornjo Savinjsko dolino se še pripravlja — brezplačni in premium del bosta na voljo
    v kratkem. Že imaš dostop (zgodnji naročniki)? Vpiši e-naslov spodaj za povezavo.</p>
    <form id="gp-login" class="gp-login" autocomplete="email">
      <input type="email" name="email" placeholder="e-naslov" required>
      <button type="submit">Pošlji povezavo</button>
    </form>
    <div id="gp-login-msg" class="gp-msg"></div>
  </div>'''

    body = f'''{BRAND_SWAP}
{top_bar_html("Gobarska napoved", None)}
{seo.crumbs_html([("Meteorec", "/"), ("Gobarska napoved", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Gobarska napoved — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Model rasti gob po vrstah · lokalna baza {len(species)} vrst · osvežuje se dnevno · {TODAY.isoformat()}</p>
{coming_soon}
  <div id="gp-cs-wrap" class="gp-cs-blur">
{hero}
{mini_map_html}
{features_html}
  <h2 class="gp-h2" id="premium">🔓 Premium: 7-dnevna napoved po vrstah</h2>
{premium_block}
{pricing}
{faq_html}
  <p class="gp-disc">Napoved je <strong>indeks ugodnosti pogojev</strong>, ne obljuba najdbe. Pripravlja jo Filip Eremita
  (gozdarstvo/mikologija) iz meritev postaje IREICA1 in podatkov Open-Meteo. Ni uradna napoved ARSO.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>
{bottom_nav_html("")}
  </div>
  <button type="button" class="gp-sos-fab" id="gp-sos-btn" aria-label="Sum zastrupitve z gobami — pomoč">🆘</button>
  <div class="gp-sos-panel" id="gp-sos-panel">
    <h4>Sum zastrupitve z gobami?</h4>
    <p>Ob težavah z dihanjem, hudi omotici ali izgubi zavesti pokliči takoj <b>112</b>. Za posvet o zaužiti gobi
    (tudi če se počutiš še dobro — nekateri simptomi pridejo z zamikom) pokliči Center za zastrupitve.</p>
    <a class="gp-sos-call" href="tel:112">🚨 112 <small>Nujna medicinska pomoč</small></a>
    <a class="gp-sos-call alt" href="tel:+38615225283">☎️ (01) 522 52 83 <small>Center za zastrupitve UKC Ljubljana · 24 ur</small></a>
    <p style="margin-bottom:0">Vzemi s seboj vzorec gobe (cela, s trosovnico) — pomaga pri določitvi vrste.</p>
  </div>
{PAGE_JS}'''
    subpages = {
        "cal_data": cal_data, "month": month,
        "species": species,
        "vs_html": vs_html, "vs_count": len(vs_cards),
        "credits_html": credits_html, "vrste_credits_html": vrste_credits_html,
        # Razdelki, ki so se z glavne strani preselili na svoje podstrani.
        "forests_html": forests_html, "terrain_html": terrain_html, "diary_html": diary_html,
    }
    return body, subpages


def main():
    print(f"[{TODAY}] Gradim gobarsko prodajno stran …")
    rules = gm.load_rules()
    spots, protected = gm.load_locations(rules)
    try:
        locs = gm.fetch_forecast(spots)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"✗ Open-Meteo: {e}", file=sys.stderr)
        sys.exit(1)
    if len(locs) != len(spots):
        print(f"✗ Pričakoval {len(spots)} lokacij, dobil {len(locs)}", file=sys.stderr)
        sys.exit(1)

    station_precip = gm.load_station_precip()
    premium = gm.compute_forecast(rules, spots, locs, station_precip, protected)
    free = gm.free_payload(premium)

    body, sub = build_body(rules, premium, free)

    build_zemljevid_page(premium, rules)
    build_koledar_page(sub["cal_data"], sub["month"])
    build_trend_page()
    n_baza = build_baza_vrst_pages(sub["species"], sub["vrste_credits_html"])
    build_dvojnice_page(sub["vs_html"], sub["vs_count"], sub["credits_html"])
    build_danes_page(sub["forests_html"], free)
    build_tereni_page(sub["terrain_html"])
    build_nasveti_page()
    build_metodologija_page()
    build_dnevnik_page(sub["diary_html"])
    print(f"  → {3 + n_baza + 6} podstrani (zemljevid, koledar, trend, "
          f"baza-vrst + {n_baza - 1} po skupinah, dvojnice, danes, tereni, nasveti, metodologija, dnevnik)")

    url = "/gobarska-napoved/"
    title = "Gobarska napoved — Zgornja Savinjska dolina"
    # Meta description naj ostane pod ~160 znaki, sicer jo Google odreže sredi
    # stavka; zadnji del je zato najbolj pogrešljiv.
    desc = (f"Gobarski indeks danes: {free['index']} % ({free['level']}). Napoved rasti gob po vrstah za "
            f"Zgornjo Savinjsko dolino, baza {len(rules['species'])} vrst in nevarne dvojnice.")

    qa_for_schema = [
        ("Je gobarski indeks napoved najdbe?",
         "Ne. Indeks je ocena ugodnosti vremenskih in talnih pogojev za rast, ne obljuba najdbe."),
        ("Katere vrste zajema premium napoved?",
         "Užitne in pogojno užitne gobe Zgornje Savinjske doline; strupene le kot opozorilo na dvojnice."),
        ("Zakaj po istem dežju vse vrste ne zrastejo hkrati?",
         "Ker se skupine gliv odzivajo z različnim zamikom. Razkrojevalke stelje tvorijo trosnjake nekaj dni po "
         "plohi, lesne razkrojevalke nekoliko pozneje, mikorizne vrste šele teden in pol do dva — model "
         "padavinsko okno zato pri vsaki vrsti zamakne za njen rastni zamik."),
        ("Ali je to uradna napoved ARSO?",
         "Ne. Samostojen model iz podatkov Open-Meteo in meritev postaje IREICA1. Ni uradna napoved ARSO."),
    ]
    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Gobarska napoved", None)]),
        seo.faq_schema(qa_for_schema),
    ])
    head_extras = schema + "\n" + PAGE_CSS + "\n" + paddle_head()

    og_image = f"{seo.SITE}/og/gobarska-napoved.jpg"
    html = seo.page_shell(title, desc, url, head_extras, body, og_image=og_image)
    seo.write_page("gobarska-napoved/index.html", html, force=True)
    print(f"  → gobarska-napoved/index.html ({free['index']} %, {free['level']})")


if __name__ == "__main__":
    main()
