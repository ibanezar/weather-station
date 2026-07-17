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

PAGE_CSS = """<style>
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
}
.gp-hero{position:relative;overflow:hidden;border:1px solid var(--card-border);border-radius:18px;
  padding:1.6rem;margin:.6rem 0 1.4rem;box-shadow:var(--card-shadow);
  background:linear-gradient(135deg,rgba(8,14,7,.82),rgba(6,10,6,.94)),url('/og/bg/misty-valley.jpg') center/cover}
.gp-hero-top{display:flex;align-items:center;gap:1.4rem;flex-wrap:wrap}
.gp-gauge-wrap{position:relative;width:132px;height:132px;flex:0 0 auto}
.gp-ring{display:block}
.gp-ring-bg{fill:none;stroke:rgba(255,255,255,.10);stroke-width:11}
.gp-ring-fg{fill:none;stroke-width:11;stroke-linecap:round;transform:rotate(-90deg);transform-origin:64px 64px}
.gp-gauge-num{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:2.7rem;font-weight:800;color:var(--text)}
.gp-gauge-num small{font-size:1rem;color:var(--muted);font-weight:600;margin-left:2px}
.gp-hero-body{flex:1;min-width:250px}
.gp-hero-kicker{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.gp-hero-lvl{font-size:1.9rem;font-weight:800;line-height:1.1;margin:.1rem 0 .55rem}
.gp-hero-best{font-size:.95rem;color:var(--text);margin-bottom:.75rem}
.gp-hero-best-pct{display:inline-block;font-weight:700;font-size:.8rem;padding:.05rem .45rem;
  border-radius:6px;margin-left:.25rem;font-variant-numeric:tabular-nums}
.gp-hero-note{color:var(--muted);font-size:.85rem;line-height:1.55;margin-top:1rem;
  border-top:1px solid rgba(255,255,255,.09);padding-top:.85rem}
.gp-hero-sub{color:var(--muted);font-size:.9rem;margin-top:.35rem;line-height:1.55}
.gp-h2{margin-top:1.7rem;padding-bottom:.3rem;border-bottom:1px solid var(--border)}
.gp-cta{display:inline-block;background:var(--blue);color:#04070e;font:inherit;
  font-weight:700;padding:.6rem 1.2rem;border-radius:10px;text-decoration:none;margin-top:.4rem;
  border:0;cursor:pointer;line-height:1.2}
.gp-cta-lg{padding:.7rem 1.4rem;font-size:1rem}
.gp-cta.alt{background:transparent;color:var(--blue);border:1px solid var(--blue)}
.gp-forests{display:grid;gap:.6rem;margin:.6rem 0 1.2rem}
.gp-forest{background:var(--fc-bg);border:1px solid var(--fc-border);border-radius:12px;padding:.7rem .9rem}
.gp-forest-head{display:flex;align-items:baseline;justify-content:space-between;gap:.6rem;margin-bottom:.45rem}
.gp-forest-nm{font-weight:700;font-size:.95rem}
.gp-meter{position:relative;height:22px;background:rgba(255,255,255,.06);border-radius:7px;overflow:hidden}
.gp-meter-fill{position:absolute;left:0;top:0;bottom:0;border-radius:7px;transition:width .6s ease}
.gp-meter-val{position:absolute;right:.5rem;top:50%;transform:translateY(-50%);font-size:.75rem;
  font-weight:700;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.6);font-variant-numeric:tabular-nums}
.gp-forest-sp{font-size:.82rem;color:var(--muted);margin-top:.45rem}
.gp-forest-prot{opacity:.6}
.gp-terr{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.gp-lock{position:relative;border:1px dashed var(--card-border);border-radius:16px;
  padding:1.3rem;margin:.6rem 0 1rem;background:linear-gradient(180deg,rgba(77,159,248,.06),transparent)}
.gp-lock h3{margin:.1rem 0 .3rem}
.gp-skel{filter:blur(4px);opacity:.5;pointer-events:none;user-select:none;margin:.7rem 0;display:grid;gap:.5rem}
.gp-skel .gp-forest{background:var(--badge-bg);display:flex;justify-content:space-between}
.gp-lockbar{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-top:.8rem}
.gp-login{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.6rem}
.gp-login input{flex:1;min-width:180px;background:var(--badge-bg);border:1px solid var(--card-border);
  border-radius:9px;padding:.5rem .7rem;color:var(--text);font-size:.9rem}
.gp-login button{background:var(--blue);color:#04070e;border:0;border-radius:9px;
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
.gp-disc{font-size:.82rem;color:var(--muted);border-left:3px solid var(--amber);padding:.3rem .8rem;margin:1rem 0}

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
.gp-vs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.8rem;margin:.7rem 0 1rem}
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
.gp-diary-btn{background:var(--badge-bg);border:1px solid var(--card-border);color:var(--text);
  border-radius:9px;padding:.5rem .8rem;font-size:.85rem;font-weight:600;cursor:pointer}
.gp-diary-photobtn{display:inline-block}
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
  function hexToRgb(h){h=h.replace('#','');return[parseInt(h.substr(0,2),16),parseInt(h.substr(2,2),16),parseInt(h.substr(4,2),16)];}
  function render(d){
    var meta=d.species_meta||{};
    var home=(d.locations||[]).filter(function(l){return l.home;})[0]||d.locations[0];
    var html="";
    // today per forest — same bar-meter cards as the free section
    html+='<h3>Danes po gozdovih</h3><div class="gp-forests">';
    (d.locations||[]).slice().sort(function(a,b){return b.days[0].overall-a.days[0].overall;})
      .forEach(function(l){var o=l.days[0];var top=o.species[0];var col=levelColor(o.overall);
        html+='<div class="gp-forest"><div class="gp-forest-head"><span class="gp-forest-nm">'+
          (TERR_ICON[l.terrain]||"🌲")+' '+l.name+'</span><span class="gp-terr">'+(l.terrain||'')+
          ' · '+l.elev_m+' m</span></div><div class="gp-meter"><div class="gp-meter-fill" style="width:'+
          Math.max(3,o.overall)+'%;background:'+col+'"></div><span class="gp-meter-val">'+o.overall+' % · '+
          o.level+'</span></div><div class="gp-forest-sp">🍄 '+(top&&meta[top.id]?meta[top.id].name_sl:'—')+
          '</div></div>';});
    html+='</div>';
    // 7-day matrix for home, top 8 species by today's index
    var top=home.days[0].species.slice(0,8).map(function(s){return s.id;});
    html+='<h3>'+home.name+' — 7-dnevni indeks po vrstah</h3>';
    html+='<div class="gp-legend"><span><i style="background:#34d399"></i>Dobra/odlična (≥55%)</span>'+
      '<span><i style="background:#f59e0b"></i>Zmerna (35–54%)</span>'+
      '<span><i style="background:#fb923c"></i>Slaba (18–34%)</span>'+
      '<span><i style="background:#f87171"></i>Brez (&lt;18%)</span></div>';
    html+='<div class="gp-scroll"><table class="gp-matrix"><thead><tr><th style="text-align:left">Vrsta</th>';
    home.days.forEach(function(day){var dt=new Date(day.date);
      html+='<th>'+(day===home.days[0]?'danes':(dt.getDate()+'.'+(dt.getMonth()+1)+'.'))+'</th>';});
    html+='</tr></thead><tbody>';
    top.forEach(function(id){html+='<tr><td class="nm">'+(meta[id]?meta[id].name_sl:id)+'</td>';
      home.days.forEach(function(day){var s=day.species.filter(function(x){return x.id===id;})[0];
        var v=s?s.index:0;var c=levelColor(v);var rgb=hexToRgb(c);
        var alpha=(0.12+0.55*Math.min(100,v)/100).toFixed(2);
        html+='<td><span class="gp-cell" style="background:rgba('+rgb.join(',')+','+alpha+');color:'+c+'">'+v+'</span></td>';});
      html+='</tr>';});
    html+='</tbody></table></div>';
    // today's carriers with explanation
    html+='<h3>Danes — zakaj (razlage)</h3><ul style="color:var(--muted);font-size:.88rem;line-height:1.7">';
    home.days[0].species.slice(0,6).forEach(function(s){var m=meta[s.id]||{};
      html+='<li><b style="color:var(--text)">'+(m.name_sl||s.id)+' — '+s.index+'%</b>: '+s.explanation+
        (m.doubles?' <span class="gp-dbl">⚠ dvojnica: '+m.doubles+'</span>':'')+'</li>';});
    html+='</ul>';
    content.innerHTML=html;
    content.hidden=false;lock.hidden=true;
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
  var t=tok();
  if(t){
    fetch(API+"/premium/forecast?token="+encodeURIComponent(t))
      .then(function(r){if(!r.ok)throw 0;return r.json();})
      .then(function(d){render(d);initIdentify(t);
        if(statusEl){statusEl.hidden=false;statusEl.textContent="✓ Premium dostop aktiven.";}})
      .catch(function(){localStorage.removeItem(LS);});
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
    return (f'<svg viewBox="0 0 128 128" class="gp-ring" width="132" height="132" aria-hidden="true">'
            f'<circle cx="64" cy="64" r="{r}" class="gp-ring-bg"/>'
            f'<circle cx="64" cy="64" r="{r}" class="gp-ring-fg" stroke="{color}" '
            f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{off:.1f}"/></svg>')


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
        <div class="gp-gauge-num">{pct}<small>%</small></div>
      </div>
      <div class="gp-hero-body">
        <div class="gp-hero-kicker">Gobarski indeks danes · Rečica ob Savinji</div>
        <div class="gp-hero-lvl" style="color:{level_color(pct)}">{lvl}</div>
        <div class="gp-hero-best">🌲 Najugodnejši gozd danes: <strong>{_esc(best_loc["name"])}</strong>
          <span class="gp-hero-best-pct" style="background:{level_color(best_o["overall"])}22;color:{level_color(best_o["overall"])}">{best_o["overall"]} % · {best_o["level"]}</span></div>
        <a class="gp-cta gp-cta-lg" href="#pricing">Odkleni 7-dnevno napoved po vrstah →</a>
      </div>
    </div>
    <div class="gp-hero-note">Indeks je <strong>ocena ugodnosti pogojev</strong> za rast, ne obljuba najdbe.
    Upošteva temperaturo in vlago tal, kumulativne padavine (lokalno iz postaje IREICA1), zračno vlago in
    nočno ohladitev — po vrstah in po geologiji terena.</div>
  </div>'''

    # ── today per forest (free) — horizontal bar meters ───────────────────────
    forests = ['  <div class="gp-forests">']
    for loc in sorted(premium["locations"], key=lambda l: l["days"][0]["overall"], reverse=True):
        o = loc["days"][0]
        top = o["species"][0]
        top_nm = premium["species_meta"][top["id"]]["name_sl"] if top else "—"
        terr = loc.get("terrain", "")
        t_icon = TERRAIN_STYLE.get(terr, ("", "🌲"))[1]
        col = level_color(o["overall"])
        forests.append(
            f'''    <div class="gp-forest">
      <div class="gp-forest-head"><span class="gp-forest-nm">{t_icon} {_esc(loc["name"])}</span>
        <span class="gp-terr">{terr} · {loc["elev_m"]} m</span></div>
      <div class="gp-meter"><div class="gp-meter-fill" style="width:{max(3, o["overall"])}%;background:{col}"></div>
        <span class="gp-meter-val">{o["overall"]} % · {o["level"]}</span></div>
      <div class="gp-forest-sp">🍄 {_esc(top_nm)}</div>
    </div>''')
    if premium.get("protected_areas"):
        forests.append(
            f'''    <div class="gp-forest gp-forest-prot">
      <div class="gp-forest-head"><span class="gp-forest-nm">🚫 {_esc(", ".join(premium["protected_areas"]))}</span>
        <span class="gp-terr">zaščiteno</span></div>
      <div class="gp-forest-sp">Nabiranje prepovedano</div>
    </div>''')
    forests.append("  </div>")
    forests_html = "\n".join(forests)

    # ── PREMIUM locked block ──────────────────────────────────────────────────
    skel_rows = "\n".join(
        f'      <div class="gp-forest"><span>{_esc(premium["species_meta"][s["id"]]["name_sl"])}</span><b>•• % ······</b></div>'
        for s in home["days"][0]["species"][:5])
    premium_block = f'''  <div id="gp-premium-status" class="gp-msg" hidden></div>
  <div id="gp-content" hidden></div>
  <div id="gp-identify" class="gp-diary" hidden>
    <h3 style="margin-top:0">🔍 AI prepoznava gobe iz fotografije</h3>
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
    pricing = f'''  <h2 id="pricing" class="gp-h2">🎟️ Naročnina</h2>
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
  računa — po plačilu prejmeš povezavo za dostop na svoj e-naslov, ki deluje na vseh napravah.</p>'''

    # ── monthly calendar (free) ───────────────────────────────────────────────
    cal_rows = []
    for m in range(1, 13):
        names = [s["name_sl"] for s in indexed if m in season_months(s)]
        mark = " ←" if m == month else ""
        hi = ' style="background:var(--fc-today-bg)"' if m == month else ""
        joined = ", ".join(names) or "—"
        cal_rows.append(
            f'      <tr{hi}>'
            f'<th>{seo.MES_NOM[m].capitalize()}{mark}</th>'
            f'<td style="text-align:left">{_esc(joined)}</td></tr>')
    calendar_html = ('  <table class="stats">\n' + "\n".join(cal_rows) + "\n  </table>")

    # ── 50-species reference table (free, SEO + credibility) ──────────────────
    sp_rows = []
    for s in sorted(species, key=lambda x: (not x.get("gets_index"), x["name_sl"])):
        se = s["season"]
        season_txt = f'{se["start"]}–{se["end"]}'
        sp_rows.append(
            f'      <tr><td><b>{_esc(s["name_sl"])}</b><br><span class="lat">{_esc(s["name_lat"])}</span></td>'
            f'<td>{edib_badge(s.get("edibility"))}</td>'
            f'<td>{season_txt}</td>'
            f'<td class="gp-dbl">{_esc(s.get("doubles") or "—")}</td></tr>')
    species_table = (
        '  <div class="gp-scroll"><table class="gp-sptable"><thead><tr>'
        '<th>Vrsta</th><th>Užitnost</th><th>Sezona</th><th>Nevarne dvojnice</th></tr></thead><tbody>\n'
        + "\n".join(sp_rows) + "\n  </tbody></table></div>")

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
    faq_html = ("  <h2 class=\"gp-h2\">❓ Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{_esc(q)}</summary><p>{_esc(a)}</p></details>' for q, a in qa
    ) + "\n  </div>")

    # Sub-brand swap: this page shows "MeteoGobar" with its own mushroom mark
    # instead of the site-wide Meteorec logo/name. Done via a tiny synchronous
    # script (runs immediately after the shared header markup is parsed)
    # rather than touching generate_seo_pages.py's shared HEADER template —
    # every other generated page keeps the plain Meteorec header untouched.
    brand_swap = '''<script>(function(){
  var img=document.querySelector(".site-head .brand-logo");
  var nm=document.querySelector(".site-head .brand-name");
  if(img){img.src="/gobarska-napoved/logo-gobar.svg";img.alt="MeteoGobar";}
  if(nm){nm.innerHTML="Meteo<em>Gobar</em>";}
})();</script>'''

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

    body = f'''{brand_swap}
{seo.crumbs_html([("Meteorec", "/"), ("Gobarska napoved", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Gobarska napoved — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Model rasti gob po vrstah · lokalna baza {len(species)} vrst · osvežuje se dnevno · {TODAY.isoformat()}</p>
{hero}
  <h2 class="gp-h2">🌲 Danes po gozdovih</h2>
  <p class="archive-intro">Gobarski indeks za nabiralna območja Zgornje Savinjske doline, izračunan iz istih vhodnih
  podatkov (vlaga in temperatura tal, padavine, zračna vlaga) ter geologije terena.</p>
{forests_html}
  <h2 class="gp-h2">🔓 Premium: 7-dnevna napoved po vrstah</h2>
{premium_block}
{pricing}
  <h2 class="gp-h2">📅 Kaj utegne rasti v {MES_FULL[month - 1]}</h2>
  <p class="archive-intro">Užitne in pogojno užitne vrste, ki so ta mesec v sezoni (iz lokalne baze).</p>
{calendar_html}
  <h2 class="gp-h2">📊 Sezona v primerjavi s preteklimi leti</h2>
  <p class="archive-intro">Mesečno povprečje gobarskega indeksa za Rečico ob Savinji, izračunano nazaj (backtest)
  z zgodovinskimi vremenskimi podatki (ERA5-Land) — zadnjih do 5 let. Letošnja sezona je poudarjena.
  Približek: uporablja podnebni arhiv namesto postajnih meritev, zato se lahko rahlo razlikuje od dnevne napovedi.</p>
  <div id="gp-trend" class="gp-trend-wrap">
    <div class="gp-msg">Nalagam …</div>
  </div>
  <h2 class="gp-h2">📖 Baza {len(species)} vrst — užitnost in nevarne dvojnice</h2>
  <p class="archive-intro">Referenčni pregled najpogostejših gob doline z oznako užitnosti in ključno razliko do
  nevarnih dvojnic. <strong>Nikoli ne uživaj gobe, ki je ne poznaš 100 %.</strong></p>
{species_table}
  <h2 class="gp-h2">⚠️ Nevarne dvojnice — primerjava</h2>
  <p class="archive-intro">Užitna vrsta ob strupeni ali neužitni dvojnici, s ključno razliko za varno ločevanje.
  Fotografije se bodo dodale sproti — do takrat vsaka kartica prikaže ime in besedilno razlago.
  <strong>Ob dvomu gobe nikoli ne uživaj.</strong></p>
{vs_html}
  <h2 class="gp-h2">🗺️ Geološki tereni doline</h2>
  <p class="archive-intro">Podlaga odloča, kaj raste: model za vsako vrsto upošteva afiniteto do terena.</p>
{terrain_html}
  <div class="card" style="margin:1rem 0">
    <div class="clabel">📋 Nasveti in pravila</div>
    <div style="font-size:.85rem;color:var(--muted);line-height:1.7;margin-top:.5rem">
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
  <h2 class="gp-h2">📔 Gobarjev dnevnik</h2>
{diary_html}
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
{PAGE_JS}
{DIARY_JS}
{TREND_JS}'''
    return body


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

    body = build_body(rules, premium, free)

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
