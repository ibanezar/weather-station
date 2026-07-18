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
    return "neužitna"


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
.gp-forests{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.6rem;margin:.6rem 0 1.2rem}
/* Compact two-column row: name/terrain/species stack on the left, a single
   glanceable colour-coded percentage disc on the right — so scanning the
   whole list for "where's it worth going" doesn't require reading every
   line, the disc colour + number says it at a glance. */
.gp-forest{background:var(--fc-bg);border:1px solid var(--fc-border);border-radius:12px;padding:.6rem .8rem;
  display:flex;align-items:center;justify-content:space-between;gap:.7rem}
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
.gp-forest-pct .n{font-size:1.05rem;font-weight:800;line-height:1;font-variant-numeric:tabular-nums}
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
  align-items:stretch;gap:.7rem;padding-right:3.4rem}
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
   above them — most visibly right under the sticky quicknav. Force room. */
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

/* ── Hitri meni (sticky) + zložljive (details) sekcije ── */
/* Wrapper omogoča fade namig na desni, da je jasno, da se meni scrolla vodoravno. */
.gp-quicknav-wrap{position:sticky;top:0;z-index:20;background:var(--bg);
  border-bottom:1px solid var(--border);margin:.2rem 0 1.4rem}
.gp-quicknav-wrap::after{content:"";position:absolute;top:0;right:0;bottom:1px;width:2.4rem;
  pointer-events:none;background:linear-gradient(90deg,transparent,var(--bg))}
/* flex-wrap intentionally omitted (default nowrap) so the row never breaks
   onto a second line; overflow-x:auto turns the overflow into a touch/scroll
   swipe instead. Scrollbar hidden per-engine (Firefox/WebKit/legacy Edge)
   since the horizontal swipe is already obvious from the chip row itself. */
.gp-quicknav{display:flex;flex-wrap:nowrap;gap:.45rem;overflow-x:auto;padding:.65rem 0;
  scrollbar-width:none;-ms-overflow-style:none;-webkit-overflow-scrolling:touch}
.gp-quicknav::-webkit-scrollbar{display:none}
.gp-quicknav a{flex:0 0 auto;display:inline-flex;align-items:center;min-height:2.75rem;
  background:var(--badge-bg);border:1px solid var(--card-border);
  color:var(--text);text-decoration:none;font-size:.82rem;padding:.4rem .8rem;border-radius:20px;
  white-space:nowrap;transition:border-color .15s ease,color .15s ease}
.gp-quicknav a:last-child{margin-right:2.4rem}
.gp-quicknav a:hover{border-color:var(--blue);color:var(--blue)}
.gp-collapse{border:1px solid var(--card-border);border-radius:14px;margin:.6rem 0 1rem;overflow:hidden}
.gp-collapse summary{cursor:pointer;list-style:none;padding:.8rem 1rem;font-weight:700;
  display:flex;align-items:center;justify-content:space-between;background:var(--card-bg)}
.gp-collapse summary::-webkit-details-marker{display:none}
.gp-collapse summary::after{content:"▾";color:var(--muted);transition:transform .2s ease;margin-left:.6rem}
.gp-collapse[open] summary::after{transform:rotate(180deg)}
.gp-collapse summary small{font-weight:500;color:var(--muted);margin-left:.5rem}
.gp-collapse > :not(summary){padding:0 1rem 1rem}
.gp-collapse[open] > :not(summary){padding-top:.3rem}
/* ── Section-level accordions (Geološki tereni / Nasveti / Dnevnik) — same
   collapse mechanics as .gp-collapse, but the summary reads like a .gp-h2
   heading rather than a small card toggle, so a closed section still looks
   like a normal page section, just one the user has to tap to open. Default
   closed (no `open` attribute) keeps the "active" data above the fold. ── */
.gp-collapse-section{border:none;border-radius:0;margin:2.6rem 0 1rem;overflow:visible;scroll-margin-top:4rem}
.gp-collapse-section summary{padding:0 0 .4rem;min-height:2.75rem;border-bottom:1px solid var(--border);
  background:transparent;font-size:1.35rem;font-weight:700}
.gp-collapse-section summary::after{font-size:1rem}
.gp-collapse-section > .gp-collapse-body{padding:.9rem 0 0}
/* FAQ <details> otherwise rely on bare UA defaults — too short a tap target
   on mobile. Padding (not margin) grows the hit area without widening the
   row's footprint or spacing against its neighbours. */
.faq details{border-bottom:1px solid var(--border)}
.faq details:last-child{border-bottom:0}
.faq summary{cursor:pointer;min-height:2.75rem;display:flex;align-items:center;
  padding:.7rem .2rem;font-weight:600}
.faq p{margin:0 .2rem .8rem;color:var(--muted);font-size:.9rem;line-height:1.6}

/* ── Navigacijski hub (kartice na podstrani) ── */
.gp-hub{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.8rem;margin:.6rem 0 1.2rem}
.gp-hub-card{display:flex;flex-direction:column;background:var(--card-bg);overflow:hidden;
  border:1px solid var(--card-border);border-radius:14px;
  text-decoration:none;color:var(--text);box-shadow:var(--card-shadow);
  transition:border-color .15s ease,transform .15s ease}
.gp-hub-card:hover{border-color:var(--blue);transform:translateY(-2px)}
.gp-hub-photo{height:84px}
.gp-hub-photo img{width:100%;height:100%;object-fit:cover;display:block}
.gp-hub-body{display:flex;flex-direction:column;gap:.3rem;padding:.85rem 1.1rem 1.05rem}
.gp-hub-ic{font-size:1.3rem}
.gp-hub-title{font-weight:700;font-size:1.02rem}
.gp-hub-sub{font-size:.82rem;color:var(--muted);line-height:1.4}
.gp-hub-arrow{margin-top:.3rem;font-size:.8rem;color:var(--blue);font-weight:600}

/* Zadnja vsebina naj se ne skrije za plavajočim SOS gumbom (spodaj desno).
   body .wrap (not .wrap) so this reliably beats blog.css's own unconditional
   .wrap{padding:2rem 0 4rem}, which loads after this inline stylesheet and
   would otherwise win the tie on source order alone. Declared here, right
   before the mobile media query below, so the narrower 9.7rem/3.5rem
   mobile override (same specificity) still wins on small screens — a rule
   after this one in source order would otherwise beat it regardless of
   which media query is narrower. */
body .wrap{padding-bottom:5.5rem}

/* ── Bottom nav (mobile, app-style) — hidden on desktop, where the top
   quicknav/hub cards already cover cross-page navigation ── */
.gp-bottomnav{display:none}
/* ── Top App Bar (mobile, Material 3 "small top app bar") — a NEW element
   scoped to this page only, not a rework of the shared .site-head used by
   every other generated page. It sits above the sticky quicknav so a user
   mid-scroll always knows which of the 6 gobarska-napoved/ pages they're on
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
  .gp-quicknav-wrap{top:3rem}
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
.gp-map-attr{font-size:.72rem;color:var(--muted);margin-top:.2rem}
.gp-map-attr a{color:var(--muted)}
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
.gp-map-pop .sp-list{list-style:none;margin:.3rem 0 0;padding:0;font-size:.8rem;line-height:1.5}
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
  .gp-forests,.gp-hub,.gp-vs-grid,.gp-terrmap{grid-template-columns:1fr;gap:.7rem}
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
  function explainCardsHtml(day, meta){
    return day.species.slice(0,6).map(function(s){var m=meta[s.id]||{};
      var dblHtml=m.doubles?('<span class="dbl">⚠ dvojnica: '+esc2(m.doubles)+'</span>'):'';
      return `<div class="gp-explain-card">
        <div class="gp-explain-photo"><img src="/gobarska-napoved/img/vrste/${s.id}.jpg" loading="lazy" alt=""
          onerror="this.replaceWith(document.createTextNode('🍄'))"></div>
        <div class="gp-explain-body">
        <div class="gp-explain-name">${esc2(m.name_sl||s.id)}</div>
        <div class="gp-explain-idx" style="color:${levelColor(s.index)}">${s.index} %</div>
        <details class="gp-explain-more"><summary></summary><p>${esc2(s.explanation)}${dblHtml}</p></details>
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
  function forestRowHtml(l, dayIdx, meta){
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
    return '<div class="gp-forest gp-forest-premium">'+
      '<div class="gp-forest-top"><div class="gp-forest-namewrap">'+
      '<span class="gp-forest-nm">'+(TERR_ICON[l.terrain]||"🌲")+' '+esc2(l.name)+'</span>'+
      '<span class="gp-terr">'+(l.terrain||'')+' · '+l.elev_m+' m</span></div>'+
      '<div class="gp-forest-pct '+pctCls+'"><span class="n">'+o.overall+'%</span><span class="lvl">'+o.level+'</span></div>'+
      '</div>'+
      '<div class="gp-forest-sp3">'+spHtml+'</div>'+
      '<div class="gp-forest-bottom"><div class="gp-forest-meta">'+metaHtml+'</div>'+
      '<div class="gp-forest-spark">'+sparklineSvg(l.days.map(function(dd){return dd.overall;}),"#c17f3e")+'</div>'+
      '</div></div>';
  }
  function forestsListHtml(locs, dayIdx, meta){
    return locs.slice().sort(function(a,b){return b.days[dayIdx].overall-a.days[dayIdx].overall;})
      .map(function(l){return forestRowHtml(l,dayIdx,meta);}).join('');
  }
  function locDetailHtml(loc, meta){
    var html="";
    var top=loc.days[0].species.slice(0,8).map(function(s){return s.id;});
    html+='<h3>'+esc2(loc.name)+' — 7-dnevna napoved</h3>';
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
    if(chipRow){chipRow.addEventListener("click",function(e){
      var btn=e.target.closest(".gp-chip");
      if(!btn)return;
      chipRow.querySelectorAll(".gp-chip").forEach(function(c){c.classList.remove("active");});
      btn.classList.add("active");
      btn.scrollIntoView({inline:"center",block:"nearest",behavior:"smooth"});
      var newLoc=locs[parseInt(btn.dataset.i,10)];
      detail.innerHTML=locDetailHtml(newLoc, meta);
      wireDayChips(detail, newLoc, meta);
    });}
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
          var html=(d.candidates||[]).map(function(c){
            var confCls=CONF_CLS[c.confidence]||"mid";
            return '<div class="gp-id-card"><div class="gp-id-head"><span><span class="gp-id-name">'+
              esc2(c.name_sl||"?")+'</span><span class="gp-id-lat">'+esc2(c.name_lat||"")+'</span></span>'+
              '<span class="gp-id-conf '+confCls+'">zanesljivost: '+esc2(c.confidence||"?")+'</span></div>'+
              (c.edibility?'<div class="gp-id-reason"><b style="color:var(--text)">'+esc2(c.edibility)+'</b></div>':'')+
              (c.reasoning?'<div class="gp-id-reason">'+esc2(c.reasoning)+'</div>':'')+
              (c.warning?'<div class="gp-id-warn">⚠ '+esc2(c.warning)+'</div>':'')+'</div>';
          }).join("");
          if(d.note)html+='<div class="gp-id-note">'+esc2(d.note)+'</div>';
          if(!html)html='<div class="gp-id-note">AI ni prepoznal gobe na fotografiji. Poskusi z bolj ostro sliko klobuka in trosovnice.</div>';
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
  var navPricing=document.getElementById("gp-nav-pricing");
  var heroUnlock=document.getElementById("gp-hero-unlock");
  function hidePricing(){
    if(pricingWrap)pricingWrap.hidden=true;
    if(navPricing)navPricing.hidden=true;
    if(heroUnlock)heroUnlock.hidden=true;
  }
  function skeletonHtml(){
    var block=function(h){return '<div class="gp-loadskel" style="height:'+h+'"></div>';};
    return '<div class="gp-loadskel-group">'+block('1.4rem')+block('5.2rem')+block('5.2rem')+
      block('2.6rem')+block('9rem')+block('9rem')+'</div>';
  }
  var t=tok();
  if(t){
    // A paying user shouldn't see the "Naroči se" upsell while their own
    // data is still in flight — swap straight to a skeleton instead of
    // flashing the paywall first.
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
      .then(function(d){render(d);initIdentify(t);})
      .catch(function(){
        // Token turned out to be invalid/expired or the fetch genuinely
        // failed — fall back to the real paywall instead of leaving the
        // skeleton spinning forever.
        if(content){content.hidden=true;content.innerHTML="";}
        if(lock)lock.hidden=false;
      });
  }
  var f=document.getElementById("gp-login");
  if(f){f.addEventListener("submit",function(e){e.preventDefault();
    var msg=document.getElementById("gp-login-msg");var em=(f.email.value||"").trim();
    if(!em){return;}msg.textContent="Pošiljam …";
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
      var priceId=cfg?cfg.prices[plan]:null;
      if(!ready||!priceId){
        // Fallback: not configured yet — go to pricing, don't break the page.
        var p=document.getElementById("pricing");
        if(p){e.preventDefault();p.scrollIntoView({behavior:"smooth"});
          checkoutMsg("Spletno plačilo bo kmalu na voljo. Za dostop lahko medtem pišeš na filip.eremita@gmail.com.");}
        return;
      }
      e.preventDefault();
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

  // Section accordions (Geološki tereni / Nasveti / Dnevnik) default closed;
  // auto-open + jump when the quicknav links straight to one via #hash.
  function openHashSection(){
    var id=location.hash.slice(1);
    if(!id)return;
    var el=document.getElementById(id);
    if(el&&el.tagName==="DETAILS")el.open=true;
  }
  openHashSection();
  window.addEventListener("hashchange",openHashSection);
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


GOBE_HUB = [
    # (url slug, icon, title, one-line teaser, quicknav label, thumbnail)
    ("zemljevid",  "🗺️", "Zemljevid območij",    "16 nabiralnih območij na interaktivni karti doline.", "🗺️ Zemljevid",
     "gozdna-pot-dron.jpg"),
    ("koledar",    "📅", "Koledar po mesecih",   "Katere užitne vrste so v sezoni — mesec za mesecem.", "📅 Koledar",
     "gozd-mah-banner.jpg"),
    ("trend",      "📊", "Sezonski trend",       "Letos vs. pretekla leta — backtest zadnjih 5 sezon.", "📊 Trend",
     "sluzavke-banner.jpg"),
    ("baza-vrst",  "📖", "Baza 51 vrst",         "Užitnost, sezona in nevarne dvojnice za vsako vrsto.", "📖 Baza vrst",
     "megla-jutro-banner.jpg"),
    ("dvojnice",   "⚠️", "Nevarne dvojnice",     "46 fotografij: užitna vrsta ob strupeni dvojnici.", "⚠️ Dvojnice",
     "sluzavka-portret.jpg"),
]


def hub_cards_html():
    cards = "\n".join(
        f'    <a class="gp-hub-card" href="/gobarska-napoved/{slug}/">'
        f'<div class="gp-hub-photo"><img src="/gobarska-napoved/img/foto/{thumb}" loading="lazy" alt=""></div>'
        f'<div class="gp-hub-body"><span class="gp-hub-ic">{ic}</span><span class="gp-hub-title">{_esc(title)}</span>'
        f'<span class="gp-hub-sub">{_esc(sub)}</span><span class="gp-hub-arrow">Odpri →</span></div></a>'
        for slug, ic, title, sub, _, thumb in GOBE_HUB
    )
    return f'  <div class="gp-hub">\n{cards}\n  </div>'


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
# show. Kept separate from the top gp-quicknav (in-page section jumps).
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


def subpage_shell(slug, title, desc, crumb_label, inner_html, extra_js=""):
    """Shared chrome for the 4 gobarska-napoved/<slug>/ reference subpages —
    same header/footer/brand/back-link as the main page, own URL + meta."""
    url = f"/gobarska-napoved/{slug}/"
    schema = "\n".join([
        seo.webpage_schema(url, title, desc),
        seo.crumbs_schema([("Meteorec", "/"), ("Gobarska napoved", "/gobarska-napoved/"), (crumb_label, None)]),
    ])
    head_extras = schema + "\n" + PAGE_CSS
    body = f'''{BRAND_SWAP}
{top_bar_html(crumb_label, "/gobarska-napoved/")}
{seo.crumbs_html([("Meteorec", "/"), ("Gobarska napoved", "/gobarska-napoved/"), (crumb_label, None)])}
{seo.stn_badge()}
  <h1 class="page-title">{title}</h1>
{inner_html}
  <a class="back-link" href="/gobarska-napoved/">← Nazaj na gobarsko napoved</a>
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


def build_baza_vrst_page(species_table, species_count, vrste_credits_html):
    body = ('''  <figure class="gp-banner">
    <img src="/gobarska-napoved/img/foto/megla-jutro-banner.jpg" loading="lazy" width="1400" height="600"
      alt="Jutranja megla nad gozdovi Zgornje Savinjske doline">
    <figcaption>📷 Avtorski posnetek — jutranja inverzija nad gozdovi doline</figcaption>
  </figure>
  <p class="post-meta">Referenčni pregled najpogostejših gob doline z oznako užitnosti in ključno razliko '''
            'do nevarnih dvojnic. <strong>Nikoli ne uživaj gobe, ki je ne poznaš 100 %.</strong></p>\n'
            + species_table + "\n" + vrste_credits_html)
    return subpage_shell(
        "baza-vrst", f"Baza {species_count} vrst gob — užitnost in nevarne dvojnice",
        f"Referenčna baza {species_count} vrst gob Zgornje Savinjske doline: užitnost, sezona in nevarne dvojnice.",
        "Baza vrst", body)


def build_dvojnice_page(vs_html, vs_count, credits_html):
    body = ('''  <figure class="gp-photo-card">
    <img src="/gobarska-napoved/img/foto/sluzavka-portret.jpg" loading="lazy" width="640" height="853"
      alt="Avtorski makro posnetek sluzavke v gozdu">
    <figcaption>📷 Avtorski makro posnetek — tudi navidez podobne gobe znajo biti povsem različne vrste</figcaption>
  </figure>
'''
            '  <p class="post-meta">Užitna vrsta ob strupeni ali neužitni dvojnici, s ključno razliko za varno '
            'ločevanje. <strong>Ob dvomu gobe nikoli ne uživaj.</strong></p>\n'
            + vs_html + "\n" + credits_html)
    return subpage_shell(
        "dvojnice", "Nevarne dvojnice gob — primerjava s fotografijami",
        f"{vs_count} primerjav užitnih vrst z nevarnimi dvojnicami, s fotografijami in ključno razliko za varno "
        "ločevanje.",
        "Nevarne dvojnice", body)


def build_zemljevid_page(premium, rules):
    """Interactive Leaflet map of all foraging + protected areas, coloured by
    today's index. Data is baked in (no client fetch) — Leaflet itself loads
    lazily on first click, mirroring the site's storm-map pattern."""
    meta = premium["species_meta"]
    pts = []
    for loc in premium["locations"]:
        d0 = loc["days"][0]
        top3 = d0.get("species", [])[:3]
        pts.append({
            "name": loc["name"], "lat": loc["lat"], "lon": loc["lon"],
            "elev": loc["elev_m"], "terrain": loc.get("terrain"),
            "idx": d0["overall"], "lvl": d0["level"],
            "sp": [meta[s["id"]]["name_sl"] for s in top3 if s["id"] in meta],
            "prot": False,
        })
    for loc in rules.get("locations", []):
        if loc.get("protected"):
            pts.append({
                "name": loc["name"], "lat": loc["lat"], "lon": loc["lon"],
                "elev": loc.get("elev_m"), "terrain": loc.get("terrain"),
                "idx": None, "lvl": None, "sp": [], "prot": True,
            })
    data_js = _json_mod.dumps(pts, ensure_ascii=False)
    pick_count = sum(1 for p in pts if not p["prot"])

    inner = f'''  <figure class="gp-photo-card">
    <img src="/gobarska-napoved/img/foto/gozdna-pot-dron.jpg" loading="lazy" width="640" height="853"
      alt="Dronski posnetek gozdne poti v Zgornji Savinjski dolini">
    <figcaption>📷 Avtorski dronski posnetek — gozdna pot skozi eno od nabiralnih območij</figcaption>
  </figure>
  <p class="post-meta">Vseh {pick_count} nabiralnih območij Zgornje Savinjske doline na eni karti,
  obarvanih po <strong>današnjem gobarskem indeksu</strong>. Klikni oznako za podrobnosti. Zaščitena območja
  (nabiranje prepovedano) so označena posebej. Oznake so <strong>širša območja</strong>, ne točne najdbe.</p>
  <div class="gp-map-legend">
    <span><i style="background:#34d399"></i>Dobra/odlična (≥55 %)</span>
    <span><i style="background:#f59e0b"></i>Zmerna (35–54 %)</span>
    <span><i style="background:#fb923c"></i>Slaba (18–34 %)</span>
    <span><i style="background:#f87171"></i>Brez (&lt;18 %)</span>
    <span><i style="background:#a78bfa"></i>Zaščiteno</span>
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
  Leaflet se naloži šele ob kliku (s storitve unpkg.com).</p>'''

    map_js = '''<script>
(function(){
  var PTS=''' + data_js + ''';
  var hint=document.getElementById("gp-map-hint");
  var mapEl=document.getElementById("gp-map");
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
      h+='<div class="sp" style="color:#c4b5fd;margin-top:.35rem">🚫 Zaščiteno — nabiranje prepovedano</div>';
    }else{
      h+='<div style="margin-top:.35rem"><span class="idx" style="color:'+levelColor(p.idx)+'">'+p.idx+' %</span> · '+esc(p.lvl)+'</div>';
      if(p.sp&&p.sp.length)h+='<ul class="sp-list">'+p.sp.map(function(s){return'<li>🍄 '+esc(s)+'</li>';}).join('')+'</ul>';
    }
    h+='</div>';
    return h;
  }
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
      var group=[];
      PTS.forEach(function(p){
        var m=L.circleMarker([p.lat,p.lon],{
          radius:p.prot?7:9,color:"#0b0906",weight:1.5,
          fillColor:levelColor(p.idx),fillOpacity:p.prot?.55:.9
        }).addTo(map);
        m.bindPopup(popupHtml(p));
        m.bindTooltip(p.name,{direction:"top",offset:[0,-6]});
        group.push(m);
      });
      if(group.length){
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
})();
</script>'''

    return subpage_shell(
        "zemljevid", "Zemljevid nabiralnih območij — Zgornja Savinjska dolina",
        f"Interaktivni zemljevid {pick_count} nabiralnih območij Zgornje Savinjske doline, obarvanih po današnjem "
        "gobarskem indeksu. Vključuje zaščitena območja, kjer je nabiranje prepovedano.",
        "Zemljevid", inner, extra_js=map_js)


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
    hero = f'''  <div class="gp-hero">
    <div class="gp-hero-top">
      <div class="gp-gauge-wrap">
        {gauge_svg(pct)}
        <div class="gp-gauge-num"><span class="num">{pct}</span><small>%</small></div>
      </div>
      <div class="gp-hero-body">
        <div class="gp-hero-kicker">Gobarski indeks danes · Rečica ob Savinji</div>
        <div class="gp-hero-lvl" style="color:{level_color(pct)}">{lvl}</div>
        <div class="gp-hero-best">🌲 Najugodnejši gozd danes: <strong>{_esc(best_loc["name"])}</strong>
          <span class="gp-hero-best-pct" style="background:{level_color(best_o["overall"])}22;color:{level_color(best_o["overall"])}">{best_o["overall"]} % · {best_o["level"]}</span></div>
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
    nočno ohladitev — po vrstah in po geologiji terena.</div>
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
      <div class="gp-forest-pct {pct_cls}"><span class="n">{o["overall"]}%</span><span class="lvl">{o["level"]}</span></div>
    </div>''')
    if premium.get("protected_areas"):
        forests.append(
            f'''    <div class="gp-forest gp-forest-prot">
      <div class="gp-forest-info">
        <span class="gp-forest-nm">🚫 {_esc(", ".join(premium["protected_areas"]))}</span>
        <span class="gp-terr">zaščiteno</span>
        <span class="gp-forest-sp">Nabiranje prepovedano</span>
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
  <div id="gp-lock" class="gp-lock">
    <span class="gp-tag">🔒 PREMIUM</span>
    <h3>7-dnevna napoved po vrstah in gozdovih</h3>
    <p class="gp-hero-sub">Za vsak dan naslednjega tedna in vsako od {len(premium["locations"])} nabiralnih območij:
    indeks po posameznih vrstah, plastovita razlaga (»talna temp. optimalna, padavine pod pragom, nočna ohladitev zaznana«)
    in opozorila na nevarne dvojnice. Vključuje tudi <b>🔍 AI prepoznavo gobe iz fotografije</b>.</p>
    <div class="gp-skel">
{skel_rows}
    </div>
    <div class="gp-lockbar">
      <button type="button" class="gp-cta" data-paddle="monthly">Naroči se ({PRICE_MONTHLY}/mes)</button>
      <button type="button" class="gp-cta alt" data-paddle="season">Sezonski dostop ({PRICE_SEASON})</button>
    </div>
    <form id="gp-login" class="gp-login" autocomplete="email">
      <input type="email" name="email" placeholder="Že plačano? Vpiši e-naslov za povezavo" required>
      <button type="submit">Pošlji povezavo</button>
    </form>
    <div id="gp-login-msg" class="gp-msg"></div>
  </div>'''

    # ── pricing ───────────────────────────────────────────────────────────────
    pricing = f'''  <div id="gp-pricing-wrap">
  <h2 id="pricing" class="gp-h2">🎟️ Naročnina</h2>
  <div class="gp-pricing">
    <div class="gp-plan">
      <span class="gp-tag">MESEČNO</span>
      <div class="p-price">{PRICE_MONTHLY}<small> / mesec</small></div>
      <ul>
        <li>7-dnevna napoved po vrstah</li>
        <li>Indeks za vsa nabiralna območja</li>
        <li>Razlage in opozorila na dvojnice</li>
        <li>🔍 AI prepoznava gobe iz fotografije</li>
        <li>Prekliči kadarkoli</li>
      </ul>
      <button type="button" class="gp-cta" data-paddle="monthly">Naroči se</button>
    </div>
    <div class="gp-plan best">
      <span class="gp-tag">CELA SEZONA · najugodneje</span>
      <div class="p-price">{PRICE_SEASON}<small> / sezona</small></div>
      <ul>
        <li>Vse iz mesečnega paketa (vklj. 🔍 AI prepoznavo)</li>
        <li>Dostop do konca sezone (30. 11.)</li>
        <li>Enkratno plačilo, brez obnavljanja</li>
        <li>Podpora lokalnemu projektu</li>
      </ul>
      <button type="button" class="gp-cta" data-paddle="season">Kupi sezono</button>
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

    # ── 50-species reference cards (free, SEO + credibility) ──────────────────
    # Card top-half shows a real photo once one exists at img/vrste/<id>.jpg;
    # until then onerror swaps it for an edibility-tinted placeholder, so
    # photos can be dropped in later species-by-species with no code change
    # (same graceful-fallback trick as the /dvojnice/ comparison cards).
    sp_cards = []
    for s in sorted(species, key=lambda x: (not x.get("gets_index"), x["name_sl"])):
        se = s["season"]
        season_txt = f'{se["start"]}–{se["end"]}'
        edib = (s.get("edibility") or "").lower().strip()
        cls = EDIB_STYLE.get(edib, (None, "e-none"))[1]
        dbl = s.get("doubles")
        dbl_html = (f'<div class="gp-sp-dbl"><b>Dvojnica:</b> {_esc(dbl)}</div>' if dbl else "")
        sp_cards.append(f'''    <div class="gp-sp-card">
      <div class="gp-sp-top {cls}">
        <img src="/gobarska-napoved/img/vrste/{s['id']}.jpg" alt="{_esc(s['name_sl'])}" loading="lazy"
          onerror="this.parentElement.classList.add('ph');this.remove()">
        <span class="gp-sp-emoji">🍄</span>
      </div>
      <div class="gp-sp-body">
        <div class="gp-sp-name">{_esc(s["name_sl"])}</div>
        <div class="gp-sp-lat">{_esc(s["name_lat"])}</div>
        <div class="gp-sp-row">{edib_badge(s.get("edibility"))}<span class="gp-sp-season">📅 {season_txt}</span></div>
        {dbl_html}
      </div>
    </div>''')
    species_table = '  <div class="gp-sp-grid">\n' + "\n".join(sp_cards) + "\n  </div>"

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
        badge = edib_badge(danger)
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
    vrste_credits_html = photo_credits_html("vrste")

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
         "temperatura in vlaga tal, kumulativne padavine, zračna vlaga in nočna ohladitev, uteženo po vrsti in "
         "geologiji terena. Gozd ima vedno zadnjo besedo; visok indeks pomeni ugodne razmere, ne zajamčene gobe."),
        ("Katere vrste zajema premium napoved?",
         "Napoved po vrstah pokriva užitne in pogojno užitne gobe iz lokalne baze Zgornje Savinjske doline. "
         "Strupene vrste se pojavijo le kot opozorilo na nevarne dvojnice ob pripadajoči užitni vrsti."),
        ("Zakaj se indeks razlikuje med gozdovi?",
         "Model upošteva geologijo: kislo vulkansko pogorje Smrekovca ustreza jurčkom in žametastemu gobanu, "
         "karbonatni masivi Golte in Menine pa marelam in poletnemu gobanu. Zato ista vrsta isti dan ni enako "
         "verjetna povsod."),
        ("Kako plačam in dostopam?",
         "Plačilo obdela Paddle. Po nakupu prejmeš na e-naslov povezavo za dostop, ki deluje na vseh napravah — "
         "brez ustvarjanja računa in gesla. Če izgubiš povezavo, jo z istim e-naslovom kadarkoli zahtevaš znova."),
        ("Koliko gob smem nabrati?",
         "V Sloveniji je dovoljeno nabrati do 2 kg gob na osebo na dan (Uredba o varstvu samoniklih gliv). "
         "Logarska dolina, Robanov in Matkov kot so zaščitena območja — nabiranje je tam prepovedano."),
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

    body = f'''{BRAND_SWAP}
{top_bar_html("Gobarska napoved", None)}
{seo.crumbs_html([("Meteorec", "/"), ("Gobarska napoved", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Gobarska napoved — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Model rasti gob po vrstah · lokalna baza {len(species)} vrst · osvežuje se dnevno · {TODAY.isoformat()}</p>
{hero}
  <div class="gp-quicknav-wrap">
  <nav class="gp-quicknav" aria-label="Hitri meni">
    <a href="#gozdovi">🌲 Gozdovi</a>
    <a href="#premium">🔓 Premium</a>
    <a href="#pricing" id="gp-nav-pricing">🎟️ Cenik</a>
    <a href="/gobarska-napoved/koledar/">📅 Koledar</a>
    <a href="/gobarska-napoved/trend/">📊 Trend</a>
    <a href="/gobarska-napoved/baza-vrst/">📖 Baza vrst</a>
    <a href="/gobarska-napoved/dvojnice/">⚠️ Dvojnice</a>
    <a href="#tereni">🗺️ Tereni</a>
    <a href="#nasveti">📋 Nasveti</a>
    <a href="#dnevnik">📔 Dnevnik</a>
    <a href="#faq">❓ FAQ</a>
  </nav>
  </div>
  <h2 class="gp-h2" id="gozdovi">🌲 Danes po gozdovih</h2>
  <p class="archive-intro">Gobarski indeks za nabiralna območja Zgornje Savinjske doline, izračunan iz istih vhodnih
  podatkov (vlaga in temperatura tal, padavine, zračna vlaga) ter geologije terena.</p>
{forests_html}
  <h2 class="gp-h2" id="premium">🔓 Premium: 7-dnevna napoved po vrstah</h2>
{premium_block}
{pricing}
  <h2 class="gp-h2">🗂️ Več o dolini in gobah</h2>
  <p class="archive-intro">Koledar sezone, večletni trend, celotna baza vrst in primerjava nevarnih dvojnic —
  vsaka na svoji strani, da glavna stran ostane pregledna.</p>
{hub_cards_html()}
  <details class="gp-collapse gp-collapse-section" id="tereni">
  <summary>🗺️ Geološki tereni doline</summary>
  <div class="gp-collapse-body">
  <p class="archive-intro">Podlaga odloča, kaj raste: model za vsako vrsto upošteva afiniteto do terena.</p>
{terrain_html}
  </div>
  </details>
  <details class="gp-collapse gp-collapse-section" id="nasveti">
  <summary>📋 Nasveti in pravila</summary>
  <div class="gp-collapse-body">
  <div class="card" style="margin:1rem 0">
    <div style="font-size:.85rem;color:var(--muted);line-height:1.7">
      ⚖️ Do <b>2 kg gob na osebo na dan</b> (Uredba o varstvu samoniklih gliv).<br>
      🧺 Gobe nosi v zračni košari, ne v vrečki — trosi se tako raznašajo.<br>
      🔪 Gobo izvij ali odreži pri dnu in mesto rahlo prekrij.<br>
      ☠️ <b>Nikoli ne uživaj gobe, ki je ne poznaš 100 %.</b> Ob dvomu vprašaj gobarsko društvo ali mikologa.<br>
      🚫 Logarska dolina, Robanov in Matkov kot: <b>zaščiteno — nabiranje prepovedano.</b>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="https://www.gobe.si/" target="_blank" rel="noopener" class="mtn-avk-link">🍄 Gobe.si</a>
      <a href="https://www.gobarskazveza.si/" target="_blank" rel="noopener" class="mtn-avk-link">🇸🇮 Gobarska zveza Slovenije</a>
      <a href="https://meteo.arso.gov.si/met/sl/agromet/" target="_blank" rel="noopener" class="mtn-avk-link">🌱 ARSO — agrometeorologija</a>
    </div>
  </div>
  </div>
  </details>
  <details class="gp-collapse gp-collapse-section" id="dnevnik">
  <summary>📔 Gobarjev dnevnik</summary>
  <div class="gp-collapse-body">
{diary_html}
  </div>
  </details>
{faq_html}
  <p class="gp-disc">Napoved je <strong>indeks ugodnosti pogojev</strong>, ne obljuba najdbe. Pripravlja jo Filip Eremita
  (gozdarstvo/mikologija) iz meritev postaje IREICA1 in podatkov Open-Meteo. Ni uradna napoved ARSO.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>
  <button type="button" class="gp-sos-fab" id="gp-sos-btn" aria-label="Sum zastrupitve z gobami — pomoč">🆘</button>
  <div class="gp-sos-panel" id="gp-sos-panel">
    <h4>Sum zastrupitve z gobami?</h4>
    <p>Ob težavah z dihanjem, hudi omotici ali izgubi zavesti pokliči takoj <b>112</b>. Za posvet o zaužiti gobi
    (tudi če se počutiš še dobro — nekateri simptomi pridejo z zamikom) pokliči Center za zastrupitve.</p>
    <a class="gp-sos-call" href="tel:112">🚨 112 <small>Nujna medicinska pomoč</small></a>
    <a class="gp-sos-call alt" href="tel:+38615225283">☎️ (01) 522 52 83 <small>Center za zastrupitve UKC Ljubljana · 24 ur</small></a>
    <p style="margin-bottom:0">Vzemi s seboj vzorec gobe (cela, s trosovnico) — pomaga pri določitvi vrste.</p>
  </div>
{bottom_nav_html("")}
{PAGE_JS}
{DIARY_JS}'''
    subpages = {
        "cal_data": cal_data, "month": month,
        "species_table": species_table, "species_count": len(species),
        "vs_html": vs_html, "vs_count": len(vs_cards),
        "credits_html": credits_html, "vrste_credits_html": vrste_credits_html,
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
    build_baza_vrst_page(sub["species_table"], sub["species_count"], sub["vrste_credits_html"])
    build_dvojnice_page(sub["vs_html"], sub["vs_count"], sub["credits_html"])
    print(f"  → 5 podstrani (zemljevid, koledar, trend, baza-vrst, dvojnice)")

    url = "/gobarska-napoved/"
    title = "Gobarska napoved — Zgornja Savinjska dolina"
    desc = (f"Gobarski indeks danes: {free['index']} % ({free['level']}). Napoved rasti gob po vrstah za "
            f"Zgornjo Savinjsko dolino — 7-dnevni premium model, baza {len(rules['species'])} vrst, "
            f"nevarne dvojnice in gobarski koledar.")

    qa_for_schema = [
        ("Je gobarski indeks napoved najdbe?",
         "Ne. Indeks je ocena ugodnosti vremenskih in talnih pogojev za rast, ne obljuba najdbe."),
        ("Katere vrste zajema premium napoved?",
         "Užitne in pogojno užitne gobe Zgornje Savinjske doline; strupene le kot opozorilo na dvojnice."),
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
