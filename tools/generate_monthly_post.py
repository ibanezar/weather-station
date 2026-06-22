#!/usr/bin/env python3
"""
Generator mesečnih vremenskih povzetkov za blog Meteorec.

Uporaba:
    python3 tools/generate_monthly_post.py 2026-05

Iz history.json izračuna statistiko meseca + klimatološko primerjavo
(isti mesec v prejšnjih letih) in zapiše pripravljeno HTML objavo v
blog/. Na koncu izpiše vrstice, ki jih dodaš v sitemap.xml, blog.json
in blog/index.html (ali poženi z --wire za samodejno vpisovanje).
"""
import json, sys, os, calendar, re, datetime
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
# datum objave: privzeto današnji (UTC), z možnostjo prepisa prek POST_DATE
TODAY = os.environ.get("POST_DATE") or datetime.date.today().isoformat()

MES_NOM = {1:"januar",2:"februar",3:"marec",4:"april",5:"maj",6:"junij",
           7:"julij",8:"avgust",9:"september",10:"oktober",11:"november",12:"december"}
MES_GEN = {1:"januarja",2:"februarja",3:"marca",4:"aprila",5:"maja",6:"junija",
           7:"julija",8:"avgusta",9:"septembra",10:"oktobra",11:"novembra",12:"decembra"}

def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")

def compute(ym):
    d = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    year, mon = int(ym[:4]), int(ym[5:7])
    days = sorted(k for k in d if k.startswith(ym))
    if not days:
        sys.exit(f"Ni podatkov za {ym}.")
    m = {k: d[k] for k in days}
    dim = calendar.monthrange(year, mon)[1]
    tavg = st.mean(v["tempAvg"] for v in m.values())
    # po dnevnem povprečju — dosledno za stare (high==low==avg) in nove podatke
    hi = max(m.items(), key=lambda kv: kv[1]["tempAvg"])
    lo = min(m.items(), key=lambda kv: kv[1]["tempAvg"])
    prec = sum(v["precipTotal"] for v in m.values())
    wettest = max(m.items(), key=lambda kv: kv[1]["precipTotal"])
    rainy = sum(1 for v in m.values() if v["precipTotal"] > 0.2)
    wind = max(m.items(), key=lambda kv: kv[1]["windspeedHigh"])
    hum = st.mean(v["humidityAvg"] for v in m.values())
    # klimatologija: ISTO OBDOBJE (isti dnevi v mesecu) v prejšnjih letih,
    # da je primerjava delnega meseca poštena (apples-to-apples)
    dnums = {int(k[8:10]) for k in days}
    need = max(int(len(dnums) * 0.8), 1)
    clim_t, clim_p = [], []
    for y in range(2019, year):
        mm = {k: v for k, v in d.items()
              if k.startswith(f"{y}-{mon:02d}") and int(k[8:10]) in dnums}
        if len(mm) >= need:
            clim_t.append(st.mean(v["tempAvg"] for v in mm.values()))
            clim_p.append(sum(v["precipTotal"] for v in mm.values()))
    clim_tavg = st.mean(clim_t) if clim_t else None
    clim_pavg = st.mean(clim_p) if clim_p else None
    return dict(year=year, mon=mon, days=days, dim=dim, n=len(days),
                tavg=tavg, hi=hi, lo=lo, prec=prec, wettest=wettest,
                rainy=rainy, wind=wind, hum=hum,
                clim_tavg=clim_tavg, clim_pavg=clim_pavg, clim_years=len(clim_t))

def narrative(s):
    """Vrne (pridevnik_temp, anomalija, pridevnik_pad)."""
    t = "blizu dolgoletnega povprečja"
    anom = None
    if s["clim_tavg"] is not None:
        anom = s["tavg"] - s["clim_tavg"]
        if anom >= 0.7: t = "nadpovprečno topel"
        elif anom <= -0.7: t = "hladnejši od običajnega"
    p = "s približno običajno količino padavin"
    if s["clim_pavg"]:
        r = s["prec"] / s["clim_pavg"]
        if r < 0.7: p = "izrazito suh"
        elif r > 1.3: p = "namočen"
    return t, anom, p

def dayfmt(key, mon):
    return f"{int(key[8:10])}. {MES_GEN[mon]}"

def build_html(s):
    y, mon = s["year"], s["mon"]
    nom, gen = MES_NOM[mon], MES_GEN[mon]
    slug = f"vremenski-povzetek-{nom}-{y}"
    url = f"{SITE}/blog/{slug}.html"
    tdesc, anom, pdesc = narrative(s)
    anom_str = (f"{num(abs(anom))} °C {'nad' if anom>=0 else 'pod'} dolgoletnim povprečjem"
                if anom is not None else "")
    partial = ""
    if s["n"] < s["dim"]:
        partial = (f'<div class="callout"><p><strong>Opomba:</strong> povzetek temelji na '
                   f'meritvah do {int(s["days"][-1][8:10])}. {gen} {y} '
                   f'({s["n"]} od {s["dim"]} dni) — delni mesec. Primerjava z dolgoletnim '
                   f'povprečjem velja za <strong>enako obdobje</strong> (1.–{int(s["days"][-1][8:10])}. {gen}) '
                   f'prejšnjih let.</p></div>')
    title = f"Vremenski povzetek — {nom} {y}"
    desc = (f"{nom.capitalize()} {y} v Rečici ob Savinji: povprečna dnevna "
            f"temperatura {num(s['tavg'])} °C in {num(s['prec'])} mm padavin. "
            f"Povzetek meteorološke postaje IREICA1.")
    short = (f"Povprečno {num(s['tavg'])} °C"
             + (f" ({anom_str})" if anom_str else "")
             + f" in {num(s['prec'])} mm padavin.")
    lead = (f'{nom.capitalize()} {y} je bil v <strong>Rečici ob Savinji</strong> '
            f'<span class="hl">{tdesc}</span> in <span class="hl">{pdesc}</span>. '
            f'Postaja IREICA1 (366 m n. m.) je izmerila povprečno dnevno temperaturo '
            f'<strong>{num(s["tavg"])} °C</strong>'
            + (f' ({anom_str})' if anom_str else '')
            + f' in <strong>{num(s["prec"])} mm</strong> padavin.')
    rows = [
        ("Povprečna dnevna temperatura", f"{num(s['tavg'])} °C"),
    ]
    if anom is not None:
        rows.append(("Odstopanje od dolgoletnega povprečja", f"{'+' if anom>=0 else '−'}{num(abs(anom))} °C"))
    rows += [
        ("Najtoplejši dan (po dnevnem povprečju)", f"{dayfmt(s['hi'][0],mon)} · {num(s['hi'][1]['tempAvg'])} °C"),
        ("Najhladnejši dan (po dnevnem povprečju)", f"{dayfmt(s['lo'][0],mon)} · {num(s['lo'][1]['tempAvg'])} °C"),
        ("Padavine skupaj", f"{num(s['prec'])} mm"),
        ("Deževnih dni", f"{s['rainy']}"),
        ("Najbolj moker dan", f"{dayfmt(s['wettest'][0],mon)} · {num(s['wettest'][1]['precipTotal'])} mm"),
        ("Najmočnejši sunek vetra", f"{dayfmt(s['wind'][0],mon)} · {num(s['wind'][1]['windspeedHigh'])} km/h"),
        ("Povprečna vlažnost", f"{num(s['hum'],0)} %"),
    ]
    rows_html = "\n".join(f'      <tr><th>{k}</th><td>{v}</td></tr>' for k, v in rows)
    html = f'''<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="UTF-8">
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-LE8PJ1HR8B"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-LE8PJ1HR8B');
</script>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | Meteorec, Rečica ob Savinji</title>
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="sl" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<meta name="description" content="{desc}">
<meta name="keywords" content="vreme {nom} {y}, Rečica ob Savinji, vremenski povzetek, IREICA1, Savinjska dolina, padavine, temperatura">
<meta name="robots" content="index, follow">
<meta name="author" content="Filip Eremita">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="Meteorec">
<meta property="og:title" content="{title}, Rečica ob Savinji">
<meta property="og:description" content="{short}">
<meta property="og:image" content="{SITE}/og/{slug}.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="sl_SI">
<meta property="article:published_time" content="{TODAY}">
<meta property="article:author" content="Filip Eremita">
<meta property="article:section" content="Vremenski povzetki">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}, Rečica ob Savinji">
<meta name="twitter:description" content="{short}">
<meta name="twitter:image" content="{SITE}/og/{slug}.jpg">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "{title}, Rečica ob Savinji",
  "description": "{desc}",
  "image": {{ "@type": "ImageObject", "url": "{SITE}/og/{slug}.jpg", "width": 1200, "height": 630 }},
  "wordCount": "__WC__",
  "datePublished": "{TODAY}",
  "dateModified": "{TODAY}",
  "inLanguage": "sl",
  "author": {{ "@type": "Person", "name": "Filip Eremita" }},
  "publisher": {{ "@type": "Organization", "name": "Meteorec", "logo": {{ "@type": "ImageObject", "url": "{SITE}/icon-512.png" }} }},
  "mainEntityOfPage": {{ "@type": "WebPage", "@id": "{url}" }},
  "about": {{ "@type": "Place", "name": "Rečica ob Savinji", "geo": {{ "@type": "GeoCoordinates", "latitude": 46.325779, "longitude": 14.921137, "elevation": 366 }} }}
}}
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{ "@type": "ListItem", "position": 1, "name": "Meteorec", "item": "{SITE}/" }},
    {{ "@type": "ListItem", "position": 2, "name": "Blog", "item": "{SITE}/blog/" }},
    {{ "@type": "ListItem", "position": 3, "name": "{title}" }}
  ]
}}
</script>
<link rel="stylesheet" href="/fonts/fonts.css">
<link rel="stylesheet" href="blog.css">
</head>
<body>
<div id="bg" aria-hidden="true"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="blob b4"></div><div class="blob b5"></div></div>
<div class="wrap">
  <header class="site-head">
    <a class="brand" href="/">
      <img class="brand-logo" src="/logo.svg" alt="" width="42" height="42">
      <span class="brand-name">Meteo<em>rec</em></span>
    </a>
    <nav class="site-nav"><a href="/">Vreme v živo</a><a href="/blog/">Blog</a></nav>
  </header>
  <nav class="crumbs" aria-label="Drobtine">
    <a href="/">Meteorec</a> › <a href="/blog/">Blog</a> › {title}
  </nav>
  <article>
    <div class="stn-badge"><span></span> IREICA1 · Rečica ob Savinji</div>
    <h1>{title} v Rečici ob Savinji</h1>
    <p class="post-meta">{fmtdate(TODAY)} · Filip Eremita · postaja IREICA1 · ~3 min branja</p>
    <p class="lead">{lead}</p>
    {partial}
    <h2>Ključne številke</h2>
    <table class="stats">
{rows_html}
    </table>
    <p style="color:var(--muted);font-size:.9rem">Vrednosti temperature so dnevna povprečja, ne najvišje oz. najnižje vrednosti v dnevu. Padavine in sunki vetra so dejanske dnevne vrednosti.</p>
    <p style="color:var(--muted);font-size:.9rem">Vir podatkov: osebna meteorološka postaja IREICA1, Rečica ob Savinji (Savinjska dolina, 366 m n. m.). Trenutne meritve v živo: <a href="/" style="color:var(--blue)">meteorec.si</a>.</p>
    <a class="back-link" href="/blog/">← Nazaj na blog</a>
  </article>
  <footer class="site-foot">
    <span>© {y} Meteorec · Rečica ob Savinji</span>
    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a></span>
  </footer>
</div>
</body>
</html>
'''
    return slug, url, title, short, html

def main():
    if len(sys.argv) < 2:
        sys.exit("Uporaba: python3 tools/generate_monthly_post.py YYYY-MM [--wire]")
    ym = sys.argv[1]
    wire = "--wire" in sys.argv
    s = compute(ym)
    slug, url, title, short, html = build_html(s)
    plain = re.sub(r'<[^>]+>', ' ', html)
    wc = len([w for w in plain.split() if re.search(r'[a-zA-ZšđčćžŠĐČĆŽ]', w)])
    html = html.replace('"wordCount": "__WC__",', f'"wordCount": {wc},')
    out = os.path.join(ROOT, "blog", f"{slug}.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"✓ zapisano: blog/{slug}.html  ({s['n']}/{s['dim']} dni)")

    entry = {"title": title, "slug": slug, "url": f"/blog/{slug}.html",
             "date": TODAY, "summary": short,
             "tags": ["povzetek", MES_NOM[s["mon"]], str(s["year"])]}
    if wire:
        wire_all(entry, url, stats=s)
        print("✓ posodobljeno: blog.json, blog/index.html, sitemap.xml")
    else:
        print("\n— Za blog.json dodaj:\n" + json.dumps(entry, ensure_ascii=False, indent=2))
        print(f"\n— Za sitemap.xml dodaj <url><loc>{url}</loc>…")
        print("\n(ali poženi z --wire za samodejno vpisovanje)")

def wire_all(entry, url, stats=None):
    # blog.json — vstavi na vrh (najnovejše prvo), brez podvajanja
    bj = os.path.join(ROOT, "blog.json")
    posts = json.load(open(bj, encoding="utf-8"))
    posts = [p for p in posts if p.get("slug") != entry["slug"]]
    posts.insert(0, entry)
    json.dump(posts, open(bj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(bj, "a", encoding="utf-8").write("\n")
    # sitemap.xml — pregeneriraj iz fiksnih vnosov + objav
    sm = [
        (f"{SITE}/",               "hourly",  "1.0", TODAY),
        (f"{SITE}/blog/",          "weekly",  "0.8", TODAY),
        (f"{SITE}/o-postaji.html", "monthly", "0.6", "2026-06-19"),
    ]
    sm += [(f"{SITE}{p['url']}", "monthly", "0.7", p["date"]) for p in posts]
    body = "\n".join(
        f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lm}</lastmod>\n"
        f"    <changefreq>{cf}</changefreq>\n    <priority>{pr}</priority>\n  </url>"
        for loc, cf, pr, lm in sm)
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "\n</urlset>\n")
    # blog/index.html — pregeneriraj seznam objav med markerjema
    idx = os.path.join(ROOT, "blog", "index.html")
    h = open(idx, encoding="utf-8").read()
    items = "\n".join(
        f'    <li>\n      <a class="post-card" href="{p["slug"]}.html">\n'
        f'        <div class="date">{fmtdate(p["date"])}</div>\n'
        f'        <h2>{p["title"]}</h2>\n        <p>{p["summary"]}</p>\n      </a>\n    </li>'
        for p in posts)
    h = re.sub(r'(<ul class="post-list">).*?(</ul>)',
               r'\1\n' + items + r'\n  \2', h, flags=re.S)
    open(idx, "w", encoding="utf-8").write(h)
    # Try to generate per-article OG image (requires Pillow)
    if stats:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from generate_og_images import make_og
            make_og({
                'slug': entry['slug'],
                'title': f'Vremenski povzetek\n{MES_NOM[stats["mon"]]} {stats["year"]}',
                'subtitle': 'Rečica ob Savinji · IREICA1',
                'section': 'Vremenski povzetki',
                'accent': (14, 165, 233),
            })
            print(f"✓ OG slika: og/{entry['slug']}.jpg")
        except Exception as e:
            print(f"⚠ OG slika preskočena: {e}")

def fmtdate(iso):
    y, m, d = iso.split("-")
    return f"{int(d)}. {MES_GEN[int(m)]} {y}"

if __name__ == "__main__":
    main()
