#!/usr/bin/env python3
"""
Generator "nevihtnega opazovalca" -- kratek samodejni mikro-zapis na blogu,
ki se objavi, ko trenutne meritve postaje IREICA1 pokažejo:
  - hiter padec zračnega tlaka (>=3 hPa v zadnjih 3 urah, isto okno kot
    prikazuje živi nadzorni pult v app.js:applyPressureTrend), ali
  - močan sunek vetra (>=40 km/h, isti prag kot push-obvestila v worker.js).

Med sprožitvama velja hlajenje (privzeto 6 ur), da isti dogodek ne
objavlja večih zapisov zapored. Stanje zadnje objave je v
tools/.storm_watch_state.json (v repozitoriju, da se ohrani med zagoni).

Uporaba:
    python3 tools/generate_storm_watch_post.py [--wire] [--force]

--force preskoči preverjanje hlajenja (za ročno testiranje).
"""
import json, os, shutil, sys, datetime, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_monthly_post import ROOT, SITE, wire_all, fmtdate

PROXY = "https://weatherireica1.filip-eremita.workers.dev"
STATE_FILE = os.path.join(ROOT, "tools", ".storm_watch_state.json")
COOLDOWN_HOURS = 6
GUST_THRESHOLD_KMH = 40
PRESSURE_DROP_HPA = 3  # v zadnjih 3 urah -- isto okno kot na app.js (applyPressureTrend)


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def fetch_hourly():
    req = urllib.request.Request(
        PROXY + "/hourly",
        headers={"User-Agent": "Mozilla/5.0 (compatible; Meteorec-StormWatch/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    return data.get("observations", [])


def load_state():
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=2)
    open(STATE_FILE, "a", encoding="utf-8").write("\n")


def ensure_og_fallback(slug):
    """blog/index.html vedno prikaže sličico na /og/{slug}.jpg — mikro-zapisi
    nimajo posebej oblikovane OG slike, zato uporabimo splošno og-image.jpg,
    da sličica na seznamu objav ne manjka."""
    src = os.path.join(ROOT, "og-image.jpg")
    dst = os.path.join(ROOT, "og", f"{slug}.jpg")
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copyfile(src, dst)


def detect_trigger(observations):
    """Isti izračun kot app.js:applyPressureTrend (3-urno okno, primerjava
    zadnjega branja s tistim 3 mesta nazaj v urni seriji)."""
    if len(observations) < 4:
        return None
    last, prev = observations[-1], observations[-4]
    m = last.get("metric", {})
    p_now = m.get("pressureMax") or m.get("pressure")
    p_old = (prev.get("metric", {}) or {}).get("pressureMax") or (prev.get("metric", {}) or {}).get("pressure")
    # Hourly opazovanja uporabljajo *High/*Low/*Avg polja (ne windGust/windSpeed kot /current) --
    # windspeedHigh je enaka konvencija kot jo app.js uporablja za sunek iz urne serije.
    gust = m.get("windspeedHigh") or m.get("windSpeed") or 0

    if p_now and p_old:
        drop = p_old - p_now
        if drop >= PRESSURE_DROP_HPA:
            return {"type": "pressure", "obs": last, "delta": drop, "pressure": p_now}
    if gust >= GUST_THRESHOLD_KMH:
        return {"type": "wind", "obs": last, "gust": gust}
    return None


def build_html(trigger, now_utc):
    obs = trigger["obs"]
    m = obs.get("metric", {})
    time_local = (obs.get("obsTimeLocal") or "")[11:16] or "—"
    date_str = fmtdate(now_utc.date().isoformat())
    slug = f"nevihtni-opazovalec-{now_utc:%Y-%m-%d-%H%M}"
    url = f"{SITE}/blog/{slug}.html"
    temp = m.get("tempAvg") or m.get("tempHigh")  # urna serija nima navadnega polja "temp"

    if trigger["type"] == "pressure":
        title = f"Nevihtni opazovalec, {date_str} ob {time_local}: hiter padec zračnega tlaka"
        lead = (
            f'Zračni tlak na postaji <strong>IREICA1</strong> je v zadnjih treh urah padel za '
            f'<strong>{num(trigger["delta"])} hPa</strong> (zdaj <strong>{num(trigger["pressure"],0)} hPa</strong>) — '
            f'znak hitre spremembe vremena, pogosto pred frontalnim prehodom ali nevihto.'
        )
        rows = [
            ("Padec tlaka (3 h)", f"{num(trigger['delta'])} hPa"),
            ("Trenutni tlak", f"{num(trigger['pressure'],0)} hPa"),
        ]
        related_url, related_title = "/blog/kako-brati-nevihtno-napoved-cape-striz-vetra.html", "Kako brati nevihtno napoved: CAPE, indeks dviga in striženje vetra"
        tags = ["nevihtni-opazovalec", "samodejno", "pritisk", str(now_utc.year)]
    else:
        title = f"Nevihtni opazovalec, {date_str} ob {time_local}: močan sunek vetra"
        lead = (
            f'Na postaji <strong>IREICA1</strong> je bil ob {time_local} izmerjen sunek vetra '
            f'<strong>{num(trigger["gust"],0)} km/h</strong> — nad pragom za opozorilo.'
        )
        rows = [("Sunek vetra", f"{num(trigger['gust'],0)} km/h")]
        related_url, related_title = "/blog/ekoloska-tveganja-pozarna-ogrozenost-vetrolomi.html", "Ekološka in okoljska tveganja: požarna ogroženost in vetrolomi"
        tags = ["nevihtni-opazovalec", "samodejno", "veter", str(now_utc.year)]

    if temp is not None:
        rows.append(("Temperatura ob meritvi", f"{num(temp)} °C"))

    desc = lead.replace("<strong>", "").replace("</strong>", "")
    short = desc if len(desc) <= 200 else desc[:197] + "…"
    rows_html = "\n".join(f"      <tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
    today_iso = now_utc.date().isoformat()

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
<title>{title} | Meteorec, Rečica ob Savinji</title>
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="sl" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<meta name="description" content="{desc}">
<meta name="keywords" content="nevihtni opazovalec, Rečica ob Savinji, IREICA1, Savinjska dolina, vreme v živo">
<meta name="robots" content="index, follow">
<meta name="author" content="Filip Eremita">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="Meteorec">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{short}">
<meta property="og:image" content="{SITE}/og-image.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="sl_SI">
<meta property="article:published_time" content="{now_utc.isoformat()}">
<meta property="article:author" content="Filip Eremita">
<meta property="article:section" content="Nevihtni opazovalec">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{short}">
<meta name="twitter:image" content="{SITE}/og-image.jpg">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "{title}",
  "description": "{desc}",
  "image": {{ "@type": "ImageObject", "url": "{SITE}/og-image.jpg", "width": 1200, "height": 630 }},
  "datePublished": "{now_utc.isoformat()}",
  "dateModified": "{now_utc.isoformat()}",
  "inLanguage": "sl",
  "author": {{ "@type": "Person", "name": "Filip Eremita" }},
  "publisher": {{ "@type": "Organization", "name": "Meteorec", "logo": {{ "@type": "ImageObject", "url": "{SITE}/icon-512.png" }} }},
  "mainEntityOfPage": {{ "@type": "WebPage", "@id": "{url}" }},
  "about": {{ "@type": "Place", "name": "Rečica ob Savinji", "sameAs": ["https://www.wikidata.org/wiki/Q969326", "https://en.wikipedia.org/wiki/Re%C4%8Dica_ob_Savinji"], "geo": {{ "@type": "GeoCoordinates", "latitude": 46.325779, "longitude": 14.921137, "elevation": 366 }} }}
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
    <h1>{title}</h1>
    <p class="post-meta">{date_str} · Filip Eremita · postaja IREICA1 · samodejni zapis · ~1 min branja</p>
    <p class="lead">{lead}</p>
    <table class="stats">
{rows_html}
    </table>
    <p style="color:var(--muted);font-size:.9rem">To je kratek, samodejno ustvarjen zapis ob preseženem pragu na živi postaji. Za ozadje in razlago si preberi: <a href="{related_url}" style="color:var(--blue)">{related_title}</a>.</p>
    <p style="color:var(--muted);font-size:.9rem">Trenutne meritve v živo: <a href="/" style="color:var(--blue)">meteorec.si</a>.</p>
    <a class="back-link" href="/blog/">← Nazaj na blog</a>
  </article>
  <footer class="site-foot">
    <span>© {now_utc.year} Meteorec · Rečica ob Savinji</span>
    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a></span>
  </footer>
</div>
<script src="likes.js" defer></script>
</body>
</html>
'''
    entry = {
        "title": title, "slug": slug, "url": f"/blog/{slug}.html",
        "date": today_iso, "summary": short, "tags": tags,
    }
    return slug, url, html, entry


def main():
    wire = "--wire" in sys.argv
    force = "--force" in sys.argv

    state = load_state()
    now = datetime.datetime.now(datetime.timezone.utc)
    last_published = state.get("lastPublished")
    if last_published and not force:
        last_dt = datetime.datetime.fromisoformat(last_published)
        hours_since = (now - last_dt).total_seconds() / 3600
        if hours_since < COOLDOWN_HOURS:
            print(f"Hlajenje aktivno — zadnja objava pred {hours_since:.1f} h (< {COOLDOWN_HOURS} h). Preskočeno.")
            return

    observations = fetch_hourly()
    trigger = detect_trigger(observations)
    if not trigger:
        print("Ni preseženega praga (tlak/veter). Nič za objaviti.")
        return

    slug, url, html, entry = build_html(trigger, now)
    out = os.path.join(ROOT, "blog", f"{slug}.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"✓ zapisano: blog/{slug}.html ({trigger['type']})")

    if wire:
        ensure_og_fallback(slug)
        wire_all(entry, url)
        print("✓ posodobljeno: blog.json, blog/index.html, sitemap.xml")
        state["lastPublished"] = now.isoformat()
        state["lastTrigger"] = trigger["type"]
        save_state(state)
    else:
        print("\n— Za blog.json dodaj:\n" + json.dumps(entry, ensure_ascii=False, indent=2))
        print("\n(ali poženi z --wire za samodejno vpisovanje in posodobitev hlajenja)")


if __name__ == "__main__":
    main()
