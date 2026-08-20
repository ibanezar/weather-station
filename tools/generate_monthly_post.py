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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asset_version import css_links
# Tema strani se pregenerirajo ob vsaki objavi, zato verzija pride v HTML sama.
CSS_LINKS = css_links('fonts/fonts.css', 'blog/blog.css')
SITE = "https://meteorec.si"
# datum objave: privzeto današnji (UTC), z možnostjo prepisa prek POST_DATE
TODAY = os.environ.get("POST_DATE") or datetime.date.today().isoformat()

# Zgornja meja za <title>: nad ~60 znaki ga Google odreže, Semrush pa javi
# opozorilo "too much text within the title tags".
TITLE_MAX = 60

def seo_title(title, suffix=" | Meteorec"):
    """Zgradi vsebino <title> tako, da ostane znotraj TITLE_MAX znakov.

    Naslov članka (h1, og:title, JSON-LD) pusti pri miru -- krajša se samo
    title tag. Vzame najbogatejšo različico naslova, ki se še prilega, in ji
    doda pripono le, če po tem ostane znotraj meje. Vsebina naslova ima torej
    prednost pred blagovno pripono.
    """
    title = " ".join(title.split())

    # Naslovi so pogosto "Glavni del: podnaslov" ali "Glavni del — podnaslov",
    # pogosto s pojasnilom v oklepaju na koncu. Oboje je smiselno odrezati.
    variants = [title]
    no_paren = re.sub(r"\s*\([^()]*\)\s*$", "", title)
    if no_paren and no_paren != title:
        variants.append(no_paren)
    # Repne dele odrezujemo POSTOPOMA: "A — B — C" da tudi "A — B", ne samo "A".
    # Prej je bil vzet le split(sep)[0], zato je funkcija pri naslovih z dvema
    # ločiloma skočila z vsega naravnost na prvi odsek in preskočila vmesno
    # različico, ki se je prilegala in nosila ključne besede — npr.
    # "Danes po gozdovih — gobarski indeks po območjih — Gobarska napoved" (66)
    # je dalo "Danes po gozdovih" (17) namesto srednje (46), po kateri ljudje
    # sploh iščejo.
    for base in list(variants):
        for sep in (": ", " — ", " – "):
            parts = base.split(sep)
            for k in range(len(parts) - 1, 0, -1):
                variants.append(sep.join(parts[:k]))

    # Od najbogatejše (najdaljše) proti najkrajši -- prva, ki se prilega.
    for v in sorted(set(variants), key=len, reverse=True):
        if len(v) <= TITLE_MAX:
            return v + suffix if len(v + suffix) <= TITLE_MAX else v

    # Nobena naravna različica ne gre skozi -- odreži na besedni meji.
    # Če bi odrez pustil odprt oklepaj, ga odrežemo vred.
    cut = title[:TITLE_MAX - 1]
    if " " in cut:
        cut = cut[:cut.rindex(" ")]
    if cut.count("(") > cut.count(")"):
        cut = cut[:cut.rindex("(")]
    return cut.rstrip(" ,;:-—–") + "…"

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
    # prave dnevne skrajnosti (po popravku min/max v history.json)
    tmax = max(m.items(), key=lambda kv: kv[1]["tempHigh"])
    tmin = min(m.items(), key=lambda kv: kv[1]["tempLow"])
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
                tavg=tavg, tmax=tmax, tmin=tmin, prec=prec, wettest=wettest,
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
            + f' in <strong>{num(s["prec"])} mm</strong> padavin. '
            + f'Najvišja izmerjena temperatura je bila <strong>{num(s["tmax"][1]["tempHigh"])} °C</strong> '
            + f'({dayfmt(s["tmax"][0],mon)}), najnižja <strong>{num(s["tmin"][1]["tempLow"])} °C</strong> '
            + f'({dayfmt(s["tmin"][0],mon)}).')
    rows = [
        ("Povprečna dnevna temperatura", f"{num(s['tavg'])} °C"),
    ]
    if anom is not None:
        rows.append(("Odstopanje od dolgoletnega povprečja", f"{'+' if anom>=0 else '−'}{num(abs(anom))} °C"))
    rows += [
        ("Najvišja temperatura", f"{dayfmt(s['tmax'][0],mon)} · {num(s['tmax'][1]['tempHigh'])} °C"),
        ("Najnižja temperatura", f"{dayfmt(s['tmin'][0],mon)} · {num(s['tmin'][1]['tempLow'])} °C"),
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
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-LE8PJ1HR8B');
</script>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{seo_title(title, " | Meteorec, Rečica ob Savinji")}</title>
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="sl" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<meta name="description" content="{desc}">
<meta name="keywords" content="vreme {nom} {y}, Rečica ob Savinji, vremenski povzetek, IREICA1, Savinjska dolina, padavine, temperatura">
<meta name="robots" content="index, follow, max-image-preview:large">
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
  "about": {{ "@type": "Place", "name": "Rečica ob Savinji", "sameAs": ["https://www.wikidata.org/wiki/Q969326", "https://en.wikipedia.org/wiki/Re%C4%8Dica_ob_Savinji"], "geo": {{ "@type": "GeoCoordinates", "latitude": 46.325779, "longitude": 14.921137, "elevation": 366 }} }}
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
    <p style="color:var(--muted);font-size:.9rem">Povprečna temperatura je povprečje dnevnih vrednosti; najvišja in najnižja sta dejanski izmerjeni skrajnosti v mesecu.</p>
    <p style="color:var(--muted);font-size:.9rem">Vir podatkov: osebna meteorološka postaja IREICA1, Rečica ob Savinji (Savinjska dolina, 366 m n. m.). Trenutne meritve v živo: <a href="/" style="color:var(--blue)">meteorec.si</a>.</p>
    <a class="back-link" href="/blog/">← Nazaj na blog</a>
  </article>
  <footer class="site-foot">
    <span>© {y} Meteorec · Rečica ob Savinji</span>
    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a> · <a class="social-link" href="https://www.facebook.com/meteorec.si" target="_blank" rel="noopener" aria-label="Meteorec na Facebooku"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" width="14" height="14"><path d="M22 12a10 10 0 10-11.56 9.88v-6.99H7.9V12h2.54V9.8c0-2.5 1.49-3.89 3.78-3.89 1.09 0 2.24.2 2.24.2v2.46H15.2c-1.24 0-1.63.77-1.63 1.56V12h2.78l-.44 2.89h-2.34v6.99A10 10 0 0022 12z"/></svg></a> · <a class="social-link" href="https://www.instagram.com/meteorec.si" target="_blank" rel="noopener" aria-label="Meteorec na Instagramu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true" width="14" height="14"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg></a></span>
  </footer>
</div>
<script src="likes.js" defer></script>
<script src="views.js" defer></script>
<script src="/blog/share-bar.js" defer></script>
</body>
</html>
'''
    return slug, url, title, short, html

def main():
    if len(sys.argv) < 2:
        sys.exit("Uporaba: python3 tools/generate_monthly_post.py YYYY-MM [--wire]\n"
                  "       python3 tools/generate_monthly_post.py --touch <slug> [--wire]")
    if "--touch" in sys.argv:
        i = sys.argv.index("--touch")
        if i + 1 >= len(sys.argv):
            sys.exit("Uporaba: python3 tools/generate_monthly_post.py --touch <slug> [--wire]")
        touch_existing(sys.argv[i + 1], wire="--wire" in sys.argv)
        return
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

def touch_existing(slug, wire=True):
    """Označi obstoječ blog vnos kot posodobljen danes (polje 'updated'),
    za primere ko ročno urediš vsebino starejše objave (blog/<slug>.html)
    brez da bi spreminjal njen izvirni datum objave."""
    bj = os.path.join(ROOT, "blog.json")
    posts = json.load(open(bj, encoding="utf-8"))
    entry = next((p for p in posts if p.get("slug") == slug), None)
    if entry is None:
        sys.exit(f"Ni najdenega vnosa z slugom '{slug}' v blog.json.")
    if entry["date"] == TODAY:
        print(f"⚠ '{slug}' je bil objavljen danes ({TODAY}) — polje 'updated' ni potrebno.")
        return
    entry["updated"] = TODAY
    # premakni na vrh pred (stabilnim) razvrščanjem, da zmaga tudi ob
    # izenačenju datuma z drugo objavo istega dne (npr. mesečni povzetek)
    posts.remove(entry)
    posts.insert(0, entry)
    posts.sort(key=lambda p: p.get("updated") or p["date"], reverse=True)
    if not wire:
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        print("\n(poženi z --wire za samodejno vpisovanje v blog.json, blog/index.html in sitemap.xml)")
        return
    json.dump(posts, open(bj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(bj, "a", encoding="utf-8").write("\n")
    rewrite_sitemap_and_index(posts)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from compute_related_posts import compute_and_write
        compute_and_write(posts)
    except Exception as e:
        print(f"⚠ blog/related.json preskočen: {e}")
    print(f"✓ '{slug}' označen kot posodobljen ({TODAY}); blog.json, blog/index.html in sitemap.xml osveženi.")

def core_sitemap_entries():
    """Fiksni del sitemap.xml, izpeljan iz `CORE` v tools/seo_audit.py.

    Vnos je peterka, kot jo pričakuje rewrite_sitemap_and_index:
    (loc, changefreq, priority, lastmod, image).

    Izpuščene so strani, ki jih pokriva sitemap-seo.xml ali sitemap-weather.xml
    (klima, padavine, vreme/…) — te imajo svoj generator in tam tudi svoj
    lastmod; podvajanje po sitemapih ne prinese ničesar. Izpuščene so tudi
    strani, ki jih ni na disku, da v sitemapu ne nastane mrtva povezava.

    lastmod: strani, ki se osvežujejo vsak dan (hourly/daily), in tisti dve, ki
    ju ta objava res spremeni (domača stran in /blog/), dobijo današnji datum.
    Ostale ohranijo datum iz obstoječega sitemapa — sicer bi vsaka objava članka
    trdila, da so se spremenile tudi mirujoče strani (npr. o-postaji.html).
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import seo_audit

    covered = set()
    for name in ("sitemap-seo.xml", "sitemap-weather.xml"):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            covered |= seo_audit.sitemap_locs(open(p, encoding="utf-8").read())

    prev = {}
    main = os.path.join(ROOT, "sitemap.xml")
    if os.path.exists(main):
        for block in re.findall(r"<url>(.*?)</url>", open(main, encoding="utf-8").read(), re.S):
            loc = re.search(r"<loc>(.*?)</loc>", block)
            lm = re.search(r"<lastmod>(.*?)</lastmod>", block)
            if loc and lm:
                prev[loc.group(1)] = lm.group(1)

    entries = []
    for page, (cf, prio) in seo_audit.CORE.items():
        url = f"{SITE}/{page}"
        if url in covered or not os.path.exists(seo_audit.local_path(page)):
            continue
        fresh = cf in ("hourly", "daily") or page in ("", "blog/")
        lastmod = TODAY if fresh else prev.get(url, TODAY)
        img = f"{SITE}/og-image.jpg" if page == "" else None
        entries.append((url, cf, prio, lastmod, img))
    return entries


def rewrite_sitemap_and_index(posts):
    # sitemap.xml — pregeneriraj iz fiksnih vnosov + objav (lastmod = zadnja sprememba)
    # image: samo za strani z resnično lastno (ne generično) sliko -- domača
    # stran in posamezni članki bloga, vsak s svojim og/<slug>.jpg.
    #
    # Fiksni del NI svoj seznam: izpelje se iz `CORE` v tools/seo_audit.py, ki je
    # edina tabela ključnih strani. Prej sta bila seznama dva in sta se razšla —
    # ko je gobarska napoved dobila podstrani (baza-vrst, dvojnice, danes …), so
    # bile dodane samo v CORE, tukaj pa ne. Ker ta funkcija sitemap.xml prepiše na
    # novo, jih je vsaka objava članka spet pobrisala, `seo_audit --fix` (nedeljski
    # cron) pa jih je vrnil — 13 strani je bilo tako večino dni v nobenem sitemapu.
    # Nova ključna stran gre torej samo v CORE in se pojavi tudi tu.
    sm = core_sitemap_entries() + [
        (f"{SITE}/blog/poplave-2023.html", "yearly",  "0.6", "2026-07-08", f"{SITE}/og/poplave-2023.jpg"),
    ]
    sm += [(f"{SITE}{p['url']}", "monthly", "0.7", p.get("updated") or p["date"],
            f"{SITE}/og/{p['slug']}.jpg") for p in posts]
    # kategorijske (tag) strani
    tag_slugs = build_tag_pages(posts)
    sm += [(f"{SITE}/blog/tema/{t}/", "weekly", "0.5", TODAY, None) for t in tag_slugs]
    body = "\n".join(
        f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lm}</lastmod>\n"
        f"    <changefreq>{cf}</changefreq>\n    <priority>{pr}</priority>"
        + (f"\n    <image:image><image:loc>{img}</image:loc></image:image>" if img else "")
        + "\n  </url>"
        for loc, cf, pr, lm, img in sm)
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
        + body + "\n</urlset>\n")
    # blog/index.html — pregeneriraj seznam objav med markerjema
    idx = os.path.join(ROOT, "blog", "index.html")
    h = open(idx, encoding="utf-8").read()
    def li(p):
        date_html = fmtdate(p["date"])
        if p.get("updated"):
            date_html += f' <span class="post-updated" title="Posodobljeno {fmtdate(p["updated"])}">☁️</span>'
        alt = p["title"].replace('"', "&quot;")
        return (f'    <li>\n      <a class="post-card" href="{p["slug"]}.html">\n'
                f'        <img class="post-thumb" src="/og/{p["slug"]}.jpg" alt="{alt}" width="260" height="260" loading="lazy">\n'
                f'        <div class="post-card-body">\n'
                f'          <div class="date">{date_html}</div>\n'
                f'          <h2>{p["title"]}</h2>\n          <p>{p["summary"]}</p>\n'
                f'        </div>\n      </a>\n    </li>')
    items = "\n".join(li(p) for p in posts)
    h = re.sub(r'(<ul class="post-list">).*?(</ul>)',
               r'\1\n' + items + r'\n  \2', h, flags=re.S)
    open(idx, "w", encoding="utf-8").write(h)
    # RSS feed — ostane v sinhronu z blog.json
    build_rss(posts)


def tagslug(t):
    t = str(t).lower()
    for a, b in (("č", "c"), ("š", "s"), ("ž", "z"), ("ć", "c"), ("đ", "d")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


# ── Statične notranje povezave v člankih ────────────────────────────────
# "Teme:" in "Sorodni članki" je prej izrisoval samo blog/article-enhance.js
# iz blog.json + related.json. Pajki brez JS (tudi Semrushev audit) teh
# povezav niso videli, zato je imela večina člankov eno samo dohodno
# notranjo povezavo -- iz blog/index.html. Zato jih ob objavi vpišemo
# naravnost v HTML; JS blok preskoči, če je statični že tam.
REL_START = "<!-- sorodni:start — samodejno, wire_all(); ne urejaj ročno -->"
REL_END = "<!-- sorodni:end -->"
TOPICS_START = "<!-- teme:start — samodejno, wire_all(); ne urejaj ročno -->"
TOPICS_END = "<!-- teme:end -->"
# Blok "Vreme in podatki" -- glej SEO audit 2026-08, točka 11/13/15: članki so
# doslej linkali predvsem na naslovno stran in med seboj (sorodni:*), premalo
# pa na Meteorecove lastne podatkovne hub strani, ki so glavna SEO prednost
# strani. Seznam je namenoma statičen in enak za vse članke (brez
# teme-detekcije) -- vse povezave so univerzalno relevantne za vsak članek o
# vremenu v dolini, dodatna klasifikacija ne bi prinesla dovolj vrednosti.
DATA_START = "<!-- podatki:start — samodejno, wire_all(); ne urejaj ročno -->"
DATA_END = "<!-- podatki:end -->"
DATA_LINKS = [
    ("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji"),
    ("/vreme/", "Vremenski arhiv"),
    ("/klima/", "Klima in podnebje"),
    ("/padavine/", "Padavine"),
    ("/rekord/", "Rekordi"),
    ("/vreme-zgornja-savinjska-dolina/", "Vreme Zgornja Savinjska dolina"),
    ("/tocnost-napovedi/", "Točnost napovedi"),
]


def esc_attr(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _post_url(p):
    return p.get("url") or ("/blog/" + p["slug"] + ".html")


def render_topics_html(post, freq):
    """Povezave na tematske strani -- samo tagi, ki stran dejansko imajo (>=2 objavi)."""
    linkable = [t for t in post.get("tags", []) if freq.get(str(t).lower(), 0) >= 2]
    if not linkable:
        return ""
    links = "".join(
        f'<a class="pt-tag" href="/blog/tema/{tagslug(t)}/">{esc_attr(str(t).lower())}</a>'
        for t in linkable)
    return (f'    {TOPICS_START}\n'
            f'    <div class="post-topics"><span class="pt-label">Teme:</span> {links}</div>\n'
            f'    {TOPICS_END}\n')


def render_related_html(related_posts):
    """Sekcija 'Sorodni članki'. Mora biti neposredni otrok .wrap --
    blog.css (.wrap > .related-posts) jo postavi v mrežo ob stranski stolpec."""
    if not related_posts:
        return ""
    cards = []
    for p in related_posts:
        summary = (p.get("summary") or "").strip()
        if len(summary) > 120:
            summary = summary[:120] + "…"
        sum_html = f'<span class="related-sum">{esc_attr(summary)}</span>' if summary else ""
        cards.append(
            f'<a class="related-card" href="{esc_attr(_post_url(p))}">'
            f'<span class="related-date">{fmtdate(p["date"])}</span>'
            f'<span class="related-h">{esc_attr(p["title"])}</span>'
            f'{sum_html}</a>')
    return (f'  {REL_START}\n'
            f'  <section class="related-posts">\n'
            f'    <h2 class="related-title">Sorodni članki</h2>\n'
            f'    <div class="related-grid">{"".join(cards)}</div>\n'
            f'  </section>\n'
            f'  {REL_END}\n')


def render_datalinks_html():
    """Sekcija 'Vreme in podatki' -- statične povezave na hub strani. Enaka
    razredna oblika kot 'Sorodni članki' (.related-posts/.related-grid/
    .related-card), samo brez datuma/povzetka na kartici."""
    cards = "".join(
        f'<a class="related-card" href="{href}"><span class="related-h">{label}</span></a>'
        for href, label in DATA_LINKS)
    return (f'  {DATA_START}\n'
            f'  <section class="related-posts">\n'
            f'    <h2 class="related-title">Vreme in podatki</h2>\n'
            f'    <div class="related-grid">{cards}</div>\n'
            f'  </section>\n'
            f'  {DATA_END}\n')


def _replace_block(html, start, end, new_block):
    """Zamenja obstoječi označeni blok; vrne (html, ali_je_bil_ze_tam)."""
    i = html.find(start)
    if i == -1:
        return html, False
    j = html.find(end, i)
    if j == -1:
        return html, False
    j += len(end)
    # Razširi nazaj na začetek vrstice: zamik nosi že sam blok, sicer bi se
    # ob vsakem zagonu naložil še obstoječi in bi se vrstica zamikala v desno.
    line_start = html.rfind("\n", 0, i) + 1
    if not html[line_start:i].strip():
        i = line_start
    # poberi še morebitni prelom vrstice za zaključno oznako
    if html[j:j + 1] == "\n":
        j += 1
    return html[:i] + new_block + html[j:], True


def inject_related_links(posts, quiet=False):
    """Vpiše 'Teme:' in 'Sorodni članki' v HTML vseh objav iz blog.json.

    Idempotentno: bloka sta omejena z oznakama in se ob vsakem klicu
    prepišeta, tako da se sorodni članki osvežijo, ko izide nova objava.
    """
    try:
        with open(os.path.join(ROOT, "blog", "related.json"), encoding="utf-8") as f:
            related_map = json.load(f)
    except Exception as e:
        if not quiet:
            print(f"⚠ statične notranje povezave preskočene (related.json): {e}")
        return 0

    by_slug = {p["slug"].lower(): p for p in posts}
    freq = {}
    for p in posts:
        for t in p.get("tags", []):
            t = str(t).lower()
            freq[t] = freq.get(t, 0) + 1

    datalinks_block = render_datalinks_html()

    changed = 0
    for p in posts:
        slug = p["slug"]
        path = os.path.join(ROOT, "blog", f"{slug}.html")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            html = f.read()
        orig = html

        rel = [by_slug[s.lower()] for s in related_map.get(slug, [])
               if s.lower() in by_slug and s.lower() != slug.lower()]
        topics_block = render_topics_html(p, freq)
        related_block = render_related_html(rel)

        html, had = _replace_block(html, TOPICS_START, TOPICS_END, topics_block)
        if not had and topics_block:
            # pred povezavo "Nazaj na blog", tako kot jih je vstavljal JS
            m = re.search(r'^[ \t]*<a class="back-link"', html, re.M)
            if m:
                html = html[:m.start()] + topics_block + html[m.start():]

        html, had = _replace_block(html, REL_START, REL_END, related_block)
        if not had and related_block:
            # za </article>, kot neposredni otrok .wrap (zahteva blog.css)
            m = re.search(r"^[ \t]*</article>[ \t]*\n", html, re.M)
            if m:
                html = html[:m.end()] + "\n" + related_block + html[m.end():]

        html, had = _replace_block(html, DATA_START, DATA_END, datalinks_block)
        if not had:
            # za sorodnimi članki, če obstajajo, sicer neposredno za </article>
            m = re.search(re.escape(REL_END) + r"[ \t]*\n", html)
            if not m:
                m = re.search(r"^[ \t]*</article>[ \t]*\n", html, re.M)
            if m:
                html = html[:m.end()] + "\n" + datalinks_block + html[m.end():]

        if html != orig:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            changed += 1

    if not quiet:
        print(f"✓ statične notranje povezave osvežene v {changed} člankih")
    return changed


def build_tag_pages(posts):
    """Ustvari pristajalne strani /blog/tema/<tag>/ za tage z ≥2 objavama.
    Vrne seznam (slug) za sitemap."""
    # Zberi objave po slugu, ne po surovem tagu. Tagi so v blog.json pisani
    # neenotno — „vročina“ in „vrocina“, „suša“ in „susa“, „vodna bilanca“ in
    # „vodna-bilanca“ — vse pa se preslika v isti slug. Ob združevanju po surovem
    # tagu je zato nastala ista stran dvakrat: druga je prvo prepisala, tako da je
    # /blog/tema/vrocina/ naštela 16 od 27 objav, /blog/tema/susa/ pa 9 od 12,
    # v sitemapu pa sta bila oba sluga podvojena. Različice, ki same niso imele
    # dveh objav, so tiho ostale brez strani.
    by_slug = {}
    for p in posts:
        for t in p.get("tags", []):
            t = str(t).lower()
            slug = tagslug(t)
            if not slug:
                continue
            g = by_slug.setdefault(slug, {"posts": {}, "variants": {}})
            g["posts"][p["slug"]] = p
            g["variants"][t] = g["variants"].get(t, 0) + 1
    made = []
    for slug, g in by_slug.items():
        plist = list(g["posts"].values())
        if len(plist) < 2:
            continue
        # Naslov strani: najbolj pravilno zapisana različica — najprej tista s
        # šumniki (»vročina« pred »vrocina«), nato najpogostejša.
        tag = max(g["variants"].items(),
                  key=lambda kv: (any(ord(c) > 127 for c in kv[0]), kv[1]))[0]
        plist = sorted(plist, key=lambda p: p.get("updated") or p["date"], reverse=True)
        cards = "\n".join(
            f'    <li>\n      <a class="post-card" href="/blog/{p["slug"]}.html">\n'
            f'        <img class="post-thumb" src="/og/{p["slug"]}.jpg" alt="{p["title"].replace(chr(34), "&quot;")}" width="260" height="260" loading="lazy">\n'
            f'        <div class="post-card-body">\n'
            f'          <div class="date">{fmtdate(p["date"])}</div>\n'
            f'          <h2>{p["title"]}</h2>\n          <p>{p["summary"]}</p>\n'
            f'        </div>\n      </a>\n    </li>'
            for p in plist)
        canon = f"{SITE}/blog/tema/{slug}/"
        desc = f"Vsi članki bloga Meteorec na temo „{tag}“ — vremenske analize, povzetki in rekordi z meritvami postaje IREICA1 v Rečici ob Savinji."
        html = f'''<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{seo_title(f"Tema: {tag} — članki", " | Meteorec, Rečica ob Savinji")}</title>
<link rel="canonical" href="{canon}">
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:url" content="{canon}">
<meta property="og:title" content="Tema: {tag} — blog Meteorec">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{SITE}/og/blog.jpg">
<link rel="alternate" type="application/rss+xml" title="Meteorec — blog" href="/blog/rss.xml">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"CollectionPage","name":"Tema: {tag}","url":"{canon}","isPartOf":{{"@type":"Blog","name":"Blog Meteorec","url":"{SITE}/blog/"}}}}
</script>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
{{"@type":"ListItem","position":1,"name":"Meteorec","item":"{SITE}/"}},
{{"@type":"ListItem","position":2,"name":"Blog","item":"{SITE}/blog/"}},
{{"@type":"ListItem","position":3,"name":"{tag}"}}]}}
</script>
{CSS_LINKS}
</head>
<body>
<div id="bg" aria-hidden="true"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="blob b4"></div><div class="blob b5"></div></div>
<div class="wrap">
  <header class="site-head">
    <a class="brand" href="/">
      <img class="brand-logo" src="/logo.svg" alt="" width="42" height="42">
      <span class="brand-name">Meteo<em>rec</em></span>
    </a>
    <nav class="site-nav">
      <a href="/">Vreme v živo</a>
      <a href="/blog/">Blog</a>
      <a href="/o-postaji.html">O postaji</a>
    </nav>
  </header>
  <nav class="crumbs" aria-label="Drobtine"><a href="/">Meteorec</a> › <a href="/blog/">Blog</a> › Tema: {tag}</nav>
  <h1 class="page-title">Tema: {tag}</h1>
  <p class="page-intro">{len(plist)} člankov na temo „{tag}“. <a href="/blog/" style="color:var(--blue)">← Vsi članki</a></p>
  <ul class="post-list">
{cards}
  </ul>
  <footer class="site-foot">
    <span>© 2026 Meteorec · Rečica ob Savinji</span>
    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a> · <a class="social-link" href="https://www.facebook.com/meteorec.si" target="_blank" rel="noopener" aria-label="Meteorec na Facebooku"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" width="14" height="14"><path d="M22 12a10 10 0 10-11.56 9.88v-6.99H7.9V12h2.54V9.8c0-2.5 1.49-3.89 3.78-3.89 1.09 0 2.24.2 2.24.2v2.46H15.2c-1.24 0-1.63.77-1.63 1.56V12h2.78l-.44 2.89h-2.34v6.99A10 10 0 0022 12z"/></svg></a> · <a class="social-link" href="https://www.instagram.com/meteorec.si" target="_blank" rel="noopener" aria-label="Meteorec na Instagramu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true" width="14" height="14"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg></a></span>
  </footer>
</div>
</body>
</html>
'''
        d = os.path.join(ROOT, "blog", "tema", slug)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(html)
        made.append(slug)

    # Tema strani, ki so padle pod prag dveh objav (npr. ko se objave umaknejo),
    # se ne pregenerirajo — datoteka pa ostane in našteva stare, morda umaknjene
    # članke. Pretvorimo jih v preusmeritev na /blog/: brisanje bi indeksiran
    # URL sesulo v 404, tiho puščanje pa bi obiskovalcu kazalo zastarel seznam.
    tema_dir = os.path.join(ROOT, "blog", "tema")
    if os.path.isdir(tema_dir):
        live = set(made)
        for name in sorted(os.listdir(tema_dir)):
            d = os.path.join(tema_dir, name)
            if not os.path.isdir(d) or name in live:
                continue
            target = f"{SITE}/blog/"
            open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(
                f"""<!doctype html>
<html lang="sl">
<head>
<meta charset="utf-8">
<title>Tema nima več svoje strani — Meteorec</title>
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="{target}">
<meta http-equiv="refresh" content="0; url={target}">
<script>location.replace("{target}");</script>
<style>body{{font:16px/1.6 system-ui,sans-serif;margin:3rem auto;max-width:40rem;padding:0 1rem}}</style>
</head>
<body>
<p>Ta tema nima več dovolj objav za svojo stran.</p>
<p>Preusmerjam na <a href="{target}">blog Meteorec</a> …</p>
</body>
</html>
""")
    return sorted(made)


def build_rss(posts):
    """Zapiše blog/rss.xml (RSS 2.0) iz seznama objav (blog.json)."""
    def rfc822(iso):
        try:
            d = datetime.datetime.strptime(iso, "%Y-%m-%d")
            return d.strftime("%a, %d %b %Y 08:00:00 +0000")
        except Exception:
            return ""
    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    items = []
    for p in posts:
        url = p.get("url") or ("/blog/" + p["slug"] + ".html")
        link = SITE + (url if url.startswith("/") else "/" + url)
        cats = "".join(f"      <category>{esc(t)}</category>\n" for t in p.get("tags", []))
        items.append(
            "    <item>\n"
            f"      <title>{esc(p['title'])}</title>\n"
            f"      <link>{link}</link>\n"
            f'      <guid isPermaLink="true">{link}</guid>\n'
            f"      <pubDate>{rfc822(p.get('updated') or p['date'])}</pubDate>\n"
            f"      <description>{esc(p.get('summary', ''))}</description>\n"
            f"{cats}"
            "    </item>")
    now = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        '  <channel>\n'
        '    <title>Meteorec — blog</title>\n'
        f'    <link>{SITE}/blog/</link>\n'
        '    <description>Vremenski povzetki, rekordi in analize iz Rečice ob Savinji (postaja IREICA1).</description>\n'
        '    <language>sl</language>\n'
        f'    <lastBuildDate>{now}</lastBuildDate>\n'
        f'    <atom:link href="{SITE}/blog/rss.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(items) + "\n"
        '  </channel>\n</rss>\n')
    open(os.path.join(ROOT, "blog", "rss.xml"), "w", encoding="utf-8").write(xml)

def wire_all(entry, url, stats=None):
    # blog.json — vstavi/posodobi (najnovejše prvo po datumu objave/posodobitve)
    bj = os.path.join(ROOT, "blog.json")
    posts = json.load(open(bj, encoding="utf-8"))
    existing = next((p for p in posts if p.get("slug") == entry["slug"]), None)
    if existing is not None:
        # ista objava se pregenerira (npr. dopolnjen mesec) — ohrani izvirni
        # datum objave in namesto tega označi kot posodobljeno
        entry["date"] = existing["date"]
        if entry["date"] != TODAY:
            entry["updated"] = TODAY
    posts = [p for p in posts if p.get("slug") != entry["slug"]]
    posts.insert(0, entry)
    posts.sort(key=lambda p: p.get("updated") or p["date"], reverse=True)
    json.dump(posts, open(bj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(bj, "a", encoding="utf-8").write("\n")
    rewrite_sitemap_and_index(posts)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from compute_related_posts import compute_and_write
        compute_and_write(posts)
        print("✓ blog/related.json posodobljen")
    except Exception as e:
        print(f"⚠ blog/related.json preskočen: {e}")
    # Statične notranje povezave (Teme + Sorodni članki) v HTML člankov, da so
    # vidne tudi pajkom brez JS. Mora teči po compute_and_write().
    try:
        inject_related_links(posts)
    except Exception as e:
        print(f"⚠ statične notranje povezave preskočene: {e}")
    # Kratka povezava meteorec.si/i/<koda> — Instagram povezav ne naredi
    # klikabilnih, zato mora biti dovolj kratka, da se jo da pretipkati.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import short_links
        code = short_links.ensure(entry["slug"], url)
        print(f"✓ kratka povezava: {short_links.short_url(code)}")
    except Exception as e:
        print(f"⚠ kratka povezava preskočena: {e}")
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
