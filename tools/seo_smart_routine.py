#!/usr/bin/env python3
"""
tools/seo_smart_routine.py — Pametna SEO rutina za meteorec.si

Ustvari/posodobi:
  /klima/index.html        — Klimatološki povzetek (cilja "klima Rečica ob Savinji")
  /padavine/index.html     — Klimatologija padavin (cilja "padavine Rečica ob Savinji")
  /temperatura/index.html  — Klimatologija temperature (cilja "temperatura Rečica ob Savinji")
  /teden/index.html        — Zadnjih 7 dni (osveži vsak ponedeljek)
  /novosti/{slug}.html     — Strani za rekorde in sezonska prva (generirano enkrat)
  sitemap-seo.xml          — Sitemap za vse hub in event strani
  Obvesti IndexNow za vse nove/spremenjene strani

Zaženi:
  python3 tools/seo_smart_routine.py [--force-events]
"""
import json, os, sys, datetime, calendar, statistics as st, argparse, urllib.request
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
LAT, LON, ELEV = 46.325779, 14.921137, 366
TODAY = datetime.date.today()
INDEXNOW_KEY = "d4e7a1b3c9f2e5d8a0b6c3f7e2d1a4b9"
# Entity-linking za Place-shemo (preverjeno: Q969326 je naselje samo, ne občina).
RECICA_SAMEAS = ["https://www.wikidata.org/wiki/Q969326",
                 "https://en.wikipedia.org/wiki/Re%C4%8Dica_ob_Savinji"]
RECICA_SAMEAS_JSON = json.dumps(RECICA_SAMEAS, ensure_ascii=False)

MES_NOM = {1:"januar",2:"februar",3:"marec",4:"april",5:"maj",6:"junij",
           7:"julij",8:"avgust",9:"september",10:"oktober",11:"november",12:"december"}
MES_GEN = {1:"januarja",2:"februarja",3:"marca",4:"aprila",5:"maja",6:"junija",
           7:"julija",8:"avgusta",9:"septembra",10:"oktobra",11:"novembra",12:"decembra"}
MES_LOC = {1:"januarju",2:"februarju",3:"marcu",4:"aprilu",5:"maju",6:"juniju",
           7:"juliju",8:"avgustu",9:"septembru",10:"oktobru",11:"novembru",12:"decembru"}

# ── HTML gradniki (enaki vzorci kot generate_seo_pages.py) ─────────────────

GA = ('<script async src="https://www.googletagmanager.com/gtag/js?id=G-LE8PJ1HR8B"></script>\n'
      '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
      "gtag('js',new Date());gtag('config','G-LE8PJ1HR8B');</script>")

BLOBS = ('<div id="bg" aria-hidden="true">'
         '<div class="blob b1"></div><div class="blob b2"></div>'
         '<div class="blob b3"></div><div class="blob b4"></div>'
         '<div class="blob b5"></div></div>')

HEADER = '''  <header class="site-head">
    <a class="brand" href="/">
      <img class="brand-logo" src="/logo.svg" alt="" width="42" height="42">
      <span class="brand-name">Meteo<em>rec</em></span>
    </a>
    <nav class="site-nav">
      <a href="/">Vreme v živo</a>
      <a href="/blog/">Blog</a>
      <a href="/vreme/">Arhiv</a>
    </nav>
  </header>'''

HUB_CSS = '''<style>
.hub-intro{color:var(--muted);font-size:.97rem;line-height:1.7;margin-bottom:1.8rem}
.hub-intro a{color:var(--cyan);text-decoration:none}
.hub-intro a:hover{text-decoration:underline}
.hub-table{width:100%;border-collapse:collapse;font-size:.9rem;margin:1.2rem 0 2rem}
.hub-table th{font-size:.72rem;text-transform:uppercase;letter-spacing:.07em;
  color:var(--muted);font-family:'JetBrains Mono',monospace;padding:.55rem .7rem;
  border-bottom:1px solid var(--card-border);text-align:right;white-space:nowrap}
.hub-table th:first-child{text-align:left}
.hub-table td{padding:.5rem .7rem;border-bottom:1px solid rgba(255,255,255,.04);
  text-align:right;color:var(--text)}
.hub-table td:first-child{text-align:left;font-weight:600;color:#fff}
.hub-table tr:hover td{background:var(--card-bg)}
.hub-table .cold{color:#93c5fd}.hub-table .hot{color:var(--amber)}
.hub-table .rain{color:#60a5fa}.hub-table .muted{color:var(--muted);font-size:.85rem}
.hub-table a{color:var(--cyan);text-decoration:none;font-family:'JetBrains Mono',monospace;font-size:.82rem}
.hub-table a:hover{text-decoration:underline}
.hub-section{margin:2.4rem 0}
.hub-section h2{font-family:'Space Grotesk',sans-serif;font-size:1.25rem;
  font-weight:800;color:#fff;margin:0 0 .8rem}
.hub-section h3{font-size:1rem;font-weight:700;color:var(--cyan);margin:1.5rem 0 .4rem}
.bar-chart{margin:1rem 0 2rem}
.bar-row{display:flex;align-items:center;gap:.7rem;margin:.25rem 0}
.bar-row .br-label{font-family:'JetBrains Mono',monospace;font-size:.8rem;
  color:var(--muted);min-width:52px;text-align:right}
.bar-row .br-fill{height:11px;border-radius:4px;background:var(--cyan);
  min-width:2px;transition:width .3s}
.bar-row .br-fill.rain-fill{background:#60a5fa}
.bar-row .br-fill.frost-fill{background:#93c5fd}
.bar-row .br-fill.hot-fill{background:var(--amber)}
.bar-row .br-val{font-size:.88rem;color:#fff;font-weight:600}
.bar-row .br-sub{font-size:.78rem;color:var(--muted);margin-left:.2rem}
.novosti-card{display:block;text-decoration:none;color:inherit;
  background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;
  padding:.9rem 1.2rem;margin:.5rem 0;
  transition:border-color .2s;
  -webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px)}
.novosti-card:hover{border-color:rgba(34,211,238,.45)}
.novosti-card .nc-title{font-weight:700;color:#fff;font-size:.97rem;margin-bottom:.25rem}
.novosti-card .nc-meta{font-size:.78rem;color:var(--muted);font-family:'JetBrains Mono',monospace}
.event-hero{background:var(--card-bg);border:1px solid var(--card-border);
  border-radius:16px;padding:1.4rem 1.6rem;margin:1.4rem 0 2rem;
  -webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px)}
.event-hero .ev-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;
  color:var(--muted);font-family:'JetBrains Mono',monospace;margin-bottom:.4rem}
.event-hero .ev-value{font-family:'Space Grotesk',sans-serif;font-weight:900;
  font-size:3rem;line-height:1;color:#fff;margin-bottom:.3rem}
.event-hero .ev-value.cold{color:#93c5fd}
.event-hero .ev-value.hot{color:var(--amber)}
.event-hero .ev-value.rain{color:#60a5fa}
.event-hero .ev-date{font-size:.88rem;color:var(--muted)}
.back-link{display:inline-block;margin-top:2rem;color:var(--cyan);text-decoration:none;
  font-size:.9rem;font-weight:600}
.back-link:hover{text-decoration:underline}
</style>'''


def num(x, d=1):
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")

def fmtd(iso):
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    return f"{d}. {MES_GEN[m]} {y}"

def fmtd_short(iso):
    """D. Mes. YYYY"""
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    return f"{d}. {MES_NOM[m][:3]}. {y}"

def crumbs_html(crumbs):
    parts = []
    for i, (name, url) in enumerate(crumbs):
        if url and i < len(crumbs) - 1:
            parts.append(f'<a href="{url}">{name}</a>')
        else:
            parts.append(f'<span aria-current="page">{name}</span>')
    return ('  <nav class="crumbs" aria-label="Drobtine">\n    '
            + " › ".join(parts) + "\n  </nav>")

def crumbs_schema(crumbs):
    items = []
    for i, (name, url) in enumerate(crumbs):
        item = (f'{{"@type":"ListItem","position":{i+1},"name":{json.dumps(name)}'
                + (f',"item":"{SITE}{url}"' if url else "") + "}")
        items.append(item)
    return ('<script type="application/ld+json">\n'
            '{"@context":"https://schema.org","@type":"BreadcrumbList",'
            '"itemListElement":[' + ",".join(items) + "]}\n</script>")

def webpage_schema(url, title, desc, date_mod=None):
    full = f"{SITE}{url}"
    s = (f'{{"@context":"https://schema.org","@type":"WebPage",'
         f'"@id":{json.dumps(full)},"name":{json.dumps(title)},'
         f'"description":{json.dumps(desc)},"url":{json.dumps(full)},'
         f'"inLanguage":"sl","isPartOf":{{"@id":"{SITE}/#website"}},'
         f'"about":{{"@type":"Place","name":"Rečica ob Savinji","sameAs":{RECICA_SAMEAS_JSON},'
         f'"geo":{{"@type":"GeoCoordinates","latitude":{LAT},"longitude":{LON},"elevation":{ELEV}}}}}')
    if date_mod:
        s += f',"dateModified":{json.dumps(date_mod)}'
    s += "}"
    return f"<script type=\"application/ld+json\">\n{s}\n</script>"

def faq_schema(qa):
    items = []
    for q, a in qa:
        items.append(
            '{"@type":"Question","name":' + json.dumps(q) +
            ',"acceptedAnswer":{"@type":"Answer","text":' + json.dumps(a) + "}}"
        )
    return ('<script type="application/ld+json">\n'
            '{"@context":"https://schema.org","@type":"FAQPage",'
            '"inLanguage":"sl","mainEntity":[' + ",".join(items) + "]}\n</script>")

def jd(v):
    """json.dumps with readable Slovenian characters."""
    return json.dumps(v, ensure_ascii=False)

def dataset_schema(url, name, desc, keywords):
    full = f"{SITE}{url}"
    return (f'<script type="application/ld+json">\n'
            f'{{"@context":"https://schema.org","@type":"Dataset",'
            f'"@id":"{full}#dataset","name":{jd(name)},'
            f'"description":{jd(desc)},'
            f'"inLanguage":"sl","keywords":{jd(keywords)},'
            f'"url":{jd(full)},'
            f'"creator":{{"@type":"Person","name":"Filip Eremita"}},'
            f'"isAccessibleForFree":true,'
            f'"spatialCoverage":{{"@type":"Place","name":"Rečica ob Savinji","sameAs":{RECICA_SAMEAS_JSON},'
            f'"geo":{{"@type":"GeoCoordinates","latitude":{LAT},"longitude":{LON}}}}},'
            f'"temporalCoverage":"2019-11-07/..",'
            f'"variableMeasured":[]}}\n</script>')

def article_schema(url, title, desc, date_pub, date_mod=None):
    full = f"{SITE}{url}"
    dm = date_mod or date_pub
    return (f'<script type="application/ld+json">\n'
            f'{{"@context":"https://schema.org","@type":"NewsArticle",'
            f'"@id":{json.dumps(full)},"headline":{json.dumps(title)},'
            f'"description":{json.dumps(desc)},"url":{json.dumps(full)},'
            f'"inLanguage":"sl","datePublished":{json.dumps(date_pub)},'
            f'"dateModified":{json.dumps(dm)},'
            f'"author":{{"@type":"Person","name":"Filip Eremita"}},'
            f'"publisher":{{"@type":"Organization","name":"Meteorec",'
            f'"url":"{SITE}"}},'
            f'"about":{{"@type":"Place","name":"Rečica ob Savinji","sameAs":{RECICA_SAMEAS_JSON},'
            f'"geo":{{"@type":"GeoCoordinates","latitude":{LAT},"longitude":{LON}}}}}}}\n</script>')

def footer_html():
    return (f'  <footer class="site-foot">\n'
            f'    <span>© {TODAY.year} Meteorec · Rečica ob Savinji</span>\n'
            f'    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a>'
            f' · <a href="/vreme/">Arhiv</a> · <a href="/trendi/">Trendi</a></span>\n  </footer>')

def page_shell(title, desc, canonical, head_extras, body_content):
    full_url = f"{SITE}{canonical}"
    return f'''<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="UTF-8">
{GA}
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | Meteorec</title>
<link rel="canonical" href="{full_url}">
<link rel="alternate" hreflang="sl" href="{full_url}">
<link rel="alternate" hreflang="x-default" href="{full_url}">
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="Filip Eremita">
<meta property="og:type" content="website">
<meta property="og:url" content="{full_url}">
<meta property="og:site_name" content="Meteorec">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{SITE}/og-image.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="sl_SI">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{SITE}/og-image.jpg">
{head_extras}
{HUB_CSS}
<link rel="stylesheet" href="/fonts/fonts.css">
<link rel="stylesheet" href="/blog/blog.css">
<link rel="stylesheet" href="/vreme/vreme.css">
</head>
<body>
{BLOBS}
<div class="wrap">
{HEADER}
{body_content}
{footer_html()}
</div>
</body>
</html>'''

def write_page(rel_path, html, force=True):
    full_path = os.path.join(ROOT, rel_path)
    if not force and os.path.exists(full_path):
        return False
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(html)
    return True

# ── Pojav-pomočniki ────────────────────────────────────────────────────────

def is_frost(v):
    tl = v.get("tempLow")
    return tl is not None and tl <= 0

def is_hot(v):
    th = v.get("tempHigh")
    ta = v.get("tempAvg")
    if th is not None and th != ta:
        return th >= 30
    return ta is not None and ta >= 25

# ── Klimatska statistika ───────────────────────────────────────────────────

def compute_climate(history):
    """
    Izračuna mesečne klimatološke norme in ekstreme iz celotne historije.

    Vrne:
        normals[m] = {tempAvg, tempHigh, tempLow, precip_monthly,
                      frost_days_avg, hot_days_avg, abs_max, abs_min, years_count}
        annual_precip = {year: total_mm}
        annual_frost  = {year: count}
        annual_hot    = {year: count}
    """
    month_tavg   = defaultdict(list)
    month_thigh  = defaultdict(list)
    month_tlow   = defaultdict(list)
    month_precip = defaultdict(lambda: defaultdict(float))   # m -> year -> mm
    month_frost  = defaultdict(lambda: defaultdict(int))     # m -> year -> count
    month_hot    = defaultdict(lambda: defaultdict(int))     # m -> year -> count
    monthly_abs_max = {}  # m -> (date_str, value)
    monthly_abs_min = {}  # m -> (date_str, value)
    annual_precip = defaultdict(float)
    annual_frost  = defaultdict(int)
    annual_hot    = defaultdict(int)

    for ds, v in history.items():
        yr = int(ds[:4])
        mo = int(ds[5:7])

        if v.get("tempAvg") is not None:
            month_tavg[mo].append(v["tempAvg"])
        if v.get("tempHigh") is not None:
            month_thigh[mo].append(v["tempHigh"])
            if mo not in monthly_abs_max or v["tempHigh"] > monthly_abs_max[mo][1]:
                monthly_abs_max[mo] = (ds, v["tempHigh"])
        if v.get("tempLow") is not None:
            month_tlow[mo].append(v["tempLow"])
            if mo not in monthly_abs_min or v["tempLow"] < monthly_abs_min[mo][1]:
                monthly_abs_min[mo] = (ds, v["tempLow"])
        if v.get("precipTotal") is not None:
            month_precip[mo][yr] += v["precipTotal"]
            annual_precip[yr] += v["precipTotal"]
        if is_frost(v):
            month_frost[mo][yr] += 1
            annual_frost[yr] += 1
        if is_hot(v):
            month_hot[mo][yr] += 1
            annual_hot[yr] += 1

    normals = {}
    for mo in range(1, 13):
        py = month_precip[mo]
        fy = month_frost[mo]
        hy = month_hot[mo]
        all_years = sorted(set(list(py) + list(fy) + list(hy)))

        normals[mo] = {
            "tempAvg":        st.mean(month_tavg[mo])   if month_tavg[mo]  else None,
            "tempHigh":       st.mean(month_thigh[mo])  if month_thigh[mo] else None,
            "tempLow":        st.mean(month_tlow[mo])   if month_tlow[mo]  else None,
            "precip_monthly": st.mean(py.values())       if py              else None,
            "frost_days_avg": st.mean(fy.get(y, 0) for y in all_years) if all_years else 0,
            "hot_days_avg":   st.mean(hy.get(y, 0) for y in all_years) if all_years else 0,
            "abs_max":        monthly_abs_max.get(mo),
            "abs_min":        monthly_abs_min.get(mo),
            "years_count":    len(all_years),
        }

    return normals, dict(annual_precip), dict(annual_frost), dict(annual_hot)

# ── Detekcija dogodkov ─────────────────────────────────────────────────────

def detect_events(history, lookback_days=14):
    """
    Poišče notable vremenske dogodke v zadnjih lookback_days dneh:
    - Novi absolutni rekordi (tempHigh, tempLow, precipTotal, windgustHigh)
    - Sezonska prva (prva zmrzal jeseni, prvi vroči dan pomladi/poletja)

    Vrne seznam event-diktov.
    """
    cutoff = TODAY - datetime.timedelta(days=lookback_days)
    sorted_dates = sorted(history)
    if not sorted_dates:
        return []

    pre_dates    = [d for d in sorted_dates if datetime.date.fromisoformat(d) < cutoff]
    recent_dates = [d for d in sorted_dates if datetime.date.fromisoformat(d) >= cutoff]
    if not recent_dates:
        return []

    events = []

    # ── Absolutni rekordi ──────────────────────────────────────────────────
    params = [
        ("tempHigh",     "max", "rekord-vrocina",  "Rekordna vročina"),
        ("tempLow",      "min", "rekord-mraz",     "Rekordni mraz"),
        ("precipTotal",  "max", "rekord-padavine", "Rekordne padavine v enem dnevu"),
        ("windgustHigh", "max", "rekord-sunki",    "Rekordni sunki vetra"),
    ]
    for param, direction, slug_prefix, label in params:
        pre_vals = [history[d][param] for d in pre_dates if history[d].get(param) is not None]
        if not pre_vals:
            continue
        prev_rec = max(pre_vals) if direction == "max" else min(pre_vals)

        for ds in recent_dates:
            v = history[ds].get(param)
            if v is None:
                continue
            is_new = (direction == "max" and v > prev_rec) or (direction == "min" and v < prev_rec)
            if is_new:
                events.append({
                    "type":   slug_prefix,
                    "date":   ds,
                    "value":  v,
                    "param":  param,
                    "label":  label,
                    "slug":   f"{slug_prefix}-{ds}",
                })
                prev_rec = v

    # ── Sezonska prva ──────────────────────────────────────────────────────
    year = TODAY.year

    # Prva zmrzal jeseni (od 1. septembra)
    if TODAY >= datetime.date(year, 9, 1):
        season_dates = [d for d in sorted_dates if f"{year}-09-01" <= d <= TODAY.isoformat()]
        first_frost = next((d for d in season_dates if is_frost(history[d])), None)
        if first_frost and datetime.date.fromisoformat(first_frost) >= cutoff:
            # Preverimo, da to res ni bila prva zmrzal leta (pred septembrom)
            prev_frosts = [d for d in sorted_dates
                           if d < first_frost and d >= f"{year}-01-01" and is_frost(history[d])]
            if not prev_frosts:
                events.append({
                    "type":  "prva-zmrzal",
                    "date":  first_frost,
                    "value": history[first_frost].get("tempLow"),
                    "param": "tempLow",
                    "label": "Prva zmrzal sezone",
                    "slug":  f"prva-zmrzal-{year}",
                })

    # Prva zmrzal spomladi (od 1. marca — pozna zmrzal)
    if datetime.date(year, 3, 1) <= TODAY <= datetime.date(year, 6, 30):
        spring_dates = [d for d in sorted_dates if f"{year}-03-01" <= d <= TODAY.isoformat()]
        first_spring_frost = next((d for d in spring_dates if is_frost(history[d])), None)
        if first_spring_frost and datetime.date.fromisoformat(first_spring_frost) >= cutoff:
            events.append({
                "type":  "pozna-zmrzal",
                "date":  first_spring_frost,
                "value": history[first_spring_frost].get("tempLow"),
                "param": "tempLow",
                "label": "Pozna spomladanska zmrzal",
                "slug":  f"pozna-zmrzal-{year}",
            })

    # Prvi vroči dan leta (od 1. aprila)
    if TODAY >= datetime.date(year, 4, 1):
        hot_dates = [d for d in sorted_dates if f"{year}-04-01" <= d <= TODAY.isoformat()]
        first_hot = next((d for d in hot_dates if is_hot(history[d])), None)
        if first_hot and datetime.date.fromisoformat(first_hot) >= cutoff:
            events.append({
                "type":  "prvi-vrocinski-dan",
                "date":  first_hot,
                "value": history[first_hot].get("tempHigh"),
                "param": "tempHigh",
                "label": "Prvi vroči dan leta",
                "slug":  f"prvi-vrocinski-dan-{year}",
            })

    return events


def detect_heat_waves(history, lookback_days=30):
    """
    Poišče toplotne valove (3+ zaporedni dnevi z max ≥ 30 °C).
    Upošteva valove, ki so se zaključili v zadnjih lookback_days dneh.
    """
    cutoff = TODAY - datetime.timedelta(days=lookback_days)
    sorted_dates = sorted(history)
    hot_days = [d for d in sorted_dates if (history[d].get("tempHigh") or 0) >= 30]

    events = []
    i = 0
    while i < len(hot_days):
        wave = [hot_days[i]]
        j = i + 1
        while j < len(hot_days):
            prev = datetime.date.fromisoformat(hot_days[j - 1])
            curr = datetime.date.fromisoformat(hot_days[j])
            if (curr - prev).days == 1:
                wave.append(hot_days[j])
                j += 1
            else:
                break
        if len(wave) >= 3:
            wave_end = datetime.date.fromisoformat(wave[-1])
            if wave_end >= cutoff:
                max_temp = max(history[d].get("tempHigh", 0) for d in wave)
                events.append({
                    "type":     "toplotni-val",
                    "date":     wave[0],
                    "end_date": wave[-1],
                    "value":    max_temp,
                    "param":    "tempHigh",
                    "label":    f"Toplotni val ({len(wave)} dni)",
                    "slug":     f"toplotni-val-{wave[0]}",
                    "duration": len(wave),
                })
            i = j
        else:
            i += 1
    return events


def detect_droughts(history, lookback_days=30):
    """
    Poišče sušna obdobja (7+ zaporednih dni z < 1 mm padavin).
    Upošteva obdobja, ki so se zaključila v zadnjih lookback_days dneh.
    """
    cutoff = TODAY - datetime.timedelta(days=lookback_days)
    sorted_dates = sorted(history)

    events = []
    i = 0
    while i < len(sorted_dates):
        d0 = sorted_dates[i]
        if (history[d0].get("precipTotal") or 0) >= 1.0:
            i += 1
            continue
        run = [d0]
        j = i + 1
        while j < len(sorted_dates):
            prev = datetime.date.fromisoformat(sorted_dates[j - 1])
            curr = datetime.date.fromisoformat(sorted_dates[j])
            if (curr - prev).days == 1 and (history[sorted_dates[j]].get("precipTotal") or 0) < 1.0:
                run.append(sorted_dates[j])
                j += 1
            else:
                break
        if len(run) >= 7:
            run_end = datetime.date.fromisoformat(run[-1])
            if run_end >= cutoff:
                events.append({
                    "type":     "susa",
                    "date":     run[0],
                    "end_date": run[-1],
                    "value":    float(len(run)),
                    "param":    "precipTotal",
                    "label":    f"Sušno obdobje ({len(run)} dni)",
                    "slug":     f"susa-{run[0]}",
                    "duration": len(run),
                })
        i = j if j > i + 1 else i + 1
    return events


# ── Persistenca novosti ────────────────────────────────────────────────────

NOVOSTI_CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "novosti.json")


def load_novosti_catalog():
    """Naloži shranjeni katalog vseh zaznanih dogodkov."""
    if os.path.exists(NOVOSTI_CATALOG_PATH):
        try:
            return json.load(open(NOVOSTI_CATALOG_PATH, encoding="utf-8"))
        except Exception:
            return []
    return []


def save_novosti_catalog(events):
    """Shrani katalog dogodkov v novosti.json (brez duplikatov, sortirano po datumu)."""
    seen = set()
    unique = []
    for ev in sorted(events, key=lambda e: e["date"], reverse=True):
        if ev["slug"] not in seen:
            seen.add(ev["slug"])
            unique.append(ev)
    with open(NOVOSTI_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)


# ── Generatorji strani ─────────────────────────────────────────────────────

def gen_klima(normals, annual_precip, annual_frost, annual_hot, last_date, sitemap_urls):
    """Generiraj /klima/index.html — mesečne klimatološke norme."""
    url = "/klima/"
    lastmod = TODAY.isoformat()
    years_span = TODAY.year - 2019 + 1

    avg_ann_prec  = st.mean(annual_precip.values()) if annual_precip else None
    avg_ann_frost = st.mean(annual_frost.values())  if annual_frost  else None
    avg_ann_hot   = st.mean(annual_hot.values())    if annual_hot    else None

    # Mesečna tabela
    rows = []
    for mo in range(1, 13):
        nm = normals.get(mo, {})
        rows.append(
            f'    <tr>'
            f'<td>{MES_NOM[mo].capitalize()}</td>'
            f'<td class="cold">{num(nm.get("tempLow"))} °C</td>'
            f'<td>{num(nm.get("tempAvg"))} °C</td>'
            f'<td class="hot">{num(nm.get("tempHigh"))} °C</td>'
            f'<td class="rain">{num(nm.get("precip_monthly"), 0)} mm</td>'
            f'<td class="muted">{num(nm.get("frost_days_avg"), 0)}</td>'
            f'<td class="muted">{num(nm.get("hot_days_avg"), 0)}</td>'
            f'</tr>'
        )

    table_html = (
        '  <div class="hub-section">\n'
        f'    <h2 id="mesecna-klimatoloska-norma">Mesečna klimatološka norma ({years_span} let meritev)</h2>\n'
        '    <table class="hub-table">\n'
        '      <thead><tr>'
        '<th>Mesec</th><th>Min °C</th><th>Povp. °C</th><th>Max °C</th>'
        '<th>Padavine</th><th>Mrzli dni</th><th>Vroči dni</th>'
        '</tr></thead>\n'
        '      <tbody>\n' + "\n".join(rows) + '\n      </tbody>\n'
        '    </table>\n  </div>'
    )

    # Absolutni mesečni rekordi
    rec_rows = []
    for mo in range(1, 13):
        nm = normals.get(mo, {})
        mx = nm.get("abs_max")
        mn = nm.get("abs_min")
        mx_str = (f'<span class="hot">{num(mx[1])} °C</span> '
                  f'<a href="/vreme/{mx[0][:4]}/{mx[0][5:7]}/{mx[0][8:10]}/">'
                  f'{fmtd_short(mx[0])}</a>') if mx else "—"
        mn_str = (f'<span class="cold">{num(mn[1])} °C</span> '
                  f'<a href="/vreme/{mn[0][:4]}/{mn[0][5:7]}/{mn[0][8:10]}/">'
                  f'{fmtd_short(mn[0])}</a>') if mn else "—"
        rec_rows.append(
            f'    <tr><td>{MES_NOM[mo].capitalize()}</td>'
            f'<td>{mx_str}</td><td>{mn_str}</td></tr>'
        )

    records_html = (
        '  <div class="hub-section">\n'
        '    <h2 id="absolutni-mesecni-rekordi">Absolutni mesečni rekordi</h2>\n'
        '    <table class="hub-table">\n'
        '      <thead><tr><th>Mesec</th><th>Rekordni maks.</th><th>Rekordni min.</th></tr></thead>\n'
        '      <tbody>\n' + "\n".join(rec_rows) + '\n      </tbody>\n'
        '    </table>\n  </div>'
    )

    summary_html = (
        '  <div class="all-time-grid" style="margin:1.8rem 0">\n'
        '    <div class="at-card"><div class="at-label">Povp. letne padavine</div>'
        f'<div class="at-val rain">{num(avg_ann_prec, 0)} mm</div>'
        f'<div class="at-sub">povprečje 2019–{TODAY.year}</div></div>\n'
        '    <div class="at-card"><div class="at-label">Povp. mrzlih dni/leto</div>'
        f'<div class="at-val cold">{num(avg_ann_frost, 0)}</div>'
        '<div class="at-sub">min. temp. ≤ 0 °C</div></div>\n'
        '    <div class="at-card"><div class="at-label">Povp. vročih dni/leto</div>'
        f'<div class="at-val hot">{num(avg_ann_hot, 0)}</div>'
        '<div class="at-sub">maks. temp. ≥ 30 °C</div></div>\n'
        '  </div>'
    )

    warmest = max(range(1, 13), key=lambda m: normals.get(m, {}).get("tempAvg") or -99)
    coldest = min(range(1, 13), key=lambda m: normals.get(m, {}).get("tempAvg") or 99)
    wettest = max(range(1, 13), key=lambda m: normals.get(m, {}).get("precip_monthly") or -1)

    faq_qa = [
        (
            "Kakšna je klima v Rečici ob Savinji?",
            f"Rečica ob Savinji ({ELEV} m n. m., Zgornja Savinjska dolina) ima zmerno celinsko klimo. "
            f"Najtoplejši mesec je {MES_NOM[warmest]} s povprečno temperaturo {num(normals[warmest].get('tempAvg'))} °C, "
            f"najhladnejši pa {MES_NOM[coldest]} s {num(normals[coldest].get('tempAvg'))} °C. "
            f"Letno pade povprečno {num(avg_ann_prec, 0)} mm padavin."
        ),
        (
            "Kdaj je v Rečici ob Savinji najtopleje?",
            f"Najtopleje je v {MES_LOC[warmest]}, ko dnevni maksimumi v povprečju dosežejo "
            f"{num(normals[warmest].get('tempHigh'))} °C, povprečna dnevna temperatura pa je "
            f"{num(normals[warmest].get('tempAvg'))} °C."
        ),
        (
            "Kdaj v Rečici ob Savinji zmrzuje?",
            f"Zmrzal (min. temperatura ≤ 0 °C) je najpogostejša od novembra do marca. "
            f"Največ mrzlih dni je v januarju, ko jih je v povprečju "
            f"{num(normals.get(1, {}).get('frost_days_avg'), 0)} na mesec. "
            f"Na leto postaja IREICA1 zabeleži povprečno {num(avg_ann_frost, 0)} dni z mrazom."
        ),
        (
            "Koliko dežja pade v Rečici ob Savinji?",
            f"Letno pade povprečno {num(avg_ann_prec, 0)} mm padavin. "
            f"Najdeževnejši mesec je {MES_NOM[wettest]} s povprečno "
            f"{num(normals[wettest].get('precip_monthly'), 0)} mm. "
            f"Podatki postaje IREICA1 zajemajo obdobje od novembra 2019."
        ),
        (
            "Koliko vročih dni je v Rečici ob Savinji?",
            f"Vroči dan je definiran kot dan, ko temperature preseže 30 °C. "
            f"V Rečici ob Savinji je takih dni povprečno {num(avg_ann_hot, 0)} na leto, "
            f"večinoma v juliju in avgustu."
        ),
    ]

    faq_html = "\n".join(f'    <h3>{q}</h3>\n    <p class="hub-intro">{a}</p>'
                          for q, a in faq_qa)

    title = "Klima Rečica ob Savinji — mesečne norme in rekordi"
    desc  = (f"Klimatološke norme za Rečico ob Savinji ({ELEV} m n. m.): mesečna povprečja temperature "
             f"in padavin, absolutni rekordi, mrzli in vroči dnevi — podatki postaje IREICA1 od 2019.")

    schema = (crumbs_schema([("Meteorec", "/"), ("Klima", None)])
              + webpage_schema(url, title, desc, lastmod)
              + dataset_schema(url, "Klimatološke norme — Rečica ob Savinji", desc,
                               ["klima Rečica ob Savinji", "temperatura Rečica ob Savinji",
                                "padavine Rečica ob Savinji", "klimatologija Savinjska dolina",
                                "podnebje Zgornja Savinjska dolina"])
              + faq_schema(faq_qa))

    body = f'''{crumbs_html([("Meteorec", "/"), ("Klima", None)])}
  <h1 class="page-title">Klima Rečice ob Savinji</h1>
  <p class="archive-intro">Klimatološki povzetek meteorološke postaje IREICA1 v Rečici ob Savinji
  ({ELEV} m n. m., Zgornja Savinjska dolina) na osnovi {years_span} let meritev (2019–{TODAY.year}).
  Mesečna povprečja temperature in padavin, absolutni rekordi ter fenološki kazalniki.</p>

{summary_html}
{table_html}
{records_html}

  <div class="hub-section">
    <h2 id="pogosta-vprasanja-klima">Pogosta vprašanja o klimi Rečice ob Savinji</h2>
{faq_html}
  </div>

  <p class="muted-note">Vir: meteorološka postaja IREICA1, Rečica ob Savinji, Zgornja Savinjska dolina.
  Vrednosti so izračunane iz meritev od 7. 11. 2019 do {fmtd(last_date)}.
  Strani se osvežujejo samodejno ob novih podatkih.</p>
  <p class="muted-note">Podrobneje: <a href="/padavine/">padavine po mesecih</a> ·
  <a href="/temperatura/">temperatura po mesecih</a> · <a href="/teden/">vreme ta teden</a>.</p>
  <a class="back-link" href="/rekord/">→ Vsi absolutni rekordi postaje IREICA1</a>'''

    html = page_shell(title, desc, url, schema, body)
    write_page("klima/index.html", html, force=True)
    sitemap_urls.append((f"{SITE}{url}", lastmod, "weekly", "0.8"))
    print("  → /klima/index.html")


def gen_padavine(normals, annual_precip, last_date, sitemap_urls):
    """Generiraj /padavine/index.html — hub stran za padavine."""
    url = "/padavine/"
    lastmod = TODAY.isoformat()

    avg_ann = st.mean(annual_precip.values()) if annual_precip else None
    sorted_years = sorted(annual_precip)
    max_year = max(annual_precip, key=annual_precip.get) if annual_precip else None
    min_year = min(annual_precip, key=annual_precip.get) if annual_precip else None

    # Letna skupna tabela (vse leto, brez tekočega)
    complete_years = {y: v for y, v in annual_precip.items() if y < TODAY.year}
    if not complete_years:
        complete_years = annual_precip

    # Bar chart za letne padavine
    max_prec_val = max(complete_years.values()) if complete_years else 1
    bar_rows = []
    for yr in sorted(complete_years, reverse=True):
        val = complete_years[yr]
        fill_pct = max(2, int(val / max_prec_val * 280))
        bar_rows.append(
            f'    <div class="bar-row">'
            f'<span class="br-label">{yr}</span>'
            f'<div class="br-fill rain-fill" style="width:{fill_pct}px"></div>'
            f'<span class="br-val">{num(val, 0)} mm</span>'
            + (f'<span class="br-sub">+{num(val - avg_ann, 0)}</span>' if avg_ann and val > avg_ann
               else (f'<span class="br-sub">{num(val - avg_ann, 0)}</span>' if avg_ann else ""))
            + '</div>'
        )

    bars_html = (
        '  <div class="hub-section">\n'
        f'    <h2 id="letna-kolicina-padavin">Letna skupna količina padavin</h2>\n'
        f'    <p class="hub-intro">Povprečje: <strong>{num(avg_ann, 0)} mm/leto</strong></p>\n'
        '    <div class="bar-chart">\n'
        + "\n".join(bar_rows) + '\n    </div>\n  </div>'
    )

    # Mesečne norme — bar chart
    monthly_max = max((normals.get(m, {}).get("precip_monthly") or 0) for m in range(1, 13))
    month_bars = []
    for mo in range(1, 13):
        val = normals.get(mo, {}).get("precip_monthly") or 0
        fill_pct = max(2, int(val / max(monthly_max, 1) * 220))
        month_bars.append(
            f'    <div class="bar-row">'
            f'<span class="br-label">{MES_NOM[mo][:3].capitalize()}.</span>'
            f'<div class="br-fill rain-fill" style="width:{fill_pct}px"></div>'
            f'<span class="br-val">{num(val, 0)} mm</span>'
            f'</div>'
        )

    month_bars_html = (
        '  <div class="hub-section">\n'
        '    <h2 id="povprecne-mesecne-padavine">Povprečne mesečne padavine</h2>\n'
        '    <div class="bar-chart">\n'
        + "\n".join(month_bars) + '\n    </div>\n  </div>'
    )

    faq_qa = [
        (
            "Koliko dežja pade v Rečici ob Savinji na leto?",
            f"Postaja IREICA1 v Rečici ob Savinji ({ELEV} m n. m.) beleži povprečno "
            f"{num(avg_ann, 0)} mm padavin na leto (povprečje 2019–{TODAY.year}). "
            f"Največ je padlo leta {max_year} ({num(annual_precip.get(max_year), 0)} mm), "
            f"najmanj pa leta {min_year} ({num(annual_precip.get(min_year), 0)} mm)."
        ) if max_year and min_year else (
            "Koliko dežja pade v Rečici ob Savinji na leto?",
            f"Postaja IREICA1 beleži povprečno {num(avg_ann, 0)} mm padavin na leto."
        ),
        (
            "Kdaj je v Rečici ob Savinji največ dežja?",
            f"Padavine so precej enakomerno razporejene skozi celo leto, z rahlim viškom "
            f"v toplejši polovici leta. Julij in avgust sta meseca z intenzivnimi plohami in nevihtami, "
            f"jesen pa prinaša dolgotrajnejše deževje."
        ),
        (
            "Kdaj je v Rečici ob Savinji najmanj dežja?",
            f"Najsuše obdobje je pozimi, od januarja do februarja, ko precip. pade pretežno kot sneg. "
            f"Poletne suše so redke, saj dolino Savinje pogosto dosežejo nevihte iz Alp."
        ),
        (
            "Kaj so rekordne dnevne padavine v Rečici ob Savinji?",
            f"Vse rekordne vrednosti za posamezne dni so objavljene na strani z absolutnimi rekordi postaje IREICA1."
        ),
    ]

    faq_html = "\n".join(f'    <h3>{q}</h3>\n    <p class="hub-intro">{a}</p>'
                          for q, a in faq_qa)

    title = "Padavine Rečica ob Savinji — letni in mesečni podatki"
    desc  = (f"Klimatologija padavin za Rečico ob Savinji: letne in mesečne količine, "
             f"rekordi in trendi — podatki meteorološke postaje IREICA1 od 2019.")

    schema = (crumbs_schema([("Meteorec", "/"), ("Padavine", None)])
              + webpage_schema(url, title, desc, lastmod)
              + dataset_schema(url, "Klimatologija padavin — Rečica ob Savinji", desc,
                               ["padavine Rečica ob Savinji", "letne padavine Savinjska dolina",
                                "dež Rečica ob Savinji", "padavine Zgornja Savinjska dolina"])
              + faq_schema(faq_qa))

    body = f'''{crumbs_html([("Meteorec", "/"), ("Padavine", None)])}
  <h1 class="page-title">Padavine v Rečici ob Savinji</h1>
  <p class="archive-intro">Klimatološki pregled padavin meteorološke postaje IREICA1
  v Rečici ob Savinji ({ELEV} m n. m.). Letne skupne vrednosti, mesečne norme in rekordi
  na osnovi meritev od novembra 2019.</p>

{bars_html}
{month_bars_html}

  <div class="hub-section">
    <h2 id="pogosta-vprasanja-padavine">Pogosta vprašanja o padavinah v Rečici ob Savinji</h2>
{faq_html}
  </div>

  <p class="muted-note">Vir: meteorološka postaja IREICA1, Rečica ob Savinji.
  Zadnja posodobitev: {fmtd(last_date)}. Strani z dnevi z nalijem (&gt; 20 mm):
  <a href="/pojavi/naliv/">arhiv nalivov</a>.</p>
  <a class="back-link" href="/rekord/">→ Absolutni rekordi postaje</a>'''

    html = page_shell(title, desc, url, schema, body)
    write_page("padavine/index.html", html, force=True)
    sitemap_urls.append((f"{SITE}{url}", lastmod, "weekly", "0.8"))
    print("  → /padavine/index.html")


def gen_temperatura(normals, annual_frost, annual_hot, last_date, sitemap_urls):
    """Generiraj /temperatura/index.html — hub stran za temperature."""
    url = "/temperatura/"
    lastmod = TODAY.isoformat()

    avg_ann_frost = st.mean(annual_frost.values()) if annual_frost else None
    avg_ann_hot   = st.mean(annual_hot.values())   if annual_hot   else None

    # Mesečni temperaturni profil
    rows = []
    for mo in range(1, 13):
        nm = normals.get(mo, {})
        rows.append(
            f'    <tr>'
            f'<td>{MES_NOM[mo].capitalize()}</td>'
            f'<td class="cold">{num(nm.get("tempLow"))} °C</td>'
            f'<td>{num(nm.get("tempAvg"))} °C</td>'
            f'<td class="hot">{num(nm.get("tempHigh"))} °C</td>'
            f'<td class="muted">{num(nm.get("frost_days_avg"), 0)}</td>'
            f'<td class="muted">{num(nm.get("hot_days_avg"), 0)}</td>'
            f'</tr>'
        )

    profile_html = (
        '  <div class="hub-section">\n'
        '    <h2 id="mesecni-temperaturni-profil">Mesečni temperaturni profil</h2>\n'
        '    <table class="hub-table">\n'
        '      <thead><tr>'
        '<th>Mesec</th><th>Avg min °C</th><th>Avg povp. °C</th>'
        '<th>Avg maks. °C</th><th>Mrzli dni</th><th>Vroči dni</th>'
        '</tr></thead>\n'
        '      <tbody>\n' + "\n".join(rows) + '\n      </tbody>\n'
        '    </table>\n  </div>'
    )

    # Trend mrzlih dni po letih
    sorted_years = sorted(annual_frost)
    max_frost = max(annual_frost.values()) if annual_frost else 1
    frost_bars = []
    for yr in sorted_years:
        val = annual_frost[yr]
        fill_pct = max(2, int(val / max(max_frost, 1) * 220))
        frost_bars.append(
            f'    <div class="bar-row">'
            f'<span class="br-label">{yr}</span>'
            f'<div class="br-fill frost-fill" style="width:{fill_pct}px"></div>'
            f'<span class="br-val">{val} dni</span>'
            f'</div>'
        )

    # Trend vročih dni po letih
    max_hot = max(annual_hot.values()) if annual_hot else 1
    hot_bars = []
    for yr in sorted_years:
        val = annual_hot.get(yr, 0)
        fill_pct = max(0, int(val / max(max_hot, 1) * 220))
        hot_bars.append(
            f'    <div class="bar-row">'
            f'<span class="br-label">{yr}</span>'
            f'<div class="br-fill hot-fill" style="width:{max(fill_pct,2)}px"></div>'
            f'<span class="br-val">{val} dni</span>'
            f'</div>'
        )

    trends_html = (
        '  <div class="hub-section">\n'
        f'    <h2 id="mrzli-dnevi-po-letih">Mrzli dnevi (min. ≤ 0 °C) po letih</h2>\n'
        f'    <p class="hub-intro">Povprečje: <strong>{num(avg_ann_frost, 0)} dni/leto</strong></p>\n'
        '    <div class="bar-chart">\n' + "\n".join(frost_bars) + '\n    </div>\n\n'
        f'    <h2 id="vroci-dnevi-po-letih">Vroči dnevi (maks. ≥ 30 °C) po letih</h2>\n'
        f'    <p class="hub-intro">Povprečje: <strong>{num(avg_ann_hot, 0)} dni/leto</strong></p>\n'
        '    <div class="bar-chart">\n' + "\n".join(hot_bars) + '\n    </div>\n  </div>'
    )

    faq_qa = [
        (
            "Kakšne so povprečne temperature v Rečici ob Savinji?",
            f"V Rečici ob Savinji ({ELEV} m n. m., Zgornja Savinjska dolina) so povprečne "
            f"dnevne temperature od {num(normals.get(1, {}).get('tempAvg'))} °C v januarju "
            f"do {num(normals.get(7, {}).get('tempAvg'))} °C v juliju. "
            f"Letno povprečje znaša ok. {num(st.mean(normals[m]['tempAvg'] for m in range(1,13) if normals.get(m, {}).get('tempAvg') is not None))} °C."
        ),
        (
            "Kdaj je v Rečici ob Savinji najtopleje?",
            f"Najtopleje je v juliju in avgustu. Julijski dnevni maksimumi v povprečju dosežejo "
            f"{num(normals.get(7, {}).get('tempHigh'))} °C, absolutni rekord pa je "
            f"{num(normals.get(7, {}).get('abs_max', (None, None))[1])} °C."
        ) if normals.get(7) else (
            "Kdaj je v Rečici ob Savinji najtopleje?",
            "Najtopleje je v juliju in avgustu."
        ),
        (
            "Kdaj v Rečici ob Savinji zmrzuje?",
            f"Temperature pod 0 °C se pojavljajo pretežno od novembra do marca. "
            f"Na leto postaja IREICA1 zabeleži povprečno {num(avg_ann_frost, 0)} dni z mrazom, "
            f"največ v januarju ({num(normals.get(1, {}).get('frost_days_avg'), 0)} dni)."
        ),
        (
            "Koliko vročih dni je v Rečici ob Savinji?",
            f"Vroči dan (maks. ≥ 30 °C) nastopi povprečno {num(avg_ann_hot, 0)}-krat na leto, "
            f"večinoma julija in avgusta. Število vročih dni je v zadnjih letih v porastu."
        ),
    ]

    faq_html = "\n".join(f'    <h3>{q}</h3>\n    <p class="hub-intro">{a}</p>'
                          for q, a in faq_qa)

    title = "Temperatura Rečica ob Savinji — mesečna povprečja in trendi"
    desc  = (f"Klimatologija temperature za Rečico ob Savinji: mesečna povprečja in ekstremni, "
             f"trend mrzlih in vročih dni — podatki meteorološke postaje IREICA1 od 2019.")

    schema = (crumbs_schema([("Meteorec", "/"), ("Temperatura", None)])
              + webpage_schema(url, title, desc, lastmod)
              + dataset_schema(url, "Klimatologija temperature — Rečica ob Savinji", desc,
                               ["temperatura Rečica ob Savinji", "povprečna temperatura Savinjska dolina",
                                "vroči dnevi Rečica ob Savinji", "mrzli dnevi Savinjska dolina"])
              + faq_schema(faq_qa))

    body = f'''{crumbs_html([("Meteorec", "/"), ("Temperatura", None)])}
  <h1 class="page-title">Temperature v Rečici ob Savinji</h1>
  <p class="archive-intro">Klimatološki pregled temperature meteorološke postaje IREICA1
  v Rečici ob Savinji ({ELEV} m n. m., Zgornja Savinjska dolina).
  Mesečni profili, trend mrzlih in vročih dni ter absolutni rekordi od novembra 2019.</p>

{profile_html}
{trends_html}

  <div class="hub-section">
    <h2 id="pogosta-vprasanja-temperatura">Pogosta vprašanja o temperaturi v Rečici ob Savinji</h2>
{faq_html}
  </div>

  <p class="muted-note">Vir: postaja IREICA1, Rečica ob Savinji. Zadnji podatek: {fmtd(last_date)}.
  Absoluten temperaturni rekord: <a href="/rekord/">stran rekordov</a>.</p>
  <a class="back-link" href="/rekord/">→ Absolutni rekordi postaje IREICA1</a>'''

    html = page_shell(title, desc, url, schema, body)
    write_page("temperatura/index.html", html, force=True)
    sitemap_urls.append((f"{SITE}{url}", lastmod, "weekly", "0.8"))
    print("  → /temperatura/index.html")


def gen_teden(history, normals, sitemap_urls):
    """Generiraj /teden/index.html — vremenski povzetek zadnjih 7 dni (vedno osveži)."""
    url = "/teden/"
    lastmod = TODAY.isoformat()

    sorted_dates = sorted(history)
    # Zadnjih 7 polnih dni (ne vključuj danes, če ni vpisano)
    recent = sorted_dates[-7:]
    if not recent:
        return

    start_date = recent[0]
    end_date   = recent[-1]

    # Tdenski povzetek
    t_highs = [history[d]["tempHigh"] for d in recent if history[d].get("tempHigh") is not None]
    t_lows  = [history[d]["tempLow"]  for d in recent if history[d].get("tempLow")  is not None]
    t_avgs  = [history[d]["tempAvg"]  for d in recent if history[d].get("tempAvg")  is not None]
    precips = [history[d]["precipTotal"] for d in recent if history[d].get("precipTotal") is not None]

    week_max   = max(t_highs) if t_highs else None
    week_min   = min(t_lows)  if t_lows  else None
    week_tavg  = st.mean(t_avgs) if t_avgs else None
    week_prec  = sum(precips)    if precips else None

    # Primerjava s klimatološkim povprečjem istih mesecev
    months_in_week = {int(d[5:7]) for d in recent}
    clim_temps = [normals.get(m, {}).get("tempAvg") for m in months_in_week if normals.get(m, {}).get("tempAvg")]
    clim_tavg  = st.mean(clim_temps) if clim_temps else None
    anom = f"{'+' if week_tavg - clim_tavg >= 0 else ''}{num(week_tavg - clim_tavg)} °C" \
           if week_tavg is not None and clim_tavg is not None else None

    # Dnevna tabela
    rows = []
    for ds in recent:
        v = history[ds]
        d = datetime.date.fromisoformat(ds)
        day_name = ["pon","tor","sre","čet","pet","sob","ned"][d.weekday()]
        frost_cls = ' class="frost-row"' if is_frost(v) else (' class="hot-row"' if is_hot(v) else "")
        rows.append(
            f'    <tr{frost_cls}>'
            f'<td><a href="/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:10]}/">'
            f'{day_name}, {d.day}. {MES_NOM[d.month][:3]}.</a></td>'
            f'<td class="cold">{num(v.get("tempLow"))} °C</td>'
            f'<td>{num(v.get("tempAvg"))} °C</td>'
            f'<td class="hot">{num(v.get("tempHigh"))} °C</td>'
            f'<td class="rain">{num(v.get("precipTotal"), 1)} mm</td>'
            f'</tr>'
        )

    table_html = (
        '  <div class="hub-section">\n'
        '    <table class="hub-table day-table">\n'
        '      <thead><tr><th>Dan</th><th>Min °C</th><th>Povp. °C</th>'
        '<th>Maks. °C</th><th>Padavine</th></tr></thead>\n'
        '      <tbody>\n' + "\n".join(rows) + '\n      </tbody>\n'
        '    </table>\n  </div>'
    )

    summary_html = (
        '  <div class="all-time-grid" style="margin:1.2rem 0">\n'
        + (f'    <div class="at-card"><div class="at-label">Maks. temperatura</div>'
           f'<div class="at-val hot">{num(week_max)} °C</div></div>\n' if week_max is not None else "")
        + (f'    <div class="at-card"><div class="at-label">Min. temperatura</div>'
           f'<div class="at-val cold">{num(week_min)} °C</div></div>\n' if week_min is not None else "")
        + (f'    <div class="at-card"><div class="at-label">Skupne padavine</div>'
           f'<div class="at-val rain">{num(week_prec, 1)} mm</div></div>\n' if week_prec is not None else "")
        + (f'    <div class="at-card"><div class="at-label">Temp. anomalija</div>'
           f'<div class="at-val">{anom}</div>'
           f'<div class="at-sub">glede na klimatol. normo</div></div>\n' if anom else "")
        + '  </div>'
    )

    title = f"Vreme ta teden v Rečici ob Savinji — {fmtd_short(start_date)} do {fmtd_short(end_date)}"
    desc  = (f"Vremenski povzetek zadnjih 7 dni v Rečici ob Savinji: "
             f"temp. {num(week_min)}–{num(week_max)} °C, padavine {num(week_prec, 1)} mm "
             f"({fmtd_short(start_date)} – {fmtd_short(end_date)}).")

    faq_qa = [
        (
            "Kakšno je bilo vreme ta teden v Rečici ob Savinji?",
            f"Med {fmtd(start_date)} in {fmtd(end_date)} je temperatura na postaji IREICA1 nihala med "
            f"{num(week_min)} in {num(week_max)} °C, padavin je skupaj padlo {num(week_prec, 1)} mm."
        ),
    ]
    if anom:
        faq_qa.append((
            "Je bil ta teden toplejši ali hladnejši od povprečja?",
            f"Povprečna temperatura tega tedna je od klimatološke normale za ta del leta odstopala za {anom}."
        ))
    faq_qa.append((
        "Kako pogosto se ta stran posodobi?",
        "Tedenski povzetek se samodejno osveži vsak ponedeljek na podlagi meritev postaje IREICA1."
    ))

    faq_html = "  <h2>Pogosta vprašanja</h2>\n" + "\n".join(
        f'    <h3>{q}</h3>\n    <p class="hub-intro">{a}</p>' for q, a in faq_qa
    )

    schema = (crumbs_schema([("Meteorec", "/"), ("Ta teden", None)])
              + webpage_schema(url, title, desc, lastmod)
              + faq_schema(faq_qa))

    body = f'''{crumbs_html([("Meteorec", "/"), ("Ta teden", None)])}
  <h1 class="page-title">Vreme ta teden v Rečici ob Savinji</h1>
  <p class="archive-intro">{fmtd(start_date)} — {fmtd(end_date)} · postaja IREICA1 · {ELEV} m n. m.</p>

{summary_html}
{table_html}
{faq_html}

  <p class="muted-note">Povzetek se osveži vsak ponedeljek. Vse dnevne meritve so dostopne v
  <a href="/vreme/">arhivu vremena</a>. Klimatološka norma za primerjavo: <a href="/klima/">klima Rečice ob Savinji</a>.</p>
  <a class="back-link" href="/vreme/">→ Celoten vremenski arhiv</a>'''

    html = page_shell(title, desc, url, schema, body)
    write_page("teden/index.html", html, force=True)
    sitemap_urls.append((f"{SITE}{url}", lastmod, "weekly", "0.7"))
    print("  → /teden/index.html")


def gen_event_page(event, history, sitemap_urls, force=False):
    """Generiraj stran za posamezni vremenski dogodek v /novosti/."""
    slug = event["slug"]
    url  = f"/novosti/{slug}/"
    rel  = f"novosti/{slug}/index.html"
    ds   = event["date"]
    val  = event["value"]
    ev_type = event["type"]
    label   = event["label"]

    # Določimo vsebino glede na tip
    if ev_type == "rekord-vrocina":
        title      = f"Rekordna vročina v Rečici ob Savinji — {num(val)} °C ({fmtd(ds)})"
        desc       = (f"Meteorološka postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} "
                      f"zabeležila novo rekordno temperaturo: {num(val)} °C.")
        val_class  = "hot"
        val_unit   = "°C"
        intro_text = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} "
                      f"zabeležila rekordno visoko temperaturo {num(val)} °C. "
                      f"S tem je bil postavljen nov absolutni temperaturni rekord postaje.")
        link_label = "→ Dnevni podatki za ta dan"
        link_url   = f"/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:]}/".replace("//", "/")

    elif ev_type == "rekord-mraz":
        title      = f"Rekordni mraz v Rečici ob Savinji — {num(val)} °C ({fmtd(ds)})"
        desc       = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} zabeležila "
                      f"rekordno nizko temperaturo: {num(val)} °C.")
        val_class  = "cold"
        val_unit   = "°C"
        intro_text = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} "
                      f"zabeležila rekordno nizko temperaturo {num(val)} °C. "
                      f"S tem je bil dosežen nov temperaturni minimum v zgodovini meritev od novembra 2019.")
        link_label = "→ Dnevni podatki za ta dan"
        link_url   = f"/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:]}/".replace("//", "/")

    elif ev_type == "rekord-padavine":
        title      = f"Rekordne dnevne padavine v Rečici ob Savinji — {num(val, 1)} mm ({fmtd(ds)})"
        desc       = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} zabeležila "
                      f"rekordne dnevne padavine: {num(val, 1)} mm.")
        val_class  = "rain"
        val_unit   = "mm"
        intro_text = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} "
                      f"zabeležila rekordno dnevno količino padavin: {num(val, 1)} mm. "
                      f"To je nova absolutna vrednost v zgodovini meritev.")
        link_label = "→ Dnevni podatki za ta dan"
        link_url   = f"/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:]}/".replace("//", "/")

    elif ev_type == "rekord-sunki":
        title      = f"Rekordni sunki vetra v Rečici ob Savinji — {num(val, 1)} km/h ({fmtd(ds)})"
        desc       = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} zabeležila "
                      f"rekordni sunek vetra: {num(val, 1)} km/h.")
        val_class  = ""
        val_unit   = "km/h"
        intro_text = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} "
                      f"zabeležila rekordni sunek vetra {num(val, 1)} km/h — "
                      f"nov absolutni vetrovni rekord v zgodovini meritev.")
        link_label = "→ Dnevni podatki za ta dan"
        link_url   = f"/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:]}/".replace("//", "/")

    elif ev_type == "prva-zmrzal":
        year       = int(ds[:4])
        title      = f"Prva zmrzal sezone {year}/{year+1} v Rečici ob Savinji ({fmtd(ds)})"
        desc       = (f"Meteorološka postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} "
                      f"zabeležila prvo zmrzal sezone {year}/{year+1}: {num(val)} °C.")
        val_class  = "cold"
        val_unit   = "°C"
        intro_text = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} zabeležila "
                      f"prvo zmrzal jesensko-zimske sezone {year}/{year+1}. "
                      f"Minimalna temperatura je padla na {num(val)} °C.")
        link_label = "→ Dnevni podatki za ta dan"
        link_url   = f"/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:]}/".replace("//", "/")

    elif ev_type == "pozna-zmrzal":
        title      = f"Pozna spomladanska zmrzal v Rečici ob Savinji ({fmtd(ds)})"
        desc       = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} "
                      f"zabeležila pozno spomladansko zmrzal: {num(val)} °C.")
        val_class  = "cold"
        val_unit   = "°C"
        intro_text = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} zabeležila "
                      f"pozno spomladansko zmrzal (min. {num(val)} °C). "
                      f"Pozne zmrzali so po aprilu redke, a ne izjema za Zgornjo Savinjsko dolino.")
        link_label = "→ Dnevni podatki za ta dan"
        link_url   = f"/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:]}/".replace("//", "/")

    elif ev_type == "prvi-vrocinski-dan":
        year       = int(ds[:4])
        title      = f"Prvič 30 °C v letu {year} v Rečici ob Savinji ({fmtd(ds)})"
        desc       = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} zabeležila "
                      f"prvi vroči dan leta {year}: maksimum {num(val)} °C.")
        val_class  = "hot"
        val_unit   = "°C"
        intro_text = (f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} zabeležila "
                      f"prvi dan leta {year} z maksimalno temperaturo nad 30 °C "
                      f"(doseženo: {num(val)} °C).")
        link_label = "→ Dnevni podatki za ta dan"
        link_url   = f"/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:]}/".replace("//", "/")

    elif ev_type == "toplotni-val":
        end_d      = event.get("end_date", ds)
        dur        = event.get("duration", 1)
        year       = int(ds[:4])
        title      = f"Toplotni val v Rečici ob Savinji — {dur} dni ({fmtd(ds)}–{fmtd(end_d)})"
        desc       = (f"Postaja IREICA1 v Rečici ob Savinji je zabeležila {dur}-dnevni toplotni val "
                      f"({fmtd(ds)}–{fmtd(end_d)}) z maksimalno temperaturo {num(val)} °C.")
        val_class  = "hot"
        val_unit   = "°C"
        intro_text = (f"Od {fmtd(ds)} do {fmtd(end_d)} je meteorološka postaja IREICA1 v Rečici ob Savinji "
                      f"zabeležila {dur} zaporednih vročih dni (maks. temperatura ≥ 30 °C). "
                      f"Koničná temperatura vala je dosegla {num(val)} °C. "
                      f"Toplotni valovi so za kotlino Zgornje Savinjske doline redek, a vedno pogostejši pojav "
                      f"v kontekstu podnebnih sprememb.")
        link_label = "→ Dnevni podatki za začetni dan"
        link_url   = f"/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:10]}/"

    elif ev_type == "susa":
        end_d      = event.get("end_date", ds)
        dur        = int(event.get("duration", event.get("value", 7)))
        title      = f"Sušno obdobje v Rečici ob Savinji — {dur} dni ({fmtd(ds)}–{fmtd(end_d)})"
        desc       = (f"Postaja IREICA1 v Rečici ob Savinji je zabeležila sušno obdobje "
                      f"{dur} zaporednih dni brez padavin ({fmtd(ds)}–{fmtd(end_d)}).")
        val_class  = ""
        val_unit   = "dni"
        intro_text = (f"Od {fmtd(ds)} do {fmtd(end_d)} je Rečica ob Savinji doživela sušno obdobje: "
                      f"{dur} zaporednih dni z manj kot 1 mm padavin. "
                      f"Sušna obdobja poleti so v Zgornji Savinjski dolini redka, "
                      f"saj območje pogosto dosežejo nevihte s Karavank. Daljša sušna obdobja so "
                      f"navadno tesno povezana s toplotnimi valovi in anticiklonskim vremenom.")
        link_label = "→ Dnevni podatki za začetni dan"
        link_url   = f"/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:10]}/"

    else:
        title      = f"{label} v Rečici ob Savinji ({fmtd(ds)})"
        desc       = f"Meteorološka postaja IREICA1 je {fmtd(ds)} zabeležila: {label}."
        val_class  = ""
        val_unit   = ""
        intro_text = f"Postaja IREICA1 v Rečici ob Savinji je {fmtd(ds)} zabeležila: {label}."
        link_label = "→ Dnevni podatki"
        link_url   = f"/vreme/{ds[:4]}/{ds[5:7]}/{ds[8:]}/".replace("//", "/")

    _val_d = 0 if val_unit == "dni" else (1 if val_unit == "mm" else 1)
    _hero_date = (f"{fmtd(ds)} – {fmtd(event.get('end_date', ds))}"
                  if event.get("end_date") and event["end_date"] != ds else fmtd(ds))
    hero_html = (
        '  <div class="event-hero">\n'
        f'    <div class="ev-label">{label.upper()} · IREICA1 · REČICA OB SAVINJI</div>\n'
        f'    <div class="ev-value {val_class}">{num(val, _val_d)} {val_unit}</div>\n'
        f'    <div class="ev-date">{_hero_date}</div>\n'
        '  </div>'
    )

    schema = (crumbs_schema([("Meteorec", "/"), ("Novosti", "/novosti/"), (title[:60], None)])
              + article_schema(url, title, desc, ds))

    body = f'''{crumbs_html([("Meteorec", "/"), ("Novosti", "/novosti/"), (label, None)])}
  <h1 class="page-title">{title}</h1>
  <p class="post-meta">Meteorec · postaja IREICA1 · {fmtd(ds)}</p>

{hero_html}

  <div class="hub-section">
    <p class="hub-intro">{intro_text}</p>
    <p class="hub-intro">Podatki so zajeti iz meritev meteorološke postaje IREICA1 v Rečici ob
    Savinji ({ELEV} m n. m., Zgornja Savinjska dolina). Vse zgodovinske meritve so dostopne
    v <a href="/vreme/">arhivu vremena</a> in na <a href="/klima/">strani klimatoloških norm</a>.</p>
  </div>

  <a class="back-link" href="{link_url}">{link_label}</a>
  <br><a class="back-link" href="/rekord/">→ Absolutni rekordi postaje</a>
  <br><a class="back-link" href="/novosti/">→ Vse novosti</a>'''

    html = page_shell(title, desc, url, schema, body)
    changed = write_page(rel, html, force=force)
    sitemap_urls.append((f"{SITE}{url}", ds, "never", "0.6"))
    return changed


def gen_novosti_index(events_so_far, sitemap_urls):
    """Generiraj /novosti/index.html — seznam vseh event strani."""
    url     = "/novosti/"
    lastmod = TODAY.isoformat()

    # Preberi obstoječe novosti iz sitemap-seo.xml (če obstaja)
    existing_slugs = set(ev["slug"] for ev in events_so_far)

    def _ev_unit(ev):
        t = ev.get("type", "")
        if t == "susa":
            return "dni"
        if t == "toplotni-val":
            return "°C"
        if ev["param"] in ("tempHigh", "tempLow"):
            return "°C"
        if ev["param"] == "precipTotal":
            return "mm"
        return "km/h"

    def _ev_val_d(ev):
        unit = _ev_unit(ev)
        return 0 if unit == "dni" else 1

    cards = []
    for ev in sorted(events_so_far, key=lambda e: e["date"], reverse=True):
        slug   = ev["slug"]
        ev_url = f"/novosti/{slug}/"
        unit   = _ev_unit(ev)
        val_d = _ev_val_d(ev)
        date_str = fmtd(ev["date"])
        if ev.get("end_date") and ev["end_date"] != ev["date"]:
            date_str = f'{fmtd(ev["date"])} – {fmtd(ev["end_date"])}'
        cards.append(
            f'  <a class="novosti-card" href="{ev_url}">\n'
            f'    <div class="nc-title">{ev["label"]} — {num(ev["value"], val_d)} {unit}</div>\n'
            f'    <div class="nc-meta">{date_str} · IREICA1 · Rečica ob Savinji</div>\n'
            f'  </a>'
        )

    cards_html = "\n".join(cards) if cards else '  <p class="muted-note">Ni zabeleženih posebnih vremenskih dogodkov.</p>'

    title = "Vremenski dogodki — Rečica ob Savinji"
    desc  = "Zabeleženi posebni vremenski dogodki meteorološke postaje IREICA1 v Rečici ob Savinji: rekordi, sezonska prva in ekstremni pojavi."

    schema = (crumbs_schema([("Meteorec", "/"), ("Novosti", None)])
              + webpage_schema(url, title, desc, lastmod))

    body = f'''{crumbs_html([("Meteorec", "/"), ("Novosti", None)])}
  <h1 class="page-title">Vremenski dogodki v Rečici ob Savinji</h1>
  <p class="archive-intro">Posebni vremenski dogodki, rekordi in sezonska prva postaje IREICA1
  v Rečici ob Savinji ({ELEV} m n. m.). Samodejno zaznano iz dnevnih meritev.</p>

{cards_html}

  <p class="muted-note">Strani se samodejno ustvarijo ob novih rekordih ali sezonskih prvih.
  Celoten vremenski arhiv: <a href="/vreme/">arhiv vremena</a>.</p>
  <a class="back-link" href="/klima/">→ Klimatološke norme postaje</a>'''

    html = page_shell(title, desc, url, schema, body)
    write_page("novosti/index.html", html, force=True)
    sitemap_urls.append((f"{SITE}{url}", lastmod, "weekly", "0.7"))
    print("  → /novosti/index.html")


# ── Sitemap ────────────────────────────────────────────────────────────────

def write_sitemap(sitemap_urls):
    entries = []
    for loc, lastmod, cf, priority in sitemap_urls:
        entries.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{cf}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(entries) + "\n</urlset>\n")
    out = os.path.join(ROOT, "sitemap-seo.xml")
    with open(out, "w", encoding="utf-8") as f:
        f.write(xml)
    return len(entries)


# ── IndexNow ───────────────────────────────────────────────────────────────

def ping_indexnow(urls):
    if not urls:
        return
    payload = json.dumps({
        "host":        "meteorec.si",
        "key":         INDEXNOW_KEY,
        "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt",
        "urlList":     urls,
    }).encode()
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"IndexNow: {r.status} — {len(urls)} URL-jev poslano")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        print(f"IndexNow napaka {e.code}: {body}", file=sys.stderr)
    except Exception as e:
        print(f"IndexNow neuspeh: {e}", file=sys.stderr)


# ── Vstopna točka ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pametna SEO rutina za meteorec.si")
    parser.add_argument("--force-events", action="store_true",
                        help="Ustvari event strani, tudi če že obstajajo")
    parser.add_argument("--skip-indexnow", action="store_true",
                        help="Ne pošiljaj obvestila IndexNow")
    args = parser.parse_args()

    print(f"[{TODAY}] Nalagam history.json …")
    history = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    print(f"  → {len(history)} dni podatkov")

    last_date = sorted(history)[-1]
    print(f"  → Zadnji datum: {last_date}")

    print("\nIzračunavam klimatološke norme …")
    normals, annual_precip, annual_frost, annual_hot = compute_climate(history)

    sitemap_urls = []
    changed_urls = []

    print("\nGeneriram hub strani …")
    gen_klima(normals, annual_precip, annual_frost, annual_hot, last_date, sitemap_urls)
    changed_urls.append(f"{SITE}/klima/")

    gen_padavine(normals, annual_precip, last_date, sitemap_urls)
    changed_urls.append(f"{SITE}/padavine/")

    gen_temperatura(normals, annual_frost, annual_hot, last_date, sitemap_urls)
    changed_urls.append(f"{SITE}/temperatura/")

    print("\nGeneriram tedenski povzetek …")
    gen_teden(history, normals, sitemap_urls)
    changed_urls.append(f"{SITE}/teden/")

    print("\nNalagam katalog novosti …")
    catalog = load_novosti_catalog()
    catalog_by_slug = {ev["slug"]: ev for ev in catalog}

    print("\nIščem nedavne vremenske dogodke …")
    detected = detect_events(history, lookback_days=30)
    detected += detect_heat_waves(history, lookback_days=30)
    detected += detect_droughts(history, lookback_days=30)
    print(f"  → {len(detected)} zaznanh dogodkov")

    # Združi v katalog (brez duplikatov)
    for ev in detected:
        if ev["slug"] not in catalog_by_slug:
            catalog.append(ev)
            catalog_by_slug[ev["slug"]] = ev
            print(f"  + nov dogodek: {ev['slug']}")

    # Generiraj strani za vse zaznane dogodke (fix: os.path.exists namesto write_page)
    for ev in detected:
        slug = ev["slug"]
        full_path = os.path.join(ROOT, f"novosti/{slug}/index.html")
        if not os.path.exists(full_path) or args.force_events:
            changed = gen_event_page(ev, history, sitemap_urls, force=True)
            if changed:
                changed_urls.append(f"{SITE}/novosti/{slug}/")
                print(f"  → /novosti/{slug}/index.html")
        else:
            # Stran obstaja — dodaj le v sitemap
            sitemap_urls.append((f"{SITE}/novosti/{slug}/", ev["date"], "never", "0.6"))
            print(f"  → /novosti/{slug}/ že obstaja, preskočena")

    # Za vse kataložne dogodke (ne samo zadnjih 30 dni) dodaj sitemap vnose
    detected_slugs = {ev["slug"] for ev in detected}
    for ev in catalog:
        if ev["slug"] not in detected_slugs:
            full_path = os.path.join(ROOT, f"novosti/{ev['slug']}/index.html")
            if os.path.exists(full_path):
                sitemap_urls.append((f"{SITE}/novosti/{ev['slug']}/", ev["date"], "never", "0.6"))

    # Shrani posodobljeni katalog
    save_novosti_catalog(catalog)

    gen_novosti_index(catalog, sitemap_urls)
    changed_urls.append(f"{SITE}/novosti/")

    print("\nPišem sitemap-seo.xml …")
    n = write_sitemap(sitemap_urls)
    print(f"  → {n} URL-jev")
    changed_urls.append(f"{SITE}/sitemap-seo.xml")

    if not args.skip_indexnow:
        print(f"\nObveščam IndexNow ({len(changed_urls)} URL-jev) …")
        ping_indexnow(changed_urls)

    print(f"\n✓ Dokončano. {len(sitemap_urls)} strani v sitemap-seo.xml.")


if __name__ == "__main__":
    main()
