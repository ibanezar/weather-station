#!/usr/bin/env python3
"""
tools/generate_seo_pages.py — Programmatic SEO page generator for Meteorec.si

Generates from history.json:
  /vreme/index.html                     — archive index
  /vreme/YYYY/index.html                — year summary
  /vreme/YYYY/MM/index.html             — month summary
  /vreme/YYYY/MM/DD/index.html          — daily data
  /rekord/index.html                    — all-time records
  /pojavi/index.html                    — phenomena index
  /pojavi/zmrzal/index.html             — frost-day archive
  /pojavi/vroč-dan/index.html           — hot-day archive
  /pojavi/naliv/index.html              — heavy-rain archive
  /pomlad-YYYY/, /poletje-YYYY/ ...     — seasonal summaries
  sitemap-weather.xml                   — sitemap for all generated pages

Generates from app.js (GLOSSARY_TERMS, parsed — not hand-duplicated):
  /slovar/index.html                    — glossary index, grouped by category
  /slovar/<slug>/index.html             — one page per meteorological term

Usage:
  python3 tools/generate_seo_pages.py [--force]
"""
import json, os, sys, re, calendar, datetime, statistics as st, argparse
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
STATION_ID = "IREICA1"
LAT, LON, ELEV = 46.325779, 14.921137, 366

MES_NOM = {1:"januar",2:"februar",3:"marec",4:"april",5:"maj",6:"junij",
           7:"julij",8:"avgust",9:"september",10:"oktober",11:"november",12:"december"}
MES_GEN = {1:"januarja",2:"februarja",3:"marca",4:"aprila",5:"maja",6:"junija",
           7:"julija",8:"avgusta",9:"septembra",10:"oktobra",11:"novembra",12:"decembra"}
MES_LOC = {1:"januarju",2:"februarju",3:"marcu",4:"aprilu",5:"maju",6:"juniju",
           7:"juliju",8:"avgustu",9:"septembru",10:"oktobru",11:"novembru",12:"decembru"}

TODAY = datetime.date.today()
CURRENT_YM = TODAY.strftime("%Y-%m")

# ── Formatting helpers ───────────────────────────────────────────────────────

def num(x, d=1):
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")

def fmtd(iso):
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    return f"{d}. {MES_GEN[m]} {y}"

def load_history():
    return json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))

# ── HTML building blocks ─────────────────────────────────────────────────────

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
        item = f'{{"@type":"ListItem","position":{i+1},"name":{json.dumps(name)}'
        if url:
            item += f',"item":"{SITE}{url}"'
        item += "}"
        items.append(item)
    return (f'<script type="application/ld+json">\n'
            f'{{"@context":"https://schema.org","@type":"BreadcrumbList",'
            f'"itemListElement":[{",".join(items)}]}}\n</script>')

def webpage_schema(url, title, desc, date_published=None):
    full = f"{SITE}{url}"
    s = (f'{{"@context":"https://schema.org","@type":"WebPage",'
         f'"@id":{json.dumps(full)},"name":{json.dumps(title)},'
         f'"description":{json.dumps(desc)},"url":{json.dumps(full)},'
         f'"inLanguage":"sl","isPartOf":{{"@id":"{SITE}/#website"}},'
         f'"about":{{"@type":"Place","name":"Rečica ob Savinji",'
         f'"geo":{{"@type":"GeoCoordinates","latitude":{LAT},"longitude":{LON},"elevation":{ELEV}}}}}')
    if date_published:
        s += f',"datePublished":{json.dumps(date_published)}'
    s += "}"
    return f"<script type=\"application/ld+json\">\n{s}\n</script>"

def defined_term_schema(name, description, url, term_set_url):
    full = f"{SITE}{url}"
    data = {
        "@context": "https://schema.org",
        "@type": "DefinedTerm",
        "@id": f"{full}#term",
        "name": name,
        "description": description,
        "url": full,
        "inDefinedTermSet": f"{SITE}{term_set_url}#terms",
        "inLanguage": "sl",
    }
    return (f'<script type="application/ld+json">\n'
            f'{json.dumps(data, ensure_ascii=False, separators=(",", ":"))}\n</script>')


def defined_term_set_schema(name, url, terms):
    """terms: list of (name, description, term_url)"""
    full = f"{SITE}{url}"
    data = {
        "@context": "https://schema.org",
        "@type": "DefinedTermSet",
        "@id": f"{full}#terms",
        "name": name,
        "url": full,
        "inLanguage": "sl",
        "hasDefinedTerm": [
            {"@type": "DefinedTerm", "@id": f"{SITE}{turl}#term", "name": tname, "url": f"{SITE}{turl}"}
            for tname, _, turl in terms
        ],
    }
    return (f'<script type="application/ld+json">\n'
            f'{json.dumps(data, ensure_ascii=False, separators=(",", ":"))}\n</script>')


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


def dataset_schema(url, observations):
    """Dataset + nested WeatherObservation nodes for the latest measurements."""
    full = f"{SITE}{url}"
    obs = []
    for o in observations:
        obs.append(
            '{"@type":"PropertyValue","name":' + json.dumps(o["name"]) +
            ',"value":' + json.dumps(o["value"]) +
            (',"unitText":' + json.dumps(o["unit"]) if o.get("unit") else "") + "}"
        )
    return ('<script type="application/ld+json">\n'
            '{"@context":"https://schema.org","@type":"Dataset",'
            f'"@id":"{full}#dataset",'
            '"name":"Vremenske meritve — Rečica ob Savinji (IREICA1)",'
            '"description":"Dnevni arhiv temperature, padavin, vlage in vetra meteorološke '
            'postaje IREICA1 v Rečici ob Savinji od novembra 2019.",'
            '"inLanguage":"sl","keywords":["vreme Rečica ob Savinji",'
            '"vreme Zgornja Savinjska dolina","vremenska postaja Savinjska dolina"],'
            f'"url":"{full}",'
            '"creator":{"@type":"Person","name":"Filip Eremita"},'
            '"isAccessibleForFree":true,'
            '"spatialCoverage":{"@type":"Place","name":"Rečica ob Savinji",'
            f'"geo":{{"@type":"GeoCoordinates","latitude":{LAT},"longitude":{LON},"elevation":{ELEV}}}}},'
            f'"temporalCoverage":"2019-11-07/..",'
            '"variableMeasured":[' + ",".join(obs) + "]}\n</script>")


def archive_dataset_schema(first_date, last_date):
    """Full Dataset node for the /vreme/ archive — same @id used on the homepage
    and /o-postaji.html so Google resolves them as one entity, colocated here
    with the page whose url the other instances already point to."""
    data = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "@id": f"{SITE}/#dataset",
        "name": "Vremenske meritve — Rečica ob Savinji (IREICA1)",
        "description": ("Dnevni arhiv temperature, padavin, relativne vlage in vetra "
                         f"meteorološke postaje {STATION_ID} v Rečici ob Savinji od {fmtd(first_date)}."),
        "url": f"{SITE}/vreme/",
        "identifier": STATION_ID,
        "inLanguage": "sl",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "keywords": ["vreme Rečica ob Savinji", "vreme Zgornja Savinjska dolina",
                     "vremenska postaja Savinjska dolina"],
        "temporalCoverage": f"{first_date}/..",
        "creator": {"@type": "Person", "name": "Filip Eremita"},
        "publisher": {"@type": "Organization", "name": "Meteorec", "url": SITE + "/"},
        "spatialCoverage": {
            "@type": "Place",
            "name": "Rečica ob Savinji",
            "geo": {"@type": "GeoCoordinates", "latitude": LAT, "longitude": LON, "elevation": ELEV},
        },
        "variableMeasured": [
            {"@type": "PropertyValue", "name": "Temperatura zraka", "unitText": "°C"},
            {"@type": "PropertyValue", "name": "Padavine", "unitText": "mm"},
            {"@type": "PropertyValue", "name": "Relativna vlažnost", "unitText": "%"},
            {"@type": "PropertyValue", "name": "Hitrost vetra", "unitText": "km/h"},
        ],
        "distribution": {
            "@type": "DataDownload",
            "encodingFormat": "application/json",
            "contentUrl": f"{SITE}/history.json",
        },
    }
    return (f'<script type="application/ld+json">\n'
            f'{json.dumps(data, ensure_ascii=False, separators=(",", ":"))}\n</script>')


def stn_badge():
    return '  <div class="stn-badge"><span></span> IREICA1 · Rečica ob Savinji</div>'

def footer_html(year=None):
    y = year or TODAY.year
    return (f'  <footer class="site-foot">\n'
            f'    <span>© {y} Meteorec · Rečica ob Savinji</span>\n'
            f'    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a>'
            f' · <a href="/vreme/">Arhiv</a></span>\n  </footer>')

def page_shell(title, desc, canonical, head_extras, body_content, year=None):
    full_url = f"{SITE}{canonical}"
    y = year or TODAY.year
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
<meta name="robots" content="index, follow">
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
<link rel="stylesheet" href="/fonts/fonts.css">
<link rel="stylesheet" href="/blog/blog.css">
<link rel="stylesheet" href="/vreme/vreme.css">
</head>
<body>
{BLOBS}
<div class="wrap">
{HEADER}
{body_content}
{footer_html(y)}
</div>
</body>
</html>'''

def write_page(rel_path, html, force=False):
    full_path = os.path.join(ROOT, rel_path)
    if not force and os.path.exists(full_path):
        return False
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(html)
    return True

# ── Phenomenon detection ─────────────────────────────────────────────────────

def is_frost(v):
    tl = v.get("tempLow")
    return tl is not None and tl <= 0

def is_hot(v):
    th = v.get("tempHigh")
    ta = v.get("tempAvg")
    if th is not None and th != ta:
        return th >= 30
    return ta is not None and ta >= 25

def is_heavy_rain(v):
    p = v.get("precipTotal")
    return p is not None and p >= 20

def day_badges(v):
    badges = []
    if is_frost(v):
        badges.append(("zmrzal", "❄ Zmrzal", "badge-frost"))
    if is_hot(v):
        badges.append(("vroč-dan", "☀ Vroč dan", "badge-hot"))
    if is_heavy_rain(v):
        badges.append(("naliv", "🌧 Naliv", "badge-rain"))
    return badges

# ── Stats helpers ────────────────────────────────────────────────────────────

def month_stats(entries):
    """entries: list of (date, v) pairs for one month."""
    if not entries:
        return None
    vals = [v for _, v in entries]
    tavg = [v["tempAvg"] for v in vals if v.get("tempAvg") is not None]
    thigh = [v["tempHigh"] for v in vals if v.get("tempHigh") is not None]
    tlow = [v["tempLow"] for v in vals if v.get("tempLow") is not None]
    prec = [v.get("precipTotal", 0) or 0 for v in vals]
    wind = [v["windspeedHigh"] for v in vals if v.get("windspeedHigh") is not None]
    hum = [v["humidityAvg"] for v in vals if v.get("humidityAvg") is not None]
    return {
        "tavg": st.mean(tavg) if tavg else None,
        "tmax": max(thigh) if thigh else (max(tavg) if tavg else None),
        "tmin": min(tlow) if tlow else (min(tavg) if tavg else None),
        "prec_total": sum(prec),
        "prec_days": sum(1 for p in prec if p > 0.2),
        "wind_max": max(wind) if wind else None,
        "hum_avg": st.mean(hum) if hum else None,
        "count": len(entries),
    }

def year_stats(hist, year):
    entries = [(d, v) for d, v in hist.items() if d.startswith(str(year))]
    if not entries:
        return None
    s = month_stats(entries)
    s["months"] = {}
    for m in range(1, 13):
        prefix = f"{year}-{m:02d}"
        me = [(d, v) for d, v in entries if d.startswith(prefix)]
        if me:
            s["months"][m] = month_stats(me)
    return s

# ── Sitemap accumulator ──────────────────────────────────────────────────────

def sitemap_entry(loc, lastmod, changefreq, priority):
    return (loc, lastmod, changefreq, priority)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

def gen_daily_pages(hist, force, sitemap_urls):
    dates = sorted(hist.keys())
    written = skipped = 0
    for i, date in enumerate(dates):
        v = hist[date]
        y, m, d = int(date[:4]), int(date[5:7]), int(date[8:10])
        ym = date[:7]
        url = f"/vreme/{y}/{m:02d}/{d:02d}/"
        rel = f"vreme/{y}/{m:02d}/{d:02d}/index.html"

        # Skip if historical and already exists
        is_current_month = (ym == CURRENT_YM)
        if not force and not is_current_month and os.path.exists(os.path.join(ROOT, rel)):
            skipped += 1
            sitemap_urls.append(sitemap_entry(SITE + url, date, "monthly", "0.4"))
            continue

        prev_d = dates[i - 1] if i > 0 else None
        next_d = dates[i + 1] if i < len(dates) - 1 else None

        title = f"Vreme {d}. {MES_GEN[m]} {y} — Rečica ob Savinji"
        desc = (f"Vremenski podatki za {d}. {MES_GEN[m]} {y} v Rečici ob Savinji: "
                f"povp. temperatura {num(v.get('tempAvg'))} °C, "
                f"padavine {num(v.get('precipTotal', 0))} mm. Postaja IREICA1.")

        crumbs = [
            ("Meteorec", "/"),
            ("Vremenski arhiv", "/vreme/"),
            (str(y), f"/vreme/{y}/"),
            (f"{MES_NOM[m].capitalize()} {y}", f"/vreme/{y}/{m:02d}/"),
            (f"{d}. {MES_GEN[m]}", None),
        ]

        # Stats table rows
        rows = []
        if v.get("tempAvg") is not None:
            rows.append(("Povprečna temperatura", f"{num(v['tempAvg'])} °C"))
        if v.get("tempHigh") is not None and v["tempHigh"] != v.get("tempAvg"):
            rows.append(("Najvišja temperatura", f"{num(v['tempHigh'])} °C"))
        if v.get("tempLow") is not None and v["tempLow"] != v.get("tempAvg"):
            rows.append(("Najnižja temperatura", f"{num(v['tempLow'])} °C"))
        rows.append(("Padavine", f"{num(v.get('precipTotal', 0))} mm"))
        if v.get("windspeedHigh") is not None:
            rows.append(("Najmočnejši sunek vetra", f"{num(v['windspeedHigh'])} km/h"))
        if v.get("windspeedAvg") is not None:
            rows.append(("Povprečna hitrost vetra", f"{num(v['windspeedAvg'])} km/h"))
        if v.get("humidityAvg") is not None:
            rows.append(("Povprečna relativna vlažnost", f"{num(v['humidityAvg'], 0)} %"))
        rows_html = "\n".join(f'      <tr><th>{k}</th><td>{r}</td></tr>' for k, r in rows)

        # Phenomenon badges
        badges = day_badges(v)
        badges_html = ""
        if badges:
            badge_links = " ".join(
                f'<a href="/pojavi/{slug}/" class="{cls}">{label}</a>'
                for slug, label, cls in badges
            )
            badges_html = f'  <div class="badges">{badge_links}</div>\n'

        # Day navigation
        def day_link(dd, label):
            if not dd:
                return f'<span></span>'
            dy, dm, ddd = int(dd[:4]), int(dd[5:7]), int(dd[8:10])
            return f'<a href="/vreme/{dy}/{dm:02d}/{ddd:02d}/">{label}</a>'

        nav_html = (f'  <nav class="day-nav" aria-label="Navigacija po dnevih">\n'
                    f'    {day_link(prev_d, f"← {int(prev_d[8:10])}. {MES_GEN[int(prev_d[5:7])]}" if prev_d else "")}\n'
                    f'    <a href="/vreme/{y}/{m:02d}/">{MES_NOM[m].capitalize()} {y}</a>\n'
                    f'    {day_link(next_d, f"{int(next_d[8:10])}. {MES_GEN[int(next_d[5:7])]} →" if next_d else "")}\n'
                    f'  </nav>')

        schema = "\n".join([webpage_schema(url, title, desc, date), crumbs_schema(crumbs)])
        body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">{d}. {MES_NOM[m]} {y}</h1>
  <p class="post-meta">Meritve postaje IREICA1 · {ELEV} m n. m. · Rečica ob Savinji</p>
{badges_html}  <h2>Vremenski podatki</h2>
  <table class="stats">
{rows_html}
  </table>
  <p class="muted-note">Vir: meteorološka postaja IREICA1, Rečica ob Savinji ({ELEV} m n. m.), Savinjska dolina.
  Meritve so dnevni povzetki.</p>
{nav_html}'''

        html = page_shell(title, desc, url, schema, body, y)
        if write_page(rel, html, force=True):
            written += 1
        sitemap_urls.append(sitemap_entry(SITE + url, date, "monthly", "0.4"))

    return written, skipped


def gen_monthly_pages(hist, force, sitemap_urls):
    # Group by YYYY-MM
    by_month = defaultdict(list)
    for date, v in hist.items():
        by_month[date[:7]].append((date, v))

    written = 0
    for ym in sorted(by_month.keys()):
        y, m = int(ym[:4]), int(ym[5:7])
        entries = sorted(by_month[ym])
        s = month_stats(entries)
        if not s:
            continue

        url = f"/vreme/{y}/{m:02d}/"
        rel = f"vreme/{y}/{m:02d}/index.html"
        lastmod = entries[-1][0]
        is_current = (ym == CURRENT_YM)

        if not force and not is_current and os.path.exists(os.path.join(ROOT, rel)):
            sitemap_urls.append(sitemap_entry(SITE + url, lastmod, "monthly", "0.6"))
            continue

        dim = calendar.monthrange(y, m)[1]
        partial = s["count"] < dim
        title = f"Vreme — {MES_NOM[m].capitalize()} {y}, Rečica ob Savinji"
        desc = (f"{MES_NOM[m].capitalize()} {y} v Rečici ob Savinji: povp. temperatura "
                f"{num(s['tavg'])} °C in {num(s['prec_total'])} mm padavin. "
                f"Mesečni pregled postaje IREICA1.")

        crumbs = [
            ("Meteorec", "/"),
            ("Vremenski arhiv", "/vreme/"),
            (str(y), f"/vreme/{y}/"),
            (f"{MES_NOM[m].capitalize()} {y}", None),
        ]

        # Previous / next month nav
        def prev_next_month(y, m):
            pm = m - 1 if m > 1 else 12
            py = y if m > 1 else y - 1
            nm = m + 1 if m < 12 else 1
            ny = y if m < 12 else y + 1
            pm_key = f"{py}-{pm:02d}"
            nm_key = f"{ny}-{nm:02d}"
            all_months = sorted(by_month.keys())
            prev_url = f"/vreme/{py}/{pm:02d}/" if pm_key in all_months else None
            next_url = f"/vreme/{ny}/{nm:02d}/" if nm_key in all_months else None
            return prev_url, next_url, py, pm, ny, nm

        prev_url, next_url, py, pm, ny, nm = prev_next_month(y, m)

        def mnav(url_p, label_p, url_n, label_n):
            left = f'<a href="{url_p}">{label_p}</a>' if url_p else '<span></span>'
            right = f'<a href="{url_n}">{label_n}</a>' if url_n else '<span></span>'
            return (f'  <nav class="month-nav" aria-label="Navigacija po mesecih">\n'
                    f'    {left}\n'
                    f'    <a href="/vreme/{y}/">{y}</a>\n'
                    f'    {right}\n  </nav>')

        nav_html = mnav(
            prev_url, f"← {MES_NOM[pm].capitalize()} {py}",
            next_url, f"{MES_NOM[nm].capitalize()} {ny} →"
        )

        # Stat cards
        cards = f'''  <div class="stat-grid">
    <div class="stat-card c-temp">
      <div class="sc-label">Povp. temperatura</div>
      <div class="sc-val">{num(s['tavg'])} °C</div>
      <div class="sc-sub">{s['count']} dni meritev</div>
    </div>
    <div class="stat-card c-up">
      <div class="sc-label">Najvišja temp.</div>
      <div class="sc-val">{num(s['tmax'])} °C</div>
    </div>
    <div class="stat-card c-down">
      <div class="sc-label">Najnižja temp.</div>
      <div class="sc-val">{num(s['tmin'])} °C</div>
    </div>
    <div class="stat-card c-rain">
      <div class="sc-label">Padavine skupaj</div>
      <div class="sc-val">{num(s['prec_total'])} mm</div>
      <div class="sc-sub">{s['prec_days']} deževnih dni</div>
    </div>
  </div>'''

        # Day-by-day table
        day_rows = []
        for date, v in entries:
            dd = int(date[8:10])
            badges = day_badges(v)
            row_class = " frost-row" if is_frost(v) else (" hot-row" if is_hot(v) else "")
            badge_str = " ".join(f'<span class="{cls}">{lbl}</span>' for _, lbl, cls in badges)
            day_rows.append(
                f'      <tr class="{row_class}">'
                f'<td><a href="/vreme/{y}/{m:02d}/{dd:02d}/">{dd}.</a></td>'
                f'<td>{num(v.get("tempAvg"))} °C</td>'
                f'<td>{num(v.get("tempLow"))} °C</td>'
                f'<td>{num(v.get("tempHigh"))} °C</td>'
                f'<td>{num(v.get("precipTotal", 0))} mm</td>'
                f'<td>{num(v.get("windspeedHigh"))} km/h</td>'
                f'<td>{badge_str}</td>'
                f'</tr>'
            )
        day_table = (
            '  <table class="stats day-table">\n'
            '    <thead><tr><th>Dan</th><th>Povp. T</th><th>Min T</th><th>Max T</th>'
            '<th>Padavine</th><th>Sunek</th><th>Pojavi</th></tr></thead>\n'
            '    <tbody>\n' + "\n".join(day_rows) + '\n    </tbody>\n  </table>'
        )

        partial_note = ""
        if partial:
            partial_note = (f'  <div class="partial-note">\n'
                           f'    Podatki do {int(entries[-1][0][8:10])}. {MES_GEN[m]} {y} '
                           f'({s["count"]} od {dim} dni) — mesec še ni zaključen.\n  </div>\n')

        schema = "\n".join([webpage_schema(url, title, desc, entries[0][0]), crumbs_schema(crumbs)])
        body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">{MES_NOM[m].capitalize()} {y} — Rečica ob Savinji</h1>
  <p class="post-meta">Meritve postaje IREICA1 · {ELEV} m n. m. · Savinjska dolina</p>
{partial_note}{cards}
  <h2>Dnevi v mesecu</h2>
{day_table}
  <p class="muted-note">Temperatura je dnevno povprečje. Padavine so dnevna vsota. Prikazana je tudi max. hitrost sunka vetra.</p>
{nav_html}'''

        html = page_shell(title, desc, url, schema, body, y)
        write_page(rel, html, force=True)
        written += 1
        cf = "weekly" if is_current else "monthly"
        sitemap_urls.append(sitemap_entry(SITE + url, lastmod, cf, "0.6"))

    return written


def gen_yearly_pages(hist, force, sitemap_urls):
    years = sorted({d[:4] for d in hist})
    written = 0

    for yr in years:
        y = int(yr)
        s = year_stats(hist, y)
        if not s:
            continue

        url = f"/vreme/{y}/"
        rel = f"vreme/{y}/index.html"
        lastmod = max(d for d in hist if d.startswith(yr))
        is_current = (y == TODAY.year)

        if not force and not is_current and os.path.exists(os.path.join(ROOT, rel)):
            sitemap_urls.append(sitemap_entry(SITE + url, lastmod, "monthly", "0.7"))
            continue

        title = f"Vreme {y} — Rečica ob Savinji"
        desc = (f"Vremenski pregled leta {y} v Rečici ob Savinji: povprečna temperatura "
                f"{num(s['tavg'])} °C in {num(s['prec_total'])} mm padavin letno. Postaja IREICA1.")

        crumbs = [
            ("Meteorec", "/"),
            ("Vremenski arhiv", "/vreme/"),
            (str(y), None),
        ]

        cards = f'''  <div class="stat-grid">
    <div class="stat-card c-temp">
      <div class="sc-label">Letna povp. temp.</div>
      <div class="sc-val">{num(s['tavg'])} °C</div>
    </div>
    <div class="stat-card c-up">
      <div class="sc-label">Letni temp. max.</div>
      <div class="sc-val">{num(s['tmax'])} °C</div>
    </div>
    <div class="stat-card c-down">
      <div class="sc-label">Letni temp. min.</div>
      <div class="sc-val">{num(s['tmin'])} °C</div>
    </div>
    <div class="stat-card c-rain">
      <div class="sc-label">Letne padavine</div>
      <div class="sc-val">{num(s['prec_total'])} mm</div>
    </div>
  </div>'''

        month_rows = []
        for m in range(1, 13):
            ms = s["months"].get(m)
            if ms:
                month_rows.append(
                    f'      <tr>'
                    f'<td><a href="/vreme/{y}/{m:02d}/">{MES_NOM[m].capitalize()}</a></td>'
                    f'<td>{num(ms["tavg"])} °C</td>'
                    f'<td>{num(ms["tmin"])} °C</td>'
                    f'<td>{num(ms["tmax"])} °C</td>'
                    f'<td>{num(ms["prec_total"])} mm</td>'
                    f'<td>{ms["prec_days"]}</td>'
                    f'</tr>'
                )
            else:
                month_rows.append(
                    f'      <tr><td>{MES_NOM[m].capitalize()}</td>'
                    f'<td colspan="5" style="color:var(--muted);text-align:center">Ni podatkov</td></tr>'
                )

        month_table = (
            '  <table class="stats">\n'
            '    <thead><tr><th>Mesec</th><th>Povp. T</th><th>Min T</th><th>Max T</th>'
            '<th>Padavine</th><th>Dež. dnevi</th></tr></thead>\n'
            '    <tbody>\n' + "\n".join(month_rows) + '\n    </tbody>\n  </table>'
        )

        # Prev/next year
        prev_yr = str(y - 1)
        next_yr = str(y + 1)
        prev_exists = any(d.startswith(prev_yr) for d in hist)
        next_exists = any(d.startswith(next_yr) for d in hist)
        ynav = ('  <nav class="month-nav" aria-label="Navigacija po letih">\n'
                + (f'    <a href="/vreme/{y-1}/">← {y-1}</a>\n' if prev_exists else '    <span></span>\n')
                + f'    <a href="/vreme/">Vsi arhivi</a>\n'
                + (f'    <a href="/vreme/{y+1}/">{y+1} →</a>\n' if next_exists else '    <span></span>\n')
                + '  </nav>')

        schema = "\n".join([webpage_schema(url, title, desc), crumbs_schema(crumbs)])
        body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">Vreme {y} — Rečica ob Savinji</h1>
  <p class="post-meta">Letni pregled · postaja IREICA1 · {ELEV} m n. m.</p>
{cards}
  <h2>Mesečni pregled</h2>
{month_table}
{ynav}'''

        html = page_shell(title, desc, url, schema, body, y)
        write_page(rel, html, force=True)
        written += 1
        cf = "weekly" if is_current else "monthly"
        sitemap_urls.append(sitemap_entry(SITE + url, lastmod, cf, "0.7"))

    return written


def gen_archive_index(hist, sitemap_urls):
    years = sorted({d[:4] for d in hist}, reverse=True)
    url = "/vreme/"
    rel = "vreme/index.html"
    lastmod = TODAY.isoformat()

    # All-time stats
    all_v = list(hist.values())
    tavg_all = [v["tempAvg"] for v in all_v if v.get("tempAvg") is not None]
    tmax_all_v = max((v for v in all_v if v.get("tempHigh") is not None),
                     key=lambda v: v["tempHigh"], default=None)
    tmin_all_v = min((v for v in all_v if v.get("tempLow") is not None),
                     key=lambda v: v["tempLow"], default=None)
    tmax_all = tmax_all_v["tempHigh"] if tmax_all_v else None
    tmin_all = tmin_all_v["tempLow"] if tmin_all_v else None

    first_date = min(hist.keys())
    last_date = max(hist.keys())

    title = "Vremenski arhiv — Rečica ob Savinji"
    desc = (f"Arhiv vremenskih meritev postaje IREICA1 v Rečici ob Savinji od {fmtd(first_date)}. "
            f"Dnevni, mesečni in letni pregledi temperature, padavin in vetra.")

    crumbs = [("Meteorec", "/"), ("Vremenski arhiv", None)]

    # All-time quick stats
    at_cards = f'''  <div class="all-time-grid">
    <div class="at-card">
      <div class="at-label">Absolutni max. T</div>
      <div class="at-val hot">{num(tmax_all)} °C</div>
    </div>
    <div class="at-card">
      <div class="at-label">Absolutni min. T</div>
      <div class="at-val cold">{num(tmin_all)} °C</div>
    </div>
    <div class="at-card">
      <div class="at-label">Skupaj meritev</div>
      <div class="at-val">{len(hist)}</div>
      <div class="at-sub">dni od {fmtd(first_date)}</div>
    </div>
  </div>'''

    # Year cards
    year_cards = []
    for yr in years:
        y = int(yr)
        s = year_stats(hist, y)
        if not s:
            continue
        months_with_data = [k for k, v in s["months"].items() if v]
        if months_with_data:
            m_first = MES_NOM[min(months_with_data)].capitalize()
            m_last = MES_NOM[max(months_with_data)].capitalize()
            range_str = f"{m_first}" if min(months_with_data) == max(months_with_data) else f"{m_first} – {m_last}"
        else:
            range_str = "—"
        year_cards.append(
            f'    <a class="year-card" href="/vreme/{y}/">\n'
            f'      <div class="yc-year">{y}</div>\n'
            f'      <div class="yc-range">{range_str}</div>\n'
            f'      <div class="yc-stats">{num(s["tavg"])} °C · {num(s["prec_total"])} mm</div>\n'
            f'    </a>'
        )

    crumbs_schema_html = crumbs_schema(crumbs)
    schema = "\n".join([
        webpage_schema(url, title, desc),
        crumbs_schema_html,
        archive_dataset_schema(first_date, last_date),
    ])
    body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">Vremenski arhiv</h1>
  <p class="archive-intro">Arhiv meritev meteorološke postaje <strong>IREICA1</strong> v <strong>Rečici ob Savinji</strong>
  (Savinjska dolina, {ELEV} m n. m.) od novembra 2019. Vsak dan ima svojo stran z natančnimi podatki o temperaturi,
  padavinah in vetru.</p>
{at_cards}
  <h2>Izberi leto</h2>
  <div class="card-grid">
{chr(10).join(year_cards)}
  </div>
  <p class="muted-note">Za vse rekorde: <a href="/rekord/">→ Vremenski rekordi</a> ·
  Vremenski pojavi: <a href="/pojavi/">→ Zmrzal, vroči dnevi, nalivi</a></p>'''

    html = page_shell(title, desc, url, schema, body)
    write_page(rel, html, force=True)
    sitemap_urls.append(sitemap_entry(SITE + url, lastmod, "weekly", "0.8"))


def gen_records_page(hist, sitemap_urls):
    url = "/rekord/"
    rel = "rekord/index.html"
    lastmod = TODAY.isoformat()

    # Compute records
    def find_record(key, fn=max, attr=None):
        candidates = [(d, v) for d, v in hist.items() if v.get(attr or key) is not None]
        if not candidates:
            return None, None
        date, v = fn(candidates, key=lambda dv: dv[1][attr or key])
        return date, v[attr or key]

    tmax_d, tmax_v = find_record("tempHigh", max)
    tmin_d, tmin_v = find_record("tempLow", min)
    prec_d, prec_v = find_record("precipTotal", max)
    wind_d, wind_v = find_record("windspeedHigh", max)

    # Monthly records
    by_month = defaultdict(list)
    for d, v in hist.items():
        by_month[d[:7]].append((d, v))

    month_avgs = {}
    month_precs = {}
    for ym, entries in by_month.items():
        ms = month_stats(entries)
        if ms and ms["count"] >= 20:
            month_avgs[ym] = ms["tavg"]
            month_precs[ym] = ms["prec_total"]

    hottest_ym = max(month_avgs, key=month_avgs.get) if month_avgs else None
    coldest_ym = min(month_avgs, key=month_avgs.get) if month_avgs else None
    wettest_ym = max(month_precs, key=month_precs.get) if month_precs else None
    driest_ym = min(month_precs, key=month_precs.get) if month_precs else None

    def ym_link(ym):
        if not ym:
            return "—"
        y, m = int(ym[:4]), int(ym[5:7])
        return f'<a href="/vreme/{y}/{m:02d}/">{MES_NOM[m].capitalize()} {y}</a>'

    def d_link(d, val_str):
        if not d:
            return "—", "—"
        y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
        return f'<a href="/vreme/{y}/{m:02d}/{dd:02d}/">{dd}. {MES_GEN[m]} {y}</a>', val_str

    tmax_link, tmax_str = d_link(tmax_d, f"{num(tmax_v)} °C")
    tmin_link, tmin_str = d_link(tmin_d, f"{num(tmin_v)} °C")
    prec_link, prec_str = d_link(prec_d, f"{num(prec_v)} mm")
    wind_link, wind_str = d_link(wind_d, f"{num(wind_v)} km/h")

    title = "Vremenski rekordi — Rečica ob Savinji"
    desc = (f"Vremenski rekordi meteorološke postaje IREICA1 v Rečici ob Savinji. "
            f"Absolutni temperaturni ekstrem: max {num(tmax_v)} °C, min {num(tmin_v)} °C. "
            f"Dnevni rekord padavin: {num(prec_v)} mm.")

    crumbs = [("Meteorec", "/"), ("Vremenski arhiv", "/vreme/"), ("Rekordi", None)]

    rows_temp = (
        f'    <tr><th>Absolutno najvišja temperatura</th><td class="record-val">{tmax_str}</td>'
        f'<td class="record-date">{tmax_link}</td></tr>\n'
        f'    <tr><th>Absolutno najnižja temperatura</th><td class="record-val">{tmin_str}</td>'
        f'<td class="record-date">{tmin_link}</td></tr>\n'
        f'    <tr><th>Najtoplejši mesec (povp.)</th>'
        f'<td class="record-val">{num(month_avgs.get(hottest_ym))} °C</td>'
        f'<td class="record-date">{ym_link(hottest_ym)}</td></tr>\n'
        f'    <tr><th>Najhladnejši mesec (povp.)</th>'
        f'<td class="record-val">{num(month_avgs.get(coldest_ym))} °C</td>'
        f'<td class="record-date">{ym_link(coldest_ym)}</td></tr>'
    )
    rows_prec = (
        f'    <tr><th>Rekord padavin v enem dnevu</th><td class="record-val">{prec_str}</td>'
        f'<td class="record-date">{prec_link}</td></tr>\n'
        f'    <tr><th>Najbogatejši mesec s padavinami</th>'
        f'<td class="record-val">{num(month_precs.get(wettest_ym))} mm</td>'
        f'<td class="record-date">{ym_link(wettest_ym)}</td></tr>\n'
        f'    <tr><th>Najsušnejši mesec (≥20 meritev)</th>'
        f'<td class="record-val">{num(month_precs.get(driest_ym))} mm</td>'
        f'<td class="record-date">{ym_link(driest_ym)}</td></tr>'
    )
    rows_wind = (
        f'    <tr><th>Najmočnejši izmerjeni sunek vetra</th>'
        f'<td class="record-val">{wind_str}</td><td class="record-date">{wind_link}</td></tr>'
    )

    schema = "\n".join([webpage_schema(url, title, desc), crumbs_schema(crumbs)])
    body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">Vremenski rekordi</h1>
  <p class="post-meta">Postaja IREICA1 · Rečica ob Savinji · meritve od novembra 2019</p>

  <h2>Temperatura</h2>
  <table class="stats">
{rows_temp}
  </table>

  <h2>Padavine</h2>
  <table class="stats">
{rows_prec}
  </table>

  <h2>Veter</h2>
  <table class="stats">
{rows_wind}
  </table>

  <p class="muted-note">Vir: meteorološka postaja IREICA1, Rečica ob Savinji, Savinjska dolina ({ELEV} m n. m.).
  Rekordi so izračunani iz vseh razpoložljivih dnevnih meritev.</p>
  <a class="back-link" href="/vreme/">← Vremenski arhiv</a>'''

    html = page_shell(title, desc, url, schema, body)
    write_page(rel, html, force=True)
    sitemap_urls.append(sitemap_entry(SITE + url, lastmod, "weekly", "0.7"))


def gen_phenomena_pages(hist, sitemap_urls):
    written = 0
    lastmod = TODAY.isoformat()

    # Classify days
    frost_days = [(d, v) for d, v in sorted(hist.items()) if is_frost(v)]
    hot_days = [(d, v) for d, v in sorted(hist.items()) if is_hot(v)]
    rain_days = [(d, v) for d, v in sorted(hist.items()) if is_heavy_rain(v)]

    def phenomenon_page(url, rel, title, desc, intro, term_name, definition, icon, days, value_fn, value_label, crumbs):
        rows = []
        for date, v in sorted(days, reverse=True):
            y, m, d = int(date[:4]), int(date[5:7]), int(date[8:10])
            val = value_fn(v)
            rows.append(
                f'      <tr>'
                f'<td><a href="/vreme/{y}/{m:02d}/{d:02d}/">{d}. {MES_GEN[m]} {y}</a></td>'
                f'<td>{num(v.get("tempAvg"))} °C</td>'
                f'<td>{num(v.get("tempLow"))} °C / {num(v.get("tempHigh"))} °C</td>'
                f'<td>{val}</td>'
                f'</tr>'
            )
        table = (
            '  <table class="stats">\n'
            '    <thead><tr><th>Datum</th><th>Povp. T</th><th>Min / Max T</th>'
            f'<th>{value_label}</th></tr></thead>\n'
            '    <tbody>\n' + "\n".join(rows[:500]) + '\n    </tbody>\n  </table>'
        )
        schema = "\n".join([
            webpage_schema(url, title, desc),
            crumbs_schema(crumbs),
            defined_term_schema(term_name, definition, url, "/pojavi/"),
        ])
        body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">{icon} {title.split(" —")[0]}</h1>
  <p class="post-meta">Postaja IREICA1 · Rečica ob Savinji · {len(days)} dni od novembra 2019</p>
  <p class="archive-intro">{intro}</p>
{table}
  <p class="muted-note">Prikazanih je do 500 najnovejših dni. Vir: postaja IREICA1, Rečica ob Savinji.</p>
  <a class="back-link" href="/pojavi/">← Vremenski pojavi</a>'''
        html = page_shell(title, desc, url, schema, body)
        write_page(rel, html, force=True)

    # Frost page
    phenomenon_page(
        "/pojavi/zmrzal/", "pojavi/zmrzal/index.html",
        "Zmrzal — Rečica ob Savinji",
        f"Dnevi z najnižjo temperaturo ≤ 0 °C v Rečici ob Savinji. Postaja IREICA1 je zabeležila {len(frost_days)} zmrzalnih dni od novembra 2019.",
        f"Zmrzal nastopi, ko dnevna najnižja temperatura pade na 0 °C ali nižje. Postaja IREICA1 je od novembra 2019 zabeležila skupaj <strong>{len(frost_days)} dni z zmrzaljo</strong> v Rečici ob Savinji.",
        "Zmrzal",
        "Zmrzal je vremenski pojav, pri katerem dnevna najnižja temperatura zraka pade na 0 °C ali manj.",
        "❄",
        frost_days,
        lambda v: f"{num(v.get('tempLow'))} °C",
        "Najnižja T",
        [("Meteorec", "/"), ("Vremenski arhiv", "/vreme/"), ("Pojavi", "/pojavi/"), ("Zmrzal", None)],
    )
    sitemap_urls.append(sitemap_entry(f"{SITE}/pojavi/zmrzal/", lastmod, "monthly", "0.6"))

    # Hot day page
    phenomenon_page(
        "/pojavi/vroč-dan/", "pojavi/vroč-dan/index.html",
        "Vroč dan — Rečica ob Savinji",
        f"Dnevi z najvišjo temperaturo ≥ 30 °C v Rečici ob Savinji. Postaja IREICA1 je zabeležila {len(hot_days)} vročih dni od novembra 2019.",
        f"Vroč dan nastopi, ko dnevna najvišja temperatura doseže ali preseže 30 °C. Postaja IREICA1 je od novembra 2019 zabeležila skupaj <strong>{len(hot_days)} vročih dni</strong> v Rečici ob Savinji.",
        "Vroč dan",
        "Vroč dan je dan, na katerega dnevna najvišja temperatura zraka doseže ali preseže 30 °C.",
        "☀",
        hot_days,
        lambda v: f"{num(v.get('tempHigh') or v.get('tempAvg'))} °C",
        "Nejvišja T",
        [("Meteorec", "/"), ("Vremenski arhiv", "/vreme/"), ("Pojavi", "/pojavi/"), ("Vroč dan", None)],
    )
    sitemap_urls.append(sitemap_entry(f"{SITE}/pojavi/vroč-dan/", lastmod, "monthly", "0.6"))

    # Heavy rain page
    phenomenon_page(
        "/pojavi/naliv/", "pojavi/naliv/index.html",
        "Nalivi — Rečica ob Savinji",
        f"Dnevi z dnevno količino padavin ≥ 20 mm v Rečici ob Savinji. Postaja IREICA1 je zabeležila {len(rain_days)} nalivov od novembra 2019.",
        f"Naliv opredelimo kot dan z vsaj 20 mm padavin. Postaja IREICA1 je od novembra 2019 zabeležila skupaj <strong>{len(rain_days)} nalivov</strong> v Rečici ob Savinji.",
        "Naliv",
        "Naliv je dan z vsaj 20 mm padavin v 24 urah.",
        "🌧",
        rain_days,
        lambda v: f"{num(v.get('precipTotal'))} mm",
        "Padavine",
        [("Meteorec", "/"), ("Vremenski arhiv", "/vreme/"), ("Pojavi", "/pojavi/"), ("Nalivi", None)],
    )
    sitemap_urls.append(sitemap_entry(f"{SITE}/pojavi/naliv/", lastmod, "monthly", "0.6"))

    # Phenomena index
    url = "/pojavi/"
    rel = "pojavi/index.html"
    title = "Vremenski pojavi — Rečica ob Savinji"
    desc = ("Arhiv vremenskih pojavov v Rečici ob Savinji: zmrzal, vroči dnevi in nalivi. "
            "Meritve postaje IREICA1 od novembra 2019.")
    crumbs = [("Meteorec", "/"), ("Vremenski arhiv", "/vreme/"), ("Pojavi", None)]

    terms = [
        ("Zmrzal", "Zmrzal je vremenski pojav, pri katerem dnevna najnižja temperatura zraka pade na 0 °C ali manj.", "/pojavi/zmrzal/"),
        ("Vroč dan", "Vroč dan je dan, na katerega dnevna najvišja temperatura zraka doseže ali preseže 30 °C.", "/pojavi/vroč-dan/"),
        ("Naliv", "Naliv je dan z vsaj 20 mm padavin v 24 urah.", "/pojavi/naliv/"),
    ]
    schema = "\n".join([
        webpage_schema(url, title, desc),
        crumbs_schema(crumbs),
        defined_term_set_schema(title, url, terms),
    ])
    body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">Vremenski pojavi</h1>
  <p class="archive-intro">Arhiv posebnih vremenskih pojavov v <strong>Rečici ob Savinji</strong>,
  zabeleženih na postaji IREICA1 od novembra 2019.</p>
  <div class="card-grid">
    <a class="phenom-card" href="/pojavi/zmrzal/">
      <span class="ph-icon">❄</span>
      Zmrzal
      <div class="ph-count">{len(frost_days)} dni</div>
    </a>
    <a class="phenom-card" href="/pojavi/vroč-dan/">
      <span class="ph-icon">☀</span>
      Vroč dan
      <div class="ph-count">{len(hot_days)} dni</div>
    </a>
    <a class="phenom-card" href="/pojavi/naliv/">
      <span class="ph-icon">🌧</span>
      Naliv
      <div class="ph-count">{len(rain_days)} dni</div>
    </a>
  </div>
  <a class="back-link" href="/vreme/">← Vremenski arhiv</a>'''

    html = page_shell(title, desc, url, schema, body)
    write_page(rel, html, force=True)
    sitemap_urls.append(sitemap_entry(SITE + url, lastmod, "monthly", "0.7"))


def gen_seasonal_pages(hist, sitemap_urls):
    # Seasons: pomlad=Mar-May, poletje=Jun-Aug, jesen=Sep-Nov, zima=Dec-Feb
    seasons = {
        "pomlad": {"months": [3, 4, 5], "label": "Pomlad", "color": "season-pomlad",
                   "desc": "Pomladni meseci (marec, april, maj)"},
        "poletje": {"months": [6, 7, 8], "label": "Poletje", "color": "season-poletje",
                    "desc": "Poletni meseci (junij, julij, avgust)"},
        "jesen": {"months": [9, 10, 11], "label": "Jesen", "color": "season-jesen",
                  "desc": "Jesenski meseci (september, oktober, november)"},
        "zima": {"months": [12, 1, 2], "label": "Zima", "color": "season-zima",
                 "desc": "Zimski meseci (december, januar, februar)"},
    }

    # Find all years with data
    years_with_data = sorted({int(d[:4]) for d in hist})
    written = 0

    for season_key, sinfo in seasons.items():
        for y in years_with_data:
            if season_key == "zima":
                # Winter spans two calendar years: Dec(y-1) + Jan,Feb(y)
                months_dates = (
                    [(d, v) for d, v in hist.items() if d.startswith(f"{y-1}-12")] +
                    [(d, v) for d, v in hist.items() if d.startswith(f"{y}-01")] +
                    [(d, v) for d, v in hist.items() if d.startswith(f"{y}-02")]
                )
                season_label = f"Zima {y-1}–{y}"
                url_slug = f"zima-{y-1}-{y}"
                url_str = f"/zima-{y-1}-{y}/"
                rel = f"zima-{y-1}-{y}/index.html"
            else:
                months_dates = []
                for m in sinfo["months"]:
                    prefix = f"{y}-{m:02d}"
                    months_dates += [(d, v) for d, v in hist.items() if d.startswith(prefix)]
                season_label = f"{sinfo['label']} {y}"
                url_str = f"/{season_key}-{y}/"
                rel = f"{season_key}-{y}/index.html"

            if len(months_dates) < 60:
                continue

            s = month_stats(months_dates)
            if not s:
                continue

            # Only generate for complete or mostly complete seasons (≥80% of days)
            expected = 92  # ~3 months
            if s["count"] < int(expected * 0.7):
                continue

            lastmod = max(d for d, _ in months_dates)
            is_past = lastmod < TODAY.isoformat()

            title = f"{season_label} — Rečica ob Savinji"
            desc = (f"Vremenski pregled za {season_label.lower()} v Rečici ob Savinji: "
                    f"povp. temperatura {num(s['tavg'])} °C, padavine {num(s['prec_total'])} mm. "
                    f"Postaja IREICA1.")

            crumbs = [("Meteorec", "/"), ("Vremenski arhiv", "/vreme/"), (season_label, None)]

            cards = f'''  <div class="stat-grid">
    <div class="stat-card c-temp">
      <div class="sc-label">Povp. temperatura</div>
      <div class="sc-val {sinfo['color']}">{num(s['tavg'])} °C</div>
      <div class="sc-sub">{s['count']} dni meritev</div>
    </div>
    <div class="stat-card c-up">
      <div class="sc-label">Sezonski max.</div>
      <div class="sc-val">{num(s['tmax'])} °C</div>
    </div>
    <div class="stat-card c-down">
      <div class="sc-label">Sezonski min.</div>
      <div class="sc-val">{num(s['tmin'])} °C</div>
    </div>
    <div class="stat-card c-rain">
      <div class="sc-label">Padavine skupaj</div>
      <div class="sc-val">{num(s['prec_total'])} mm</div>
    </div>
  </div>'''

            schema = "\n".join([webpage_schema(url_str, title, desc), crumbs_schema(crumbs)])
            body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">{season_label}</h1>
  <p class="post-meta">Rečica ob Savinji · postaja IREICA1 · {sinfo["desc"]}</p>
{cards}
  <p class="muted-note">Vir: meteorološka postaja IREICA1, Rečica ob Savinji ({ELEV} m n. m.).</p>
  <a class="back-link" href="/vreme/">← Vremenski arhiv</a>'''

            html = page_shell(title, desc, url_str, schema, body)
            write_page(rel, html, force=True)
            written += 1
            sitemap_urls.append(sitemap_entry(SITE + url_str, lastmod, "yearly" if is_past else "monthly", "0.6"))

    return written


def climate_facts(hist):
    """Compute the climate summary used by landing + nearby-town pages."""
    vals = list(hist.values())
    tavg_all = [v["tempAvg"] for v in vals if v.get("tempAvg") is not None]
    hum_all = [v["humidityAvg"] for v in vals if v.get("humidityAvg") is not None]

    tmax_d, tmax_v = max(((d, v["tempHigh"]) for d, v in hist.items()
                          if v.get("tempHigh") is not None), key=lambda x: x[1])
    tmin_d, tmin_v = min(((d, v["tempLow"]) for d, v in hist.items()
                          if v.get("tempLow") is not None), key=lambda x: x[1])
    prec_d, prec_v = max(((d, v["precipTotal"]) for d, v in hist.items()
                          if v.get("precipTotal") is not None), key=lambda x: x[1])
    wind_d, wind_v = max(((d, v["windspeedHigh"]) for d, v in hist.items()
                          if v.get("windspeedHigh") is not None), key=lambda x: x[1])

    yr = defaultdict(list)
    for d, v in hist.items():
        if v.get("tempAvg") is not None:
            yr[int(d[:4])].append(v["tempAvg"])
    full_years = sorted(y for y in yr if len(yr[y]) >= 350)
    trend = None
    if len(full_years) >= 3:
        ys = [st.mean(yr[y]) for y in full_years]
        mx, my = st.mean(full_years), st.mean(ys)
        denom = sum((x - mx) ** 2 for x in full_years)
        if denom:
            trend = sum((full_years[i] - mx) * (ys[i] - my)
                        for i in range(len(full_years))) / denom

    ymp = defaultdict(float)
    for d, v in hist.items():
        ymp[d[:7]] += v.get("precipTotal", 0) or 0
    permonth = defaultdict(list)
    for ym, t in ymp.items():
        permonth[int(ym[5:7])].append(t)
    wettest_m = max(permonth, key=lambda m: st.mean(permonth[m]))

    return {
        "mean_t": st.mean(tavg_all) if tavg_all else None,
        "mean_hum": st.mean(hum_all) if hum_all else None,
        "frost_days": sum(1 for v in vals if v.get("tempLow") is not None and v["tempLow"] <= 0),
        "tmax_d": tmax_d, "tmax_v": tmax_v, "tmin_d": tmin_d, "tmin_v": tmin_v,
        "prec_d": prec_d, "prec_v": prec_v, "wind_d": wind_d, "wind_v": wind_v,
        "trend": trend, "full_years": full_years, "wettest_m": wettest_m,
        "first_date": min(hist.keys()), "n_days": len(hist),
        "annual_precip": st.mean([sum(v.get("precipTotal", 0) or 0
                                  for d, v in hist.items() if d.startswith(str(y)))
                                  for y in full_years]) if full_years else None,
    }


# Nearby towns without an official ARSO station. Distances are approximate
# air-line km from the IREICA1 station in Rečica ob Savinji.
NEARBY_TOWNS = [
    {"slug": "vreme-mozirje", "town": "Mozirje", "loc": "Mozirju", "gen": "Mozirja",
     "km": 4, "dir": "vzhodno", "short": "spodnji del doline",
     "note": "največji kraj in upravno središče spodnjega dela Zgornje Savinjske doline"},
    {"slug": "vreme-nazarje", "town": "Nazarje", "loc": "Nazarjah", "gen": "Nazarij",
     "km": 5, "dir": "jugozahodno", "short": "sotočje Drete in Savinje",
     "note": "kraj ob sotočju Drete in Savinje v Zgornji Savinjski dolini"},
    {"slug": "vreme-ljubno-ob-savinji", "town": "Ljubno ob Savinji", "loc": "Ljubnem ob Savinji",
     "gen": "Ljubnega ob Savinji", "km": 9, "dir": "zahodno, gorvodno ob Savinji",
     "short": "zgornji del doline",
     "note": "kraj v ožjem, višje ležečem zahodnem delu Zgornje Savinjske doline"},
]


def gen_nearby_town_pages(hist, sitemap_urls):
    """Honest 'nearest station' pages for neighbouring towns without a station."""
    f = climate_facts(hist)
    lastmod = max(hist.keys())

    def dl(d):
        y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
        return f'<a href="/vreme/{y}/{m:02d}/{dd:02d}/">{dd}. {MES_GEN[m]} {y}</a>'

    trend = f["trend"]
    trend_txt = (f"+{num(trend, 2)} °C na leto" if trend and trend > 0
                 else f"{num(trend, 2)} °C na leto")

    for t in NEARBY_TOWNS:
        town, km, dirn = t["town"], t["km"], t["dir"]
        url = f"/{t['slug']}/"
        rel = f"{t['slug']}/index.html"

        title = f"Vreme {town} — najbližja meritev (postaja IREICA1, {km} km)"
        desc = (f"Vreme za {town} ({t['short']}): {town} nima lastne postaje ARSO. "
                f"Najbližje neprekinjene meritve so s postaje IREICA1 v Rečici ob Savinji, "
                f"približno {km} km {dirn}. Temperatura, padavine, megla in trend segrevanja.")

        crumbs = [("Meteorec", "/"), (f"Vreme {town}", None)]

        disclaimer = (f'  <div class="partial-note">Pomembno: {town} nima lastne uradne '
                      f'meteorološke postaje. Spodnji podatki so dejanske meritve postaje '
                      f'<strong>IREICA1 v Rečici ob Savinji</strong> — najbližje neprekinjene '
                      f'meritve, približno <strong>{km} km {dirn}</strong> od {t["gen"]}. Zaradi '
                      f'enake lege na dnu Zgornje Savinjske doline so razmere zelo primerljive, '
                      f'a niso izmerjene v samem kraju.</div>'.replace("\n", " "))

        intro = f'''  <p class="archive-intro">
  <strong>{town}</strong> je {t["note"]}. Za napoved
  in trenutno vreme v {t["loc"]} velja enak kotlinski vzorec kot v bližnji Rečici ob Savinji:
  hladnejša jutra na dnu doline, pogosta jesenska in zimska megla ter razmeroma obilne padavine.
  Postaja IREICA1 ({km} km {dirn}) ponuja {f["n_days"]} dni realnih meritev — za razliko od
  splošnih napovedi, ki za to območje računajo le iz modela.</p>'''

        facts = f'''  <h2>Podnebje v okolici {t["gen"]} (meritve IREICA1)</h2>
  <table class="stats">
    <tr><th>Povprečna letna temperatura</th><td>{num(f["mean_t"])} °C</td></tr>
    <tr><th>Absolutni temperaturni razpon</th><td>{num(f["tmin_v"])} °C … {num(f["tmax_v"])} °C</td></tr>
    <tr><th>Dni z zmrzaljo (od 2019)</th><td>{f["frost_days"]}</td></tr>
    <tr><th>Povprečna relativna vlažnost</th><td>{num(f["mean_hum"], 0)} %</td></tr>
    <tr><th>Povprečne letne padavine</th><td>{num(f["annual_precip"], 0)} mm</td></tr>
    <tr><th>Dnevni rekord padavin</th><td>{num(f["prec_v"])} mm ({dl(f["prec_d"])})</td></tr>
    <tr><th>Najmočnejši sunek vetra</th><td>{num(f["wind_v"])} km/h ({dl(f["wind_d"])})</td></tr>
    <tr><th>Trend segrevanja</th><td>{trend_txt}</td></tr>
  </table>'''

        cta = f'''  <div class="stat-grid" style="margin-top:1.5rem">
    <a class="stat-card c-temp" href="/" style="text-decoration:none">
      <div class="sc-label">Trenutno vreme</div><div class="sc-val">V živo →</div>
      <div class="sc-sub">Postaja IREICA1</div></a>
    <a class="stat-card c-rain" href="/vreme-recica-ob-savinji/" style="text-decoration:none">
      <div class="sc-label">Mikroklima doline</div><div class="sc-val">Več →</div>
      <div class="sc-sub">Megla, inverzija, veter</div></a>
    <a class="stat-card c-up" href="/vreme/" style="text-decoration:none">
      <div class="sc-label">Vremenski arhiv</div><div class="sc-val">Po dnevih →</div>
      <div class="sc-sub">Od 2019</div></a>
  </div>'''

        qa = [
            (f"Ima {town} svojo vremensko postajo?",
             f"{town} nima lastne uradne postaje ARSO. Najbližje neprekinjene meritve vremena "
             f"prihajajo s postaje IREICA1 v Rečici ob Savinji, približno {km} km {dirn}."),
            (f"Kako daleč je najbližja postaja od {t['gen']}?",
             f"Postaja IREICA1 v Rečici ob Savinji je približno {km} km {dirn} od {t['gen']} "
             f"in od leta 2019 neprekinjeno meri temperaturo, padavine, vlago in veter."),
            (f"So meritve IREICA1 reprezentativne za {town}?",
             f"Ker {town} leži v istem delu Zgornje Savinjske doline na podobni nadmorski višini, "
             f"so temperature, megla in padavinski vzorci večinoma primerljivi. Lokalne razlike "
             f"(npr. izpostavljenost soncu ali vetru) so vseeno mogoče."),
        ]
        faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
            f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
        ) + "\n  </div>"

        place_about = (f'<script type="application/ld+json">\n'
                       f'{{"@context":"https://schema.org","@type":"Place",'
                       f'"name":{json.dumps(town)},"address":{{"@type":"PostalAddress",'
                       f'"addressLocality":{json.dumps(town)},'
                       f'"addressRegion":"Zgornja Savinjska dolina","addressCountry":"SI"}}}}\n</script>')
        schema = "\n".join([
            webpage_schema(url, title, desc),
            crumbs_schema(crumbs),
            faq_schema(qa),
            place_about,
        ])

        body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">Vreme {town}</h1>
  <p class="post-meta">Najbližja postaja IREICA1 · {km} km {dirn} · Zgornja Savinjska dolina</p>
{disclaimer}
{intro}
{cta}
{facts}
{faq_html}
  <p class="muted-note">Vir meritev: postaja IREICA1, Rečica ob Savinji ({ELEV} m n. m.).
  Vrednosti niso izmerjene v {t["loc"]}, temveč na najbližji postaji.</p>
  <a class="back-link" href="/vreme-recica-ob-savinji/">← Vreme Rečica ob Savinji</a>'''

        html = page_shell(title, desc, url, schema, body)
        write_page(rel, html, force=True)
        sitemap_urls.append(sitemap_entry(SITE + url, lastmod, "weekly", "0.7"))


def gen_landing_page(hist, sitemap_urls):
    """Hand-curated exact-match landing page: /vreme-recica-ob-savinji/."""
    url = "/vreme-recica-ob-savinji/"
    rel = "vreme-recica-ob-savinji/index.html"
    lastmod = max(hist.keys())

    # ── Climate facts (shared with nearby-town pages) ────────────────────────
    f = climate_facts(hist)
    mean_t, mean_hum, frost_days = f["mean_t"], f["mean_hum"], f["frost_days"]
    tmax_d, tmax_v = f["tmax_d"], f["tmax_v"]
    tmin_d, tmin_v = f["tmin_d"], f["tmin_v"]
    prec_d, prec_v = f["prec_d"], f["prec_v"]
    wind_d, wind_v = f["wind_d"], f["wind_v"]
    trend, full_years = f["trend"], f["full_years"]
    wettest_m, first_date = f["wettest_m"], f["first_date"]
    n_days, annual_precip = f["n_days"], f["annual_precip"]

    def dl(d):
        y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
        return f'<a href="/vreme/{y}/{m:02d}/{dd:02d}/">{dd}. {MES_GEN[m]} {y}</a>'

    trend_txt = (f"+{num(trend, 2)} °C na leto" if trend and trend > 0
                 else f"{num(trend, 2)} °C na leto")

    title = "Vreme Rečica ob Savinji — meritve v živo in lokalna mikroklima"
    desc = (f"Vreme v Rečici ob Savinji (Zgornja Savinjska dolina, {ELEV} m n. m.): meritve "
            f"v živo in {n_days} dni arhiva postaje IREICA1. Mikroklima doline, megla, "
            f"inverzija, veter in trend segrevanja {trend_txt}.")

    crumbs = [("Meteorec", "/"), ("Vreme Rečica ob Savinji", None)]

    # ── Curated prose (uses computed figures) ────────────────────────────────
    intro = f'''  <p class="archive-intro">
  <strong>Rečica ob Savinji</strong> leži na dnu <strong>Zgornje Savinjske doline</strong> na
  približno {ELEV} m nadmorske višine. Meteorološka postaja <strong>IREICA1</strong> tu neprekinjeno
  meri vreme od {fmtd(first_date)} — skupaj že <strong>{n_days} dni</strong> podatkov o temperaturi,
  padavinah, vlagi in vetru. Za razliko od splošnih napovedi, ki za to območje ponujajo le model,
  so spodnji podatki <strong>dejanske meritve</strong> z lokacije.</p>'''

    micro = f'''  <h2>Mikroklima Rečice ob Savinji</h2>
  <p>Dno alpske doline ima izrazito <strong>kotlinsko mikroklimo</strong>. Hladen zrak se ob jasnih
  nočeh nabira na dnu doline, zato so jutra pogosto hladnejša od okoliških pobočij. Postaja IREICA1
  je doslej zabeležila <strong>{frost_days} dni z zmrzaljo</strong> (najnižja dnevna temperatura ≤ 0 °C),
  povprečna letna temperatura pa znaša <strong>{num(mean_t)} °C</strong>. Absolutni temperaturni razpon
  sega od {num(tmin_v)} °C ({dl(tmin_d)}) do {num(tmax_v)} °C ({dl(tmax_d)}).</p>

  <h2>Megla in temperaturna inverzija</h2>
  <p>Visoka povprečna relativna vlažnost (<strong>{num(mean_hum, 0)} %</strong>) in zaprta lega doline
  pomenita pogosto <strong>radiacijsko meglo</strong> ter <strong>temperaturne inverzije</strong>,
  predvsem pozno jeseni in pozimi. V takih razmerah je na dnu doline mrzlo in megleno, nekaj sto metrov
  višje pa sončno in toplo — klasičen savinjski inverzijski vzorec.</p>

  <h2>Padavine in veter</h2>
  <p>Območje je razmeroma namočeno: povprečno okrog <strong>{num(annual_precip, 0)} mm padavin na leto</strong>,
  z viškom v {MES_LOC[wettest_m]} zaradi poletnih neviht. Dnevni rekord padavin postaje znaša
  <strong>{num(prec_v)} mm</strong> ({dl(prec_d)}). Vetrovi so večinoma šibki in kanalizirani po osi doline,
  najmočnejši zabeleženi sunek pa je dosegel <strong>{num(wind_v)} km/h</strong> ({dl(wind_d)}).
  Avgusta 2023 je širše območje Zgornje Savinjske doline prizadela <a href="/blog/poplave-2023.html">katastrofalna
  poplava</a>.</p>

  <h2>Podnebje se segreva</h2>
  <p>Iz arhiva postaje je razviden jasen trend: povprečna letna temperatura v Rečici ob Savinji narašča za
  približno <strong>{trend_txt}</strong> (obdobje {full_years[0]}–{full_years[-1]}). Najtoplejše leto doslej je
  bilo 2024 s povprečjem nad 11 °C.</p>'''

    cta = '''  <div class="stat-grid" style="margin-top:1.5rem">
    <a class="stat-card c-temp" href="/" style="text-decoration:none">
      <div class="sc-label">Trenutno vreme</div>
      <div class="sc-val">V živo →</div>
      <div class="sc-sub">Meritve postaje IREICA1</div>
    </a>
    <a class="stat-card c-rain" href="/vreme/" style="text-decoration:none">
      <div class="sc-label">Vremenski arhiv</div>
      <div class="sc-val">Po dnevih →</div>
      <div class="sc-sub">Od novembra 2019</div>
    </a>
    <a class="stat-card c-up" href="/rekord/" style="text-decoration:none">
      <div class="sc-label">Rekordi</div>
      <div class="sc-val">Ekstremi →</div>
      <div class="sc-sub">Temperatura, padavine, veter</div>
    </a>
  </div>'''

    # ── FAQ (visible + schema) ───────────────────────────────────────────────
    qa = [
        ("Kakšno je trenutno vreme v Rečici ob Savinji?",
         "Trenutne meritve temperature, padavin, vlage in vetra v živo objavlja meteorološka "
         "postaja IREICA1 na naslovni strani Meteorec (meteorec.si). Podatki so dejanske meritve "
         "z lokacije v Rečici ob Savinji, ne le napoved iz modela."),
        ("Kje stoji vremenska postaja v Rečici ob Savinji?",
         f"Postaja IREICA1 stoji v Rečici ob Savinji na dnu Zgornje Savinjske doline, na približno "
         f"{ELEV} m nadmorske višine. Meritve so na voljo od novembra 2019."),
        ("Zakaj je v Savinjski dolini tako pogosto megleno?",
         "Zaradi zaprte lege doline in visoke vlažnosti se hladen zrak ob jasnih nočeh nabira na dnu "
         "doline, kar povzroča radiacijsko meglo in temperaturne inverzije, zlasti jeseni in pozimi."),
        ("Se podnebje v Rečici ob Savinji segreva?",
         f"Da. Iz arhiva postaje IREICA1 je razviden trend naraščanja povprečne letne temperature za "
         f"približno {num(trend, 2)} °C na leto v obdobju {full_years[0]}–{full_years[-1]}."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    # ── Nearby towns (internal-linking hub) ──────────────────────────────────
    town_links = " · ".join(
        f'<a href="/{t["slug"]}/">Vreme {t["town"]}</a>' for t in NEARBY_TOWNS
    )
    nearby_html = (f'  <h2>Vreme v bližnjih krajih</h2>\n'
                   f'  <p>Sosednji kraji v Zgornji Savinjski dolini nimajo lastne postaje ARSO — '
                   f'meritve IREICA1 so zanje najbližji realni vir: {town_links}.</p>')

    # ── Schema ───────────────────────────────────────────────────────────────
    latest = hist[lastmod]
    observations = [
        {"name": "Povprečna temperatura", "value": latest.get("tempAvg"), "unit": "°C"},
        {"name": "Najvišja temperatura", "value": latest.get("tempHigh"), "unit": "°C"},
        {"name": "Najnižja temperatura", "value": latest.get("tempLow"), "unit": "°C"},
        {"name": "Padavine", "value": latest.get("precipTotal"), "unit": "mm"},
        {"name": "Relativna vlažnost", "value": latest.get("humidityAvg"), "unit": "%"},
        {"name": "Najmočnejši sunek vetra", "value": latest.get("windspeedHigh"), "unit": "km/h"},
    ]
    observations = [o for o in observations if o["value"] is not None]
    schema = "\n".join([
        webpage_schema(url, title, desc),
        crumbs_schema(crumbs),
        faq_schema(qa),
        dataset_schema(url, observations),
    ])

    body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">Vreme Rečica ob Savinji</h1>
  <p class="post-meta">Meritve v živo · postaja IREICA1 · Zgornja Savinjska dolina · {ELEV} m n. m.</p>
{intro}
{cta}
{micro}
{nearby_html}
{faq_html}
  <p class="muted-note">Vir: meteorološka postaja IREICA1, Rečica ob Savinji ({ELEV} m n. m.), Zgornja
  Savinjska dolina. Vrednosti so dnevni povzetki, izračunani iz {n_days} dni meritev.</p>
  <a class="back-link" href="/">← Trenutno vreme v živo</a>'''

    html = page_shell(title, desc, url, schema, body)
    write_page(rel, html, force=True)
    sitemap_urls.append(sitemap_entry(SITE + url, lastmod, "weekly", "0.9"))


GLOSS_CAT_LABELS = {
    "vlaga": "Vlaga", "padavine": "Padavine", "oblaki": "Oblaki", "veter": "Veter",
    "tlak": "Zračni tlak", "temperatura": "Temperatura", "sevanje": "Sevanje",
}
GLOSS_CATS = ["vlaga", "padavine", "oblaki", "veter", "tlak", "temperatura", "sevanje"]


def slovar_slug(term):
    """URL slug from a glossary term name — strips a trailing parenthetical
    synonym/translation (e.g. 'Fen (Föhn)' -> 'fen') and transliterates
    Slovenian diacritics."""
    base = re.sub(r"\s*\([^)]*\)\s*$", "", term).strip() or term
    base = base.replace("(", "").replace(")", "")
    base = base.translate(str.maketrans("čšžćđČŠŽĆĐ", "cszcdCSZCD"))
    base = base.lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def load_glossary_terms():
    """Parse GLOSSARY_TERMS straight out of app.js so the slovarček pages
    can never drift from the live glossary tab — this is the one source of
    truth for term text."""
    src = open(os.path.join(ROOT, "app.js"), encoding="utf-8").read()
    m = re.search(r"const GLOSSARY_TERMS=\[(.*?)\n\];", src, re.S)
    block = m.group(1)
    raw = re.findall(
        r"\{term:'((?:[^'\\]|\\.)*)',icon:'([^']*)',cat:'([^']*)',\s*"
        r"def:'((?:[^'\\]|\\.)*)',\s*"
        r"fun:'((?:[^'\\]|\\.)*)',",
        block,
    )
    def unescape(s):
        return s.replace("\\'", "'").replace('\\"', '"')

    terms = []
    for term, icon, cat, definition, fun in raw:
        terms.append({
            "term": unescape(term), "icon": icon, "cat": cat,
            "def": unescape(definition), "fun": unescape(fun),
            "slug": slovar_slug(unescape(term)),
        })
    return terms


def gen_slovar_pages(sitemap_urls):
    terms = load_glossary_terms()
    lastmod = TODAY.isoformat()

    for t in terms:
        url = f"/slovar/{t['slug']}/"
        rel = f"slovar/{t['slug']}/index.html"
        short_name = re.sub(r"\s*\([^)]*\)\s*$", "", t["term"]).strip() or t["term"]
        title = f"Kaj je {short_name.lower()}? — Vremenski slovar"
        desc = t["def"] if len(t["def"]) <= 155 else t["def"][:152].rsplit(" ", 1)[0] + "…"
        crumbs = [("Meteorec", "/"), ("Slovar", "/slovar/"), (t["term"], None)]

        qa = [(f"Kaj je {short_name.lower()}?", t["def"])]
        schema = "\n".join([
            webpage_schema(url, title, desc),
            crumbs_schema(crumbs),
            defined_term_schema(t["term"], t["def"], url, "/slovar/"),
            faq_schema(qa),
        ])
        cat_label = GLOSS_CAT_LABELS.get(t["cat"], t["cat"])
        body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">{t["icon"]} {t["term"]}</h1>
  <p class="post-meta">Vremenski slovar · <a href="/slovar/#{t["cat"]}">{cat_label}</a></p>
  <p class="archive-intro">{t["def"]}</p>
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">💡 Zanimivost</div>
    <p class="archive-intro" style="margin:.4rem 0 0">{t["fun"]}</p>
  </div>
  <p class="muted-note">Poglej tudi <a href="/slovar/">celoten vremenski slovar</a> ali
  <a href="/">trenutne meritve v živo</a> iz Rečice ob Savinji.</p>
  <a class="back-link" href="/slovar/">← Vremenski slovar</a>'''

        html = page_shell(title, desc, url, schema, body)
        write_page(rel, html, force=True)
        sitemap_urls.append(sitemap_entry(SITE + url, lastmod, "monthly", "0.5"))

    # ── /slovar/ index ────────────────────────────────────────────────────
    url = "/slovar/"
    rel = "slovar/index.html"
    title = "Vremenski slovar — meteorološki pojmi razloženi"
    desc = (f"Slovar {len(terms)} meteoroloških pojmov (rosišče, CAPE, burja, temperaturna inverzija …) "
            "z razlago in zanimivostjo za vsak izraz.")
    crumbs = [("Meteorec", "/"), ("Slovar", None)]

    by_cat = {}
    for t in terms:
        by_cat.setdefault(t["cat"], []).append(t)

    sections = []
    for cat in GLOSS_CATS:
        cat_terms = by_cat.get(cat, [])
        if not cat_terms:
            continue
        cards = "\n".join(
            f'    <a class="phenom-card" href="/slovar/{t["slug"]}/">\n'
            f'      <span class="ph-icon">{t["icon"]}</span>\n'
            f'      {t["term"]}\n'
            f'    </a>' for t in cat_terms
        )
        sections.append(f'  <h2 id="{cat}">{GLOSS_CAT_LABELS[cat]}</h2>\n  <div class="card-grid">\n{cards}\n  </div>')

    term_set = [(t["term"], t["def"], f"/slovar/{t['slug']}/") for t in terms]
    schema = "\n".join([
        webpage_schema(url, title, desc),
        crumbs_schema(crumbs),
        defined_term_set_schema(title, url, term_set),
    ])
    body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">Vremenski slovar</h1>
  <p class="archive-intro">Razlaga {len(terms)} meteoroloških pojmov, od osnovnih (rosišče, vlažnost) do
  naprednejših (CAPE-sorodni indeksi nestabilnosti, adiabatski gradient). Vsak pojem ima kratko razlago in
  zanimivost, pogosto vezano na Zgornjo Savinjsko dolino.</p>
{chr(10).join(sections)}
  <a class="back-link" href="/">← Trenutno vreme v živo</a>'''

    html = page_shell(title, desc, url, schema, body)
    write_page(rel, html, force=True)
    sitemap_urls.append(sitemap_entry(SITE + url, lastmod, "monthly", "0.6"))


def gen_sitemap(sitemap_urls):
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
    out = os.path.join(ROOT, "sitemap-weather.xml")
    with open(out, "w", encoding="utf-8") as f:
        f.write(xml)
    return len(entries)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate Meteorec SEO pages")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate all pages, even if they already exist")
    args = parser.parse_args()

    print(f"[{TODAY}] Nalagam history.json …")
    hist = load_history()
    print(f"  → {len(hist)} dni podatkov")

    sitemap_urls = []

    print("Generiram dnevne strani …")
    w, s = gen_daily_pages(hist, args.force, sitemap_urls)
    print(f"  → {w} novih, {s} preskočenih")

    print("Generiram mesečne strani …")
    w = gen_monthly_pages(hist, args.force, sitemap_urls)
    print(f"  → {w} strani")

    print("Generiram letne strani …")
    w = gen_yearly_pages(hist, args.force, sitemap_urls)
    print(f"  → {w} strani")

    print("Generiram arhivski indeks …")
    gen_archive_index(hist, sitemap_urls)
    print("  → /vreme/index.html")

    print("Generiram stran rekordov …")
    gen_records_page(hist, sitemap_urls)
    print("  → /rekord/index.html")

    print("Generiram strani pojavov …")
    gen_phenomena_pages(hist, sitemap_urls)
    print("  → /pojavi/ + 3 podstrani")

    print("Generiram sezonske strani …")
    w = gen_seasonal_pages(hist, sitemap_urls)
    print(f"  → {w} sezonskih strani")

    print("Generiram pristajalno stran /vreme-recica-ob-savinji/ …")
    gen_landing_page(hist, sitemap_urls)
    print("  → /vreme-recica-ob-savinji/index.html")

    print("Generiram strani za sosednje kraje …")
    gen_nearby_town_pages(hist, sitemap_urls)
    print(f"  → {len(NEARBY_TOWNS)} strani (Mozirje, Nazarje, Ljubno)")

    print("Generiram vremenski slovar …")
    n_terms = len(load_glossary_terms())
    gen_slovar_pages(sitemap_urls)
    print(f"  → /slovar/ + {n_terms} pojmov")

    print("Generiram sitemap-weather.xml …")
    n = gen_sitemap(sitemap_urls)
    print(f"  → {n} URL-jev")

    print(f"\n✓ Skupaj {len(sitemap_urls)} strani generirano/posodobljeno.")


if __name__ == "__main__":
    main()
