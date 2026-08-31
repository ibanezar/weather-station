#!/usr/bin/env python3
"""
tools/generate_forecast_test_post.py — mesečna objava za /test-napovedi/ (Faza 4/5
v brief-u).

1. v mesecu povzame pretekli (dokončani) koledarski mesec: zmagovalca pri D+1,
največji posamični zgrešek (z datumom in številkami) in stalno metodološko
opombo iz test-napovedi.json (zero_crossing_lead_days, klimatologija).

Isti vzorec kot invasive_watch.py/generate_storm_watch_post.py -- predloga s
pravimi izračunanimi številkami (brez LLM osnutka, da se nič ne izmisli), nato
EN prehod lekture (generate_daily_post.call_lektor) za slovnico/slog/anglicizme
-- lektura je obvezna za vsak članek (CLAUDE.md).

Usage:
    python3 tools/generate_forecast_test_post.py [--wire] [--dry-run]

Potrebne env spremenljivke:
    ANTHROPIC_API_KEY   -- za lekturo (če manjka, lektura se preskoči)
"""
import datetime, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_monthly_post import ROOT, SITE, wire_all, fmtdate, seo_title, CSS_LINKS  # noqa: E402
from asset_version import asset_href  # noqa: E402
from generate_daily_post import app_bottomnav, hexrgb, call_lektor  # noqa: E402
import generate_seo_pages as seo  # noqa: E402
from compute_forecast_test_metrics import (  # noqa: E402
    load_observations, load_forecasts, err_stats, MODEL_LABELS, LEADS,
)

DATA_PATH = os.path.join(ROOT, "data", "test-napovedi.json")
TODAY_DATE = datetime.date.fromisoformat(os.environ.get("POST_DATE") or datetime.date.today().isoformat())
TODAY = TODAY_DATE.isoformat()

METHODOLOGY_NOTE = (
    "Metodologija: vsak dan primerjamo, kaj je pet virov (ECMWF IFS, ICON, GFS, ARPEGE, best_match prek "
    "Open-Meteo Previous Runs API) dan prej napovedalo za najvišjo temperaturo v Rečici ob Savinji, z dejansko "
    "meritvijo postaje IREICA1. Izhodišče je klimatologija — dolgoletno povprečje za ta koledarski dan — ne "
    "ugibanje na pamet. Rezultat velja izključno za Zgornjo Savinjsko dolino: modeli delujejo na mreži, ki ozke "
    "alpske doline ne razloči, ARSO pa zanjo nima krajevne napovedne točke. Polna metodologija in surovi podatki "
    f'(licenca CC BY 4.0): <a href="{SITE}/test-napovedi/" style="color:var(--blue)">{SITE}/test-napovedi/</a>.'
)


def prev_month_bounds(today):
    y, m = today.year, today.month - 1
    if m == 0:
        y, m = y - 1, 12
    d1 = datetime.date(y, m, 1)
    d2 = (datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)) if m < 12 else datetime.date(y, 12, 31)
    return y, m, d1.isoformat(), d2.isoformat()


def month_stats(obs, fc_by_key, d1, d2):
    """D+1 MAE po modelu za en mesec + največji posamični zgrešek (Tmax) v njem."""
    per_model = {}
    biggest = None  # (abs_err, model, date, predicted, actual)
    for model in MODEL_LABELS:
        errs = []
        for r in fc_by_key.get((model, 1), []):
            if not (d1 <= r["valid_at"] <= d2):
                continue
            o = obs.get(r["valid_at"])
            if not o or r["tmax_c"] is None:
                continue
            e = r["tmax_c"] - o["tmax"]
            errs.append(e)
            if biggest is None or abs(e) > biggest[0]:
                biggest = (abs(e), model, r["valid_at"], r["tmax_c"], o["tmax"])
        per_model[model] = err_stats(errs)
    return per_model, biggest


def build_article(y, m, per_model, biggest, site_data):
    mes = seo.MES_NOM[m]
    mes_loc = seo.MES_LOC[m]
    ranked = sorted(
        ((mdl, s) for mdl, s in per_model.items() if s.get("mae") is not None),
        key=lambda kv: kv[1]["mae"])

    if not ranked:
        lead = (f'V {mes_loc} {y} ni bilo dovolj razrešenih napovedi za primerjavo — '
                f'preveri stanje na <a href="{SITE}/test-napovedi/" style="color:var(--blue)">/test-napovedi/</a>.')
        sections = [{
            "label": "01 — status", "heading": "Ta mesec brez zadostnih podatkov", "id": "status",
            "paragraphs": [lead],
        }]
        title = f"Test napovedi: {mes} {y} brez zadostnih podatkov"
    else:
        winner_m, winner_s = ranked[0]
        winner_label = MODEL_LABELS[winner_m]
        lead = (f'V {mes_loc} {y} je pri napovedi najvišje temperature za jutri (D+1) najmanj zgrešil '
                f'{winner_label} — povprečna napaka ±{seo.num(winner_s["mae"])} °C '
                f'(bias {seo.num(winner_s["bias"])} °C, {winner_s["n"]} primerjanih dni).')

        rows_html = "<ul style='margin:.4rem 0 0;padding-left:1.2rem'>" + "".join(
            f'<li>{MODEL_LABELS[mdl]} — MAE ±{seo.num(s["mae"])} °C, bias {seo.num(s["bias"])} °C, '
            f'{seo.num(s.get("pct_gt3"), 0) if s.get("pct_gt3") is not None else "—"} % dni z napako &gt;3 °C</li>'
            for mdl, s in ranked
        ) + "</ul>"

        biggest_html = ""
        if biggest:
            abs_e, mdl, date, pred, actual = biggest
            diff_word = "precenil" if pred > actual else "podcenil"
            biggest_html = (f'<p>Največji posamični zgrešek meseca: <strong>{MODEL_LABELS[mdl]}</strong> je za '
                             f'{fmtdate(date)} napovedal {seo.num(pred)} °C, postaja je izmerila {seo.num(actual)} °C — '
                             f'{diff_word} je za {seo.num(abs_e)} °C.</p>')

        zero_crossing = (site_data or {}).get("zero_crossing_lead_days") or {}
        climo_mae = (((site_data or {}).get("climatology") or {}).get("tmax") or {}).get("mae")
        if zero_crossing:
            crossing_txt = ("; ".join(
                f'{MODEL_LABELS.get(mdl, mdl)} pri D+{ld}' for mdl, ld in zero_crossing.items()) +
                " napoved ni več boljša od klimatologije.")
        else:
            crossing_txt = ("noben od petih virov v celotnem vzorcu (D+1 do D+7) ne pade na raven klimatologije "
                             f'(±{seo.num(climo_mae) if climo_mae is not None else "—"} °C za Tmax) — razlika se z '
                             "vsakim dnem vnaprej manjša, a modeli ostanejo pred golim ugibanjem povprečja tudi teden vnaprej.")

        sections = [
            {"label": "01 — lestvica meseca", "heading": f"Lestvica za {mes} {y} (napoved za jutri)",
             "id": "lestvica", "paragraphs": [rows_html]},
            {"label": "02 — največji zgrešek", "heading": "Kje je šlo najbolj narobe", "id": "zgresek",
             "paragraphs": [biggest_html] if biggest_html else ["Ta mesec ni bilo izstopajočega posamičnega zgreška."]},
            {"label": "03 — do kje sega napoved", "heading": "Po katerem dnevu napoved odpove", "id": "prelom",
             "paragraphs": [f'Glede na celotno zgodovino primerjav (ne samo mesec {mes}): {crossing_txt}']},
            {"label": "04 — metodologija", "heading": "Kako merimo", "id": "metodologija",
             "paragraphs": [METHODOLOGY_NOTE]},
        ]
        title = f"Test napovedi: {mes} {y} — zmagal {winner_label}"

    return {
        "title": title,
        "meta_description": (f'Mesečni pregled natančnosti vremenske napovedi za Zgornjo Savinjsko dolino '
                              f'v {mes_loc} {y}: primerjava ECMWF, ICON, GFS, ARPEGE in best_match proti postaji IREICA1.'),
        "tags": ["test-napovedi", "mesecni-pregled", str(y)],
        "section_label": "Test napovedi",
        "og_photo": "weather-station",
        "og_accent_hex": "#38bdf8",
        "lead": lead,
        "sections": sections,
        "callout": None,
        "sources_note": ("Viri: Open-Meteo Previous Runs API (ECMWF IFS, ICON, GFS, ARPEGE, best_match), "
                          "meritve postaje IREICA1. Podatki in metodologija: /test-napovedi/."),
    }


def build_html(article, y, m, now_utc):
    slug = f"test-napovedi-{y}-{m:02d}"
    url = f"{SITE}/blog/{slug}.html"
    title = article["title"]
    desc = article["meta_description"]
    date_str = fmtdate(TODAY)

    sec_parts = []
    for s in article["sections"]:
        paras = "\n".join(
            p if p.lstrip().startswith(("<ul", "<ol", "<table", "<p")) else f"    <p>{p}</p>"
            for p in s["paragraphs"]
        )
        sec_parts.append(f'    <span class="section-label">{s["label"]}</span>\n'
                          f'    <h2 id="{s["id"]}">{s["heading"]}</h2>\n{paras}')
    sections_html = "\n\n".join(sec_parts)

    tags = article.get("tags", [])
    keywords = ", ".join(tags)
    section_label = article.get("section_label", "Test napovedi")

    html = f'''<!DOCTYPE html>
<html lang="sl">
<head>
<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','GTM-N2B38HHG');</script>
<!-- End Google Tag Manager -->
<meta charset="UTF-8">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-LE8PJ1HR8B"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-LE8PJ1HR8B');
</script>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{seo_title(title)}</title>
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
<link rel="alternate" type="application/rss+xml" title="Meteorec — blog" href="/blog/rss.xml">
{CSS_LINKS}
<style>.section-label{{font-family:'JetBrains Mono',monospace;font-size:.65rem;letter-spacing:.15em;text-transform:uppercase;color:var(--cyan);opacity:.75}}</style>
</head>
<body>
<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-N2B38HHG"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->
<div id="bg" aria-hidden="true"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="blob b4"></div><div class="blob b5"></div></div>
<div class="wrap">

  <header class="site-head">
    <a class="brand" href="/">
      <img class="brand-logo" src="/logo.svg" alt="" width="42" height="42">
      <span class="brand-name">Meteo<em>rec</em></span>
    </a>
    <nav class="site-nav"><a href="/">Vreme v živo</a><a href="/blog/">Blog</a><a href="/test-napovedi/">Test napovedi</a></nav>
  </header>

  <nav class="crumbs" aria-label="Drobtine">
    <a href="/">Meteorec</a> › <a href="/blog/">Blog</a> › {title}
  </nav>

  <article>
    <div class="stn-badge"><span></span> Test napovedi · {section_label}</div>
    <h1>{title}</h1>
    <p class="post-meta">{date_str} · Filip Eremita · samodejni mesečni pregled</p>

    <p class="lead">{article["lead"]}</p>
{sections_html}
    <p style="color:var(--muted);font-size:.9rem;margin-top:2rem">{article["sources_note"]}</p>

    <a class="back-link" href="/test-napovedi/">← Vsi podatki na /test-napovedi/</a>
  </article>

  <footer class="site-foot">
    <span>© {now_utc.year} Meteorec · Rečica ob Savinji</span>
    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a> · <a class="social-link" href="https://www.facebook.com/meteorec.si" target="_blank" rel="noopener" aria-label="Meteorec na Facebooku"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" width="14" height="14"><path d="M22 12a10 10 0 10-11.56 9.88v-6.99H7.9V12h2.54V9.8c0-2.5 1.49-3.89 3.78-3.89 1.09 0 2.24.2 2.24.2v2.46H15.2c-1.24 0-1.63.77-1.63 1.56V12h2.78l-.44 2.89h-2.34v6.99A10 10 0 0022 12z"/></svg></a> · <a class="social-link" href="https://www.instagram.com/meteorec.si" target="_blank" rel="noopener" aria-label="Meteorec na Instagramu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true" width="14" height="14"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg></a></span>
  </footer>

</div>
<script src="{asset_href('blog/likes.js')}" defer></script>
<script src="{asset_href('blog/views.js')}" defer></script>
<script src="{asset_href('blog/share-bar.js')}" defer></script>
<script src="{asset_href('blog/comments.js')}" defer></script>
<script src="{asset_href('blog/subscribe.js')}" defer></script>
{app_bottomnav()}
</body>
</html>
'''
    entry = {"title": title, "slug": slug, "url": f"/blog/{slug}.html", "date": TODAY,
              "summary": desc, "tags": tags}
    og_meta = {
        "title": f"Test napovedi\n{seo.MES_NOM[m].capitalize()} {y}",
        "subtitle": "Zgornja Savinjska dolina · IREICA1",
        "section": section_label,
        "accent": hexrgb(article["og_accent_hex"]),
        "photo": article["og_photo"],
    }
    return slug, html, entry, og_meta


def main():
    wire = "--wire" in sys.argv
    dry_run = "--dry-run" in sys.argv

    y, m, d1, d2 = prev_month_bounds(TODAY_DATE)
    print(f"Mesečni pregled test-napovedi: {seo.MES_NOM[m]} {y} ({d1}..{d2})")

    obs, _ = load_observations()
    fc_by_key = load_forecasts()
    per_model, biggest = month_stats(obs, fc_by_key, d1, d2)

    site_data = None
    if os.path.exists(DATA_PATH):
        site_data = json.load(open(DATA_PATH, encoding="utf-8"))

    if dry_run:
        print(json.dumps({"per_model": per_model, "biggest": biggest}, ensure_ascii=False, indent=2))
        return

    article = build_article(y, m, per_model, biggest, site_data)

    if os.environ.get("ANTHROPIC_API_KEY"):
        lektor_context = {"mesec": f"{seo.MES_NOM[m]} {y}", "lestvica": per_model,
                           "najvecji_zgresek": biggest}
        review = call_lektor(article, lektor_context)
        if review.get("issues"):
            print("  lektor:")
            for i in review["issues"]:
                print(f"  - {i}")
        final = review.get("corrected") or article
    else:
        print("  ⚠ ANTHROPIC_API_KEY ni nastavljen -- lektura preskočena.")
        final = article

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    slug, html, entry, og_meta = build_html(final, y, m, now_utc)
    out = os.path.join(ROOT, "blog", f"{slug}.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"✓ zapisano: blog/{slug}.html")

    if wire:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
            print(f"✓ OG slika: og/{slug}.jpg")
        except Exception as e:
            print(f"⚠ OG slika preskočena: {e}")
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml osveženi.")
    else:
        print("\n(poženi z --wire za samodejno vpisovanje in OG sliko)")


if __name__ == "__main__":
    main()
