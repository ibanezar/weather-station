#!/usr/bin/env python3
"""
tools/invasive_watch.py — Invazivke-alarm za meteorec.si
----------------------------------------------------------
Vsako noč:
  1. Potegne sveža iNaturalist opazovanja ciljnih invazivnih vrst
     (data/invasive_species.json) za Zgornjo Savinjsko dolino.
  2. Zazna, kdaj se vrsta prvič pojavi v novi mrežni celici (~1 km,
     glej data/invasive_state.json -- cache taxon ID-jev + videnih celic).
  3. Ob novi lokaciji zgradi kratek samodejni blog zapis (isti vzorec kot
     tools/generate_storm_watch_post.py / generate_arso_newsjack_post.py --
     predloga + podatki, brez LLM osnutka -- in ga pred objavo pošlje skozi
     isti lektor kot dnevni članek, glej generate_daily_post.call_lektor).
  4. Posodobi data/invazivke.json (podatki za spoke stran /invazivke/).
  5. Ob prvem dnevu v mesecu doda še mesečni pregled (brez alertov).

Prvi zagon je "bootstrap": vse najdene celice zapiše kot videne, NE
generira alertov (sicer bi ob prvem zagonu nastalo na desetine objav) --
za baseline potegne zadnjih 5 let opazovanj.

Uporaba:
    python3 tools/invasive_watch.py [--wire] [--dry-run]

Potrebne env spremenljivke:
    ANTHROPIC_API_KEY   -- za lekturo alertov (če manjka, lektura se preskoči)
"""
import datetime, json, math, os, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_monthly_post import ROOT, SITE, wire_all, fmtdate  # noqa: E402
from generate_daily_post import APP_TOPBAR, app_bottomnav, hexrgb, call_lektor  # noqa: E402

BASE = "https://api.inaturalist.org/v1"
UA = {"User-Agent": "Meteorec-InvasiveWatch/1.0 (https://meteorec.si; kontakt: filip.eremita@gmail.com)"}
CONFIG_FILE = os.path.join(ROOT, "data", "invasive_species.json")
STATE_FILE = os.path.join(ROOT, "data", "invasive_state.json")
OUTPUT_FILE = os.path.join(ROOT, "data", "invazivke.json")

RETRY_DELAYS = [2, 4, 8]  # sekunde, exponential backoff
BOOTSTRAP_YEARS = 5
WINDOW_DAYS = 30
ALERTS_LOG_KEEP_DAYS = 400  # ~13 mesecev, dovolj za "isti mesec lani" primerjavo

MUNICIPALITIES = [
    ("Mozirje", 46.339, 14.962),
    ("Rečica ob Savinji", 46.326, 14.921),
    ("Ljubno ob Savinji", 46.339, 14.837),
    ("Luče", 46.362, 14.760),
    ("Solčava", 46.427, 14.687),
    ("Gornji Grad", 46.284, 14.807),
    ("Nazarje", 46.311, 14.964),
]

SEVERITY_LABEL = {"critical": "kritična (zdravju nevarna)", "high": "visoka", "medium": "srednja", "low": "nizka"}
SEVERITY_ACCENT = {"critical": "#dc2626", "high": "#f97316", "medium": "#eab308", "low": "#22c55e"}
SEVERITY_OG_PHOTO = {"critical": "storm-clouds", "high": "storm-clouds", "medium": "misty-valley", "low": "misty-valley"}

MES_NOM = {1: "januar", 2: "februar", 3: "marec", 4: "april", 5: "maj", 6: "junij", 7: "julij",
           8: "avgust", 9: "september", 10: "oktober", 11: "november", 12: "december"}
MES_LOC = {1: "januarju", 2: "februarju", 3: "marcu", 4: "aprilu", 5: "maju", 6: "juniju", 7: "juliju",
           8: "avgustu", 9: "septembru", 10: "oktobru", 11: "novembru", 12: "decembru"}


def sl_opazovanj(n):
    """Sklanjaj samostalnik 'opazovanje' glede na število (dvojina/trojina/množina)."""
    n100 = n % 100
    if n100 == 1:
        return f"{n} opazovanje"
    if n100 == 2:
        return f"{n} opazovanji"
    if n100 in (3, 4):
        return f"{n} opazovanja"
    return f"{n} opazovanj"


def today_date():
    return datetime.date.fromisoformat(os.environ.get("POST_DATE") or datetime.date.today().isoformat())


TODAY_DATE = today_date()
TODAY = TODAY_DATE.isoformat()


def http_get_json(url, params=None, timeout=20):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    last_err = None
    for i, delay in enumerate([*RETRY_DELAYS, None]):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if delay is None:
                break
            print(f"⚠ iNaturalist klic ni uspel ({e}) -- ponovni poskus čez {delay}s ({i + 1}/{len(RETRY_DELAYS)})...")
            time.sleep(delay)
    raise RuntimeError(f"iNaturalist API po {len(RETRY_DELAYS) + 1} poskusih ni dosegljiv: {last_err}")


def load_config():
    return json.load(open(CONFIG_FILE, encoding="utf-8"))


def load_state():
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {"cells": {}, "seen_obs_ids": [], "taxon_ids": {}, "last_observed": {}}


def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(STATE_FILE, "a", encoding="utf-8").write("\n")


def load_output():
    try:
        return json.load(open(OUTPUT_FILE, encoding="utf-8"))
    except Exception:
        return {"updated": None, "species": [], "alerts": []}


def resolve_taxon_ids(species, state):
    """Razreši manjkajoče taxon ID-je prek iNaturalist /taxa in jih cachira
    v state -- nikoli ne hardcodiramo ID-jev (glej SPEC #2)."""
    ids = state.setdefault("taxon_ids", {})
    for sp in species:
        if sp["slug"] in ids:
            continue
        time.sleep(1)
        try:
            data = http_get_json(f"{BASE}/taxa", {"q": sp["sci"], "rank": "species", "per_page": 1})
        except RuntimeError as e:
            print(f"⚠ taxon za {sp['sci']} ni bil razrešen: {e}")
            continue
        results = data.get("results") or []
        if not results:
            print(f"⚠ taxon ne obstaja na iNaturalist za '{sp['sci']}'")
            continue
        ids[sp["slug"]] = results[0]["id"]
        print(f"  ✓ {sp['sl']} -> taxon_id {results[0]['id']}")
    return ids


def fetch_observations(taxon_ids_csv, bbox, d1, d2=None):
    per_page = 200
    page = 1
    out = []
    while True:
        time.sleep(1)
        params = {
            "taxon_id": taxon_ids_csv,
            "swlat": bbox["swlat"], "swlng": bbox["swlng"],
            "nelat": bbox["nelat"], "nelng": bbox["nelng"],
            "d1": d1, "quality_grade": "research,needs_id",
            "per_page": per_page, "order_by": "observed_on", "order": "desc", "page": page,
        }
        if d2:
            params["d2"] = d2
        data = http_get_json(f"{BASE}/observations", params)
        batch = data.get("results") or []
        out.extend(batch)
        total = data.get("total_results", 0)
        if not batch or len(out) >= total:
            break
        page += 1
    return out


def fetch_total_results(taxon_id, bbox, d1, d2):
    time.sleep(1)
    params = {
        "taxon_id": taxon_id,
        "swlat": bbox["swlat"], "swlng": bbox["swlng"],
        "nelat": bbox["nelat"], "nelng": bbox["nelng"],
        "d1": d1, "d2": d2, "quality_grade": "research,needs_id", "per_page": 1,
    }
    data = http_get_json(f"{BASE}/observations", params)
    return data.get("total_results", 0)


def cell_key(lat, lng, grid):
    return f"{math.floor(lat / grid) * grid:.2f}_{math.floor(lng / grid) * grid:.2f}"


def is_obscured(obs):
    if obs.get("obscured"):
        return True
    return obs.get("geoprivacy") in ("obscured", "private") or obs.get("taxon_geoprivacy") in ("obscured", "private")


def obs_photo_url(obs):
    photos = obs.get("photos") or []
    if not photos:
        return None
    url = photos[0].get("url") or ""
    return url.replace("square", "medium") if url else None


def obs_coords(obs):
    coords = ((obs.get("geojson") or {}).get("coordinates"))
    if not coords or len(coords) != 2:
        return None, None
    lng, lat = coords
    return lat, lng


def process_observations(config, state, observations, bootstrap):
    """Sprocesira sveže pridobljena opazovanja: posodobi state (celice,
    seen_obs_ids, last_observed) in vrne (new_alerts, recent_by_slug)."""
    id_to_slug = {v: k for k, v in state["taxon_ids"].items()}
    grid = config["grid_size_deg"]
    seen_ids = set(state.setdefault("seen_obs_ids", []))
    cells = state.setdefault("cells", {})
    last_observed = state.setdefault("last_observed", {})
    sp_by_slug = {sp["slug"]: sp for sp in config["species"]}

    new_alerts = []
    recent_by_slug = {}
    new_seen_ids = []

    for obs in observations:
        obs_id = obs.get("id")
        taxon = obs.get("taxon") or {}
        slug = id_to_slug.get(taxon.get("id"))
        if slug is None or obs_id in seen_ids:
            continue
        new_seen_ids.append(obs_id)

        observed_on = obs.get("observed_on") or ""
        lat, lng = obs_coords(obs)
        place = obs.get("place_guess") or "Zgornja Savinjska dolina"
        uri = obs.get("uri") or f"https://www.inaturalist.org/observations/{obs_id}"
        photo = obs_photo_url(obs)
        obscured = is_obscured(obs)

        if observed_on and observed_on > (last_observed.get(slug) or ""):
            last_observed[slug] = observed_on

        recent_by_slug.setdefault(slug, []).append({
            "date": observed_on,
            "place": place,
            "lat_approx": round(lat, 2) if lat is not None else None,
            "lng_approx": round(lng, 2) if lng is not None else None,
            "url": uri,
            "photo": photo,
        })

        if obscured or lat is None or lng is None:
            continue  # koordinate namerno zamaknjene -- preskoči celično logiko

        cell = cell_key(lat, lng, grid)
        known = cells.setdefault(slug, [])
        if cell not in known:
            known.append(cell)
            if not bootstrap:
                new_alerts.append({
                    "slug": slug, "sci": sp_by_slug[slug]["sci"], "sl": sp_by_slug[slug]["sl"],
                    "severity": sp_by_slug[slug]["severity"], "desc_sl": sp_by_slug[slug]["desc_sl"],
                    "date": observed_on or TODAY, "cell": cell, "place": place,
                    "lat_approx": round(lat, 2), "lng_approx": round(lng, 2),
                    "url": uri, "photo": photo,
                })

    seen_ids.update(new_seen_ids)
    state["seen_obs_ids"] = list(seen_ids)[-5000:]  # omeji rast datoteke
    for slug, items in recent_by_slug.items():
        items.sort(key=lambda x: x["date"], reverse=True)
        recent_by_slug[slug] = items[:5]

    return new_alerts, recent_by_slug


def municipality_for_cell(cell):
    lat, lng = (float(x) for x in cell.split("_"))
    best, best_d = None, None
    for name, mlat, mlng in MUNICIPALITIES:
        d = (lat - mlat) ** 2 + (lng - mlng) ** 2
        if best_d is None or d < best_d:
            best, best_d = name, d
    return best


def build_output_json(config, state, new_alerts, recent_by_slug):
    prev = load_output()
    alerts_log = prev.get("alerts", []) + new_alerts
    cutoff = (TODAY_DATE - datetime.timedelta(days=ALERTS_LOG_KEEP_DAYS)).isoformat()
    alerts_log = [a for a in alerts_log if a.get("date", "") >= cutoff]
    alerts_log.sort(key=lambda a: a.get("date", ""), reverse=True)

    cutoff30 = (TODAY_DATE - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    prev_species_by_slug = {s["slug"]: s for s in prev.get("species", [])}

    species_out = []
    for sp in config["species"]:
        slug = sp["slug"]
        total_cells = len(state.get("cells", {}).get(slug, []))
        new_cells_30d = sum(1 for a in alerts_log if a["slug"] == slug and a["date"] >= cutoff30)
        recent = recent_by_slug.get(slug) or prev_species_by_slug.get(slug, {}).get("recent", [])
        species_out.append({
            "slug": slug, "sl": sp["sl"], "sci": sp["sci"], "severity": sp["severity"],
            "total_cells": total_cells, "new_cells_30d": new_cells_30d,
            "last_observed": state.get("last_observed", {}).get(slug),
            "recent": recent,
        })

    output = {
        "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "region": config["region"],
        "species": species_out,
        "alerts": alerts_log[:200],
    }
    json.dump(output, open(OUTPUT_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(OUTPUT_FILE, "a", encoding="utf-8").write("\n")
    return output


# ── Blog: kratki samodejni alert-zapisi (isti vzorec kot storm-watch/ARSO
# newsjack -- predloga + podatki, brez LLM osnutka, a z lektor prehodom) ──────

def slugify_simple(text):
    import re
    t = text.lower()
    for a, b in (("č", "c"), ("š", "s"), ("ž", "z")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def build_alert_article(alert):
    sev = alert["severity"]
    sev_label = SEVERITY_LABEL[sev]
    warn = ""
    if sev == "critical":
        warn = (f'<strong>Pozor:</strong> {alert["sl"]} je zdravju nevarna rastlina — stik s sokom in sončna '
                 f'svetloba lahko povzročita hude opekline. Rastline se ne dotikaj, o najdbi obvesti pristojno občino.')

    lead = (f'Na iNaturalistu je bilo pri kraju <strong>{alert["place"]}</strong> prvič zabeleženo opazovanje '
             f'vrste <strong>{alert["sl"]}</strong> ({alert["sci"]}) na tem delu Zgornje Savinjske doline — '
             f'nova mrežna celica v našem spremljanju invazivnih vrst.')

    paragraphs_intro = [alert["desc_sl"]]
    if warn:
        paragraphs_intro.append(warn)

    article = {
        "title": (f'{"⚠ " if sev == "critical" else ""}Invazivka na novi lokaciji: {alert["sl"]} pri {alert["place"]}'),
        "meta_description": (f'{alert["sl"]} ({alert["sci"]}) je bila opažena na novi lokaciji pri {alert["place"]} '
                               f'({fmtdate(alert["date"]) if alert["date"] else "neznan datum"}). Resnost: {sev_label}.'),
        "tags": ["invazivke", alert["slug"], sev, str(TODAY_DATE.year)],
        "section_label": "Invazivke",
        "og_photo": SEVERITY_OG_PHOTO[sev],
        "og_accent_hex": SEVERITY_ACCENT[sev],
        "lead": lead,
        "sections": [
            {"label": "01 — o vrsti", "heading": f'Zakaj spremljamo {alert["sl"].lower()}', "id": "o-vrsti",
             "paragraphs": paragraphs_intro},
            {"label": "02 — opazovanje", "heading": "Podatki o opazovanju", "id": "opazovanje",
             "paragraphs": [
                 (f'Opazovanje je bilo zabeleženo {fmtdate(alert["date"]) if alert["date"] else "pred kratkim"} '
                  f'in ga je na <a href="{alert["url"]}" style="color:var(--blue)">iNaturalist</a> mogoče videti '
                  f'v izvirniku (natančna koordinata na strani ni objavljena — prikazujemo jo zaokroženo na '
                  f'približno 1 km, glej <a href="/invazivke/" style="color:var(--blue)">/invazivke/</a>).'),
             ]},
        ],
        "callout": {"label": "Prijavi tudi ti", "text": ('Če opaziš invazivno vrsto v naravi, jo prijavi na '
                     '<a href="https://www.inaturalist.org" style="color:var(--blue)">iNaturalist</a> — s fotografijo '
                     'in lokacijo. Prijave se samodejno pretakajo v naš pregled na /invazivke/.')},
        "sources_note": "Vir: iNaturalist (opazovanja skupnosti, licenca CC), analiza lokacij Meteorec.",
    }
    return article


def build_alert_html(article, alert, now_utc):
    date_compact = (alert["date"] or TODAY).replace("-", "")
    cell_slug = alert["cell"].replace(".", "").replace("_", "-")
    slug = f'invazivka-{alert["slug"]}-{date_compact}-{cell_slug}'
    url = f"{SITE}/blog/{slug}.html"
    title = article["title"]
    desc = article["meta_description"]
    date_str = fmtdate(alert["date"]) if alert["date"] else fmtdate(TODAY)

    rows = [
        ("Vrsta", f'{alert["sl"]} <em>({alert["sci"]})</em>'),
        ("Resnost", SEVERITY_LABEL[alert["severity"]].capitalize()),
        ("Približna lokacija", alert["place"]),
        ("Koordinate (≈1 km)", f'{alert["lat_approx"]}, {alert["lng_approx"]}'),
        ("Datum opazovanja", date_str),
    ]
    rows_html = "\n".join(f"      <tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)

    sec_parts = []
    for s in article["sections"]:
        paras = "\n".join(f"    <p>{p}</p>" for p in s["paragraphs"])
        sec_parts.append(f'    <span class="section-label">{s["label"]}</span>\n'
                          f'    <h2 id="{s["id"]}">{s["heading"]}</h2>\n{paras}')
    sections_html = "\n\n".join(sec_parts)

    callout_html = ""
    if article.get("callout"):
        c = article["callout"]
        callout_html = f'\n    <div class="callout">\n      <p><strong>{c["label"]}:</strong> {c["text"]}</p>\n    </div>\n'

    tags = article.get("tags", [])
    keywords = ", ".join(tags)
    section_label = article.get("section_label", "Invazivke")

    html = f'''<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="UTF-8">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-LE8PJ1HR8B"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-LE8PJ1HR8B');
</script>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | Meteorec</title>
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="sl" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<meta name="description" content="{desc}">
<meta name="keywords" content="{keywords}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="Filip Eremita">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="Meteorec">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{SITE}/og/{slug}.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="sl_SI">
<meta property="article:published_time" content="{now_utc.isoformat()}">
<meta property="article:author" content="Filip Eremita">
<meta property="article:section" content="{section_label}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{SITE}/og/{slug}.jpg">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "{title}",
  "description": "{desc}",
  "image": {{ "@type": "ImageObject", "url": "{SITE}/og/{slug}.jpg", "width": 1200, "height": 630 }},
  "datePublished": "{now_utc.isoformat()}",
  "dateModified": "{now_utc.isoformat()}",
  "inLanguage": "sl",
  "author": {{ "@type": "Person", "name": "Filip Eremita" }},
  "publisher": {{ "@type": "Organization", "name": "Meteorec", "logo": {{ "@type": "ImageObject", "url": "{SITE}/icon-512.png" }} }},
  "mainEntityOfPage": {{ "@type": "WebPage", "@id": "{url}" }},
  "keywords": "{keywords}"
}}
</script>
<link rel="stylesheet" href="/fonts/fonts.css">
<link rel="alternate" type="application/rss+xml" title="Meteorec — blog" href="/blog/rss.xml">
<link rel="stylesheet" href="blog.css">
<style>.section-label{{font-family:'JetBrains Mono',monospace;font-size:.65rem;letter-spacing:.15em;text-transform:uppercase;color:var(--cyan);opacity:.75}}</style>
</head>
<body>
{APP_TOPBAR.format(title=title)}
<div id="bg" aria-hidden="true"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="blob b4"></div><div class="blob b5"></div></div>
<div class="wrap">

  <header class="site-head">
    <a class="brand" href="/">
      <img class="brand-logo" src="/logo.svg" alt="" width="42" height="42">
      <span class="brand-name">Meteo<em>rec</em></span>
    </a>
    <nav class="site-nav"><a href="/">Vreme v živo</a><a href="/blog/">Blog</a><a href="/invazivke/">Invazivke</a></nav>
  </header>

  <nav class="crumbs" aria-label="Drobtine">
    <a href="/">Meteorec</a> › <a href="/blog/">Blog</a> › {title}
  </nav>

  <article>
    <div class="stn-badge"><span></span> Invazivke · {alert["place"]} · {section_label}</div>
    <h1>{title}</h1>
    <p class="post-meta">{date_str} · Filip Eremita · samodejni zapis (iNaturalist)</p>

    <p class="lead">{article["lead"]}</p>

    <table class="stats">
{rows_html}
    </table>
{sections_html}
{callout_html}
    <p style="color:var(--muted);font-size:.9rem;margin-top:2rem">{article["sources_note"]}</p>

    <a class="back-link" href="/invazivke/">← Vse invazivne vrste v dolini</a>
  </article>

  <footer class="site-foot">
    <span>© {now_utc.year} Meteorec · Rečica ob Savinji</span>
    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a></span>
  </footer>

</div>
<script src="likes.js" defer></script>
<script src="/blog/comments.js" defer></script>
{app_bottomnav()}
</body>
</html>
'''
    entry = {"title": title, "slug": slug, "url": f"/blog/{slug}.html", "date": alert["date"] or TODAY,
              "summary": desc, "tags": tags}
    og_meta = {
        "title": article["title"].split(":")[0][:40],
        "subtitle": f'{alert["place"]} · {date_str}',
        "section": section_label,
        "accent": hexrgb(article["og_accent_hex"]),
        "photo": article["og_photo"],
    }
    return slug, html, entry, og_meta


def publish_alert(alert, now_utc, wire):
    article = build_alert_article(alert)
    if os.environ.get("ANTHROPIC_API_KEY"):
        lektor_context = {"opazovanje": alert}
        review = call_lektor(article, lektor_context)
        if review.get("issues"):
            print("   lektor:")
            for i in review["issues"]:
                print(f"   - {i}")
        final = review.get("corrected") or article
    else:
        print("   ⚠ ANTHROPIC_API_KEY ni nastavljen -- lektura preskočena.")
        final = article
    slug, html, entry, og_meta = build_alert_html(final, alert, now_utc)
    out = os.path.join(ROOT, "blog", f"{slug}.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"✓ zapisano: blog/{slug}.html ({alert['sl']} @ {alert['place']})")
    if wire:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
        except Exception as e:
            print(f"⚠ OG slika preskočena: {e}")
        wire_all(entry, entry["url"])


# ── Mesečni pregled (1. dan v mesecu, tudi brez alertov) ─────────────────────

def prev_month_bounds(today):
    y, m = today.year, today.month - 1
    if m == 0:
        y, m = y - 1, 12
    d1 = datetime.date(y, m, 1)
    d2 = datetime.date(y, m + 1, 1) - datetime.timedelta(days=1) if m < 12 else datetime.date(y, 12, 31)
    return y, m, d1.isoformat(), d2.isoformat()


def build_monthly_digest(config, state, output):
    y, m, d1, d2 = prev_month_bounds(TODAY_DATE)
    y_ly, m_ly = y - 1, m
    d1_ly = datetime.date(y_ly, m_ly, 1).isoformat()
    d2_ly = (datetime.date(y_ly, m_ly + 1, 1) - datetime.timedelta(days=1)).isoformat() if m_ly < 12 \
        else datetime.date(y_ly, 12, 31).isoformat()
    bbox = config["region"]["bbox"]
    alerts_log = output.get("alerts", [])

    rows = []
    for sp in config["species"]:
        slug = sp["slug"]
        taxon_id = state["taxon_ids"].get(slug)
        count = fetch_total_results(taxon_id, bbox, d1, d2) if taxon_id else 0
        count_ly = fetch_total_results(taxon_id, bbox, d1_ly, d2_ly) if taxon_id else 0
        new_cells = sum(1 for a in alerts_log if a["slug"] == slug and d1 <= a.get("date", "") <= d2)
        rows.append({"sl": sp["sl"], "severity": sp["severity"], "count": count,
                     "count_ly": count_ly, "new_cells": new_cells})

    mesec_label = f"{MES_NOM[m]} {y}"
    mesec_loc = f"{MES_LOC[m]} {y}"
    rows_html = "\n".join(
        f'      <tr><th>{r["sl"]}</th><td>Opazovanj: {r["count"]} · Novih celic: {r["new_cells"]} · '
        f'Lani ({MES_NOM[m]} {y_ly}): {r["count_ly"]}</td></tr>'
        for r in rows
    )
    total_now = sum(r["count"] for r in rows)
    total_ly = sum(r["count_ly"] for r in rows)

    title = f"Mesečni pregled invazivnih vrst — {mesec_label}"
    desc = (f"Pregled opazovanj invazivnih vrst v Zgornji Savinjski dolini za {mesec_label}: "
            f"{total_now} opazovanj (lani istega meseca {total_ly}), po vrstah in novih lokacijah.")
    slug = f"invazivke-mesecni-pregled-{y}-{m:02d}"
    url = f"{SITE}/blog/{slug}.html"
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    html = f'''<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="UTF-8">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-LE8PJ1HR8B"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-LE8PJ1HR8B');
</script>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | Meteorec</title>
<link rel="canonical" href="{url}">
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="Filip Eremita">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{SITE}/og/{slug}.jpg">
<link rel="stylesheet" href="/fonts/fonts.css">
<link rel="stylesheet" href="blog.css">
</head>
<body>
{APP_TOPBAR.format(title=title)}
<div id="bg" aria-hidden="true"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="blob b4"></div><div class="blob b5"></div></div>
<div class="wrap">
  <header class="site-head">
    <a class="brand" href="/">
      <img class="brand-logo" src="/logo.svg" alt="" width="42" height="42">
      <span class="brand-name">Meteo<em>rec</em></span>
    </a>
    <nav class="site-nav"><a href="/">Vreme v živo</a><a href="/blog/">Blog</a><a href="/invazivke/">Invazivke</a></nav>
  </header>
  <nav class="crumbs" aria-label="Drobtine"><a href="/">Meteorec</a> › <a href="/blog/">Blog</a> › {title}</nav>
  <article>
    <div class="stn-badge"><span></span> Invazivke · Zgornja Savinjska dolina · Mesečni pregled</div>
    <h1>{title}</h1>
    <p class="post-meta">{fmtdate(TODAY)} · Filip Eremita · samodejni mesečni pregled</p>
    <p class="lead">V {mesec_loc} smo v Zgornji Savinjski dolini na iNaturalist zabeležili
    <strong>{sl_opazovanj(total_now)}</strong> ciljnih invazivnih vrst (isti mesec lani: {sl_opazovanj(total_ly)}).</p>
    <table class="stats">
{rows_html}
    </table>
    <p style="color:var(--muted);font-size:.9rem;margin-top:2rem">Vir: iNaturalist (opazovanja skupnosti). Podroben pregled po vrstah in lokacijah: <a href="/invazivke/" style="color:var(--blue)">/invazivke/</a>.</p>
    <a class="back-link" href="/invazivke/">← Vse invazivne vrste v dolini</a>
  </article>
  <footer class="site-foot">
    <span>© {now_utc.year} Meteorec · Rečica ob Savinji</span>
    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a></span>
  </footer>
</div>
<script src="likes.js" defer></script>
{app_bottomnav()}
</body>
</html>
'''
    entry = {"title": title, "slug": slug, "url": f"/blog/{slug}.html", "date": TODAY, "summary": desc,
              "tags": ["invazivke", "mesecni-pregled", str(y)]}
    return slug, html, entry


def publish_monthly_digest(config, state, output, wire):
    slug, html, entry = build_monthly_digest(config, state, output)
    out = os.path.join(ROOT, "blog", f"{slug}.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"✓ zapisano: blog/{slug}.html (mesečni pregled)")
    if wire:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, "title": "Mesečni pregled\ninvazivnih vrst", "subtitle": "Zgornja Savinjska dolina",
                     "section": "Invazivke", "accent": (34, 197, 94), "photo": "misty-valley"})
        except Exception as e:
            print(f"⚠ OG slika preskočena: {e}")
        wire_all(entry, entry["url"])


def main():
    wire = "--wire" in sys.argv
    dry_run = "--dry-run" in sys.argv

    config = load_config()
    state = load_state()
    bootstrap = "last_run" not in state

    try:
        resolve_taxon_ids(config["species"], state)
        taxon_ids = state.get("taxon_ids", {})
        if not taxon_ids:
            raise RuntimeError("noben taxon ID ni bil razrešen")
        csv_ids = ",".join(str(v) for v in taxon_ids.values())
        bbox = config["region"]["bbox"]
        d1 = (TODAY_DATE - datetime.timedelta(days=365 * BOOTSTRAP_YEARS) if bootstrap
              else TODAY_DATE - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
        print(f"{'BOOTSTRAP' if bootstrap else 'Pregled'}: iščem opazovanja od {d1} ...")
        observations = fetch_observations(csv_ids, bbox, d1)
        print(f"  {len(observations)} opazovanj pridobljenih.")
    except RuntimeError as e:
        print(f"::warning::invasive_watch.py: iNaturalist API nedosegljiv, preskačem ta zagon: {e}")
        sys.exit(0)

    new_alerts, recent_by_slug = process_observations(config, state, observations, bootstrap)
    state["last_run"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if dry_run:
        print(f"(--dry-run) {len(new_alerts)} novih alertov, {len(observations)} opazovanj, bootstrap={bootstrap}")
        return

    output = build_output_json(config, state, new_alerts, recent_by_slug)
    save_state(state)
    print(f"✓ data/invazivke.json posodobljen ({len(new_alerts)} novih alertov)")

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    for alert in new_alerts:
        publish_alert(alert, now_utc, wire)

    if TODAY_DATE.day == 1:
        try:
            publish_monthly_digest(config, state, output, wire)
        except RuntimeError as e:
            print(f"⚠ Mesečni pregled preskočen (API napaka): {e}")


if __name__ == "__main__":
    main()
