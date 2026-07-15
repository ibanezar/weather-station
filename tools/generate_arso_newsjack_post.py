#!/usr/bin/env python3
"""
tools/generate_arso_newsjack_post.py — ARSO newsjacking protocol

Whenever ARSO issues a new orange/red warning, national media cover it in
general terms ("northeast Slovenia"). This script fills in a pre-built
template with the live alert + current station conditions and publishes a
hyperlocal blog post within one cron tick (15 min) — filling the gap for
"kaj to pomeni za Zgornjo Savinjsko dolino" before anyone else does.

Two phases, run together on every invocation:
  1. RESOLVE — for previously published newsjack posts whose alert window
     has ended and whose day is now finalized in history.json, inject an
     "Update: kaj se je dejansko zgodilo" section with real measurements
     (turns the fast, thin post into an evergreen one).
  2. DETECT  — for any currently active orange/red ARSO alert not yet
     posted about (tracked by signature in tools/.arso_newsjack_state.json),
     publish a new post immediately using the fixed template below.

Wired into: .github/workflows/arso-newsjack.yml (every 15 min).

Usage:
  python3 tools/generate_arso_newsjack_post.py [--wire] [--force]
"""
import datetime, hashlib, json, os, re, shutil, sys, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_monthly_post import ROOT, SITE, wire_all, fmtdate  # noqa: E402

WORKER = "https://weatherireica1.filip-eremita.workers.dev"
UA = {"User-Agent": "Mozilla/5.0 (compatible; Meteorec-ArsoNewsjack/1.0; +https://meteorec.si)"}
STATE_FILE = os.path.join(ROOT, "tools", ".arso_newsjack_state.json")
HIST_FILE = os.path.join(ROOT, "history.json")

# Fill-in-the-blank per ARSO warning parameter — written once, reused every
# time so a new post takes a cron tick, not editorial judgement.
CATEGORY = {
    "WarningTS": {
        "label": "nevihte", "icon": "⛈",
        "practical": ("Umakni avto izpod dreves, zapri okna in zavaruj predmete na prostem. "
                      "Če opaziš točo, jo fotografiraj in prijavi na "
                      f'<a href="/toca/">našem toča-trackerju</a> — to je edini kraj, kjer '
                      "nastaja skupen pregled po krajih doline."),
        "link_url": "/toca/", "link_label": "📷 Toča-tracker — arhiv in prijava toče v dolini",
        "photo": "storm-clouds", "accent": (139, 92, 246),
    },
    "WarningWind": {
        "label": "veter", "icon": "💨",
        "practical": ("Pospravi ali pritrdi vse, kar veter lahko odnese (mize, senčnike, tramponline). "
                      "Izogibaj se gozdu in vožnji skozi gozdnate odseke, dokler ne mine."),
        "link_url": "/#tab-storm", "link_label": "💨 Napoved sunkov vetra v živo",
        "photo": "storm-clouds", "accent": (96, 165, 250),
    },
    "WarningRA": {
        "label": "obilne padavine", "icon": "🌧",
        "practical": ("Spremljaj vodostaj Savinje in hudourniških pritokov (Lučnica, Ljubnica, "
                      "Mozirnica, Dreta) — na izsušenih ali že namočenih tleh lahko odtok naraste zelo hitro. "
                      "Izogibaj se nižinam ob vodotokih."),
        "link_url": "/vodostaj-savinje/", "link_label": "🌊 Vodostaj in napoved pretoka Savinje",
        "photo": "flood-river", "accent": (59, 130, 246),
    },
    "WarningSN": {
        "label": "sneženje", "icon": "🌨",
        "practical": "Prilagodi hitrost vožnje, uporabi zimsko opremo in računaj na daljši čas na cesti.",
        "link_url": "/", "link_label": "🌡 Trenutne razmere v živo",
        "photo": "night-fog-valley", "accent": (96, 165, 250),
    },
    "WarningFG": {
        "label": "megla", "icon": "🌫",
        "practical": "Prižgi meglenke, zmanjšaj hitrost in poveč varnostno razdaljo — v dolini se megla rada zadržuje dlje kot drugod.",
        "link_url": "/", "link_label": "🌡 Trenutne razmere v živo",
        "photo": "misty-valley", "accent": (148, 163, 184),
    },
    "WarningIC": {
        "label": "poledica/žled", "icon": "🧊",
        "practical": "Previdno na cestah, pločnikih in pod drevesi (nevarnost padajočih vej). Odloži nenujne poti.",
        "link_url": "/", "link_label": "🌡 Trenutne razmere v živo",
        "photo": "night-fog-valley", "accent": (56, 189, 248),
    },
    "WarningHT": {
        "label": "vročina", "icon": "🌡",
        "practical": "Pij dovolj tekočine, izogibaj se naporu med 12. in 17. uro in poskrbi za starejše in bolne v okolici.",
        "link_url": "/", "link_label": "🌡 Trenutne razmere v živo",
        "photo": "drought", "accent": (239, 68, 68),
    },
    "WarningLT": {
        "label": "mraz", "icon": "❄",
        "practical": "Zaščiti občutljive rastline in poskrbi, da imajo domače živali dostop do zavetja.",
        "link_url": "/", "link_label": "🌡 Trenutne razmere v živo",
        "photo": "night-fog-valley", "accent": (99, 102, 241),
    },
}
CATEGORY["WarningFire"] = {
    "label": "požarna ogroženost", "icon": "🔥",
    "practical": ("Ne kuri v naravi in ne odmetavaj cigaretnih ogorkov. Suha trava in gozdna tla ob "
                  "dolgotrajni vročini in brez padavin hitro postanejo vnetljivi — v Zgornji Savinjski "
                  "dolini je tveganje večje na osončenih, strmih pobočjih."),
    "link_url": "/", "link_label": "🌡 Trenutne razmere v živo",
    "photo": "drought", "accent": (249, 115, 22),
}
DEFAULT_CAT = {"label": "vreme", "icon": "⚠️", "practical": "Spremljaj uradna opozorila ARSO in razmere v živo.",
               "link_url": "/", "link_label": "🌡 Trenutne razmere v živo",
               "photo": "storm-clouds", "accent": (234, 179, 8)}

# Ključne besede kot rezerva, če ARSO-jeva koda parametra (node.parameter) ni
# med zgoraj poimenovanimi ali je prazna — klasifikacija po besedilu opozorila.
KEYWORD_CATEGORY = [
    ("toč", "WarningTS"), ("nevih", "WarningTS"),
    ("veter", "WarningWind"), ("sunk", "WarningWind"),
    ("padavin", "WarningRA"), ("poplav", "WarningRA"), ("naliv", "WarningRA"),
    ("sneg", "WarningSN"), ("sneženj", "WarningSN"),
    ("megla", "WarningFG"),
    ("poledic", "WarningIC"), ("žled", "WarningIC"),
    ("vročin", "WarningHT"), ("temperatura", "WarningHT"),
    ("mraz", "WarningLT"), ("mrzlo", "WarningLT"),
    ("požar", "WarningFire"),
]


def classify(alert):
    t = alert.get("type")
    if t and t in CATEGORY:
        return CATEGORY[t]
    blob = f'{alert.get("text","")} {alert.get("desc","")} {alert.get("more","")}'.lower()
    for kw, code in KEYWORD_CATEGORY:
        if kw in blob:
            return CATEGORY[code]
    return DEFAULT_CAT


MARK_START = "<!-- ARSO-UPDATE:START -->"
MARK_END = "<!-- ARSO-UPDATE:END -->"


def num(x, d=1):
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_alerts():
    req = urllib.request.Request(f"{WORKER}/arso-warning?region=SLOVENIA_NORTH-EAST", headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r).get("alerts", [])


def fetch_current():
    try:
        req = urllib.request.Request(f"{WORKER}/current", headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        obs = data.get("observations", [{}])[0]
        m = obs.get("metric", {})
        return {"temp": m.get("temp"), "wind": m.get("windSpeed"), "gust": m.get("windGust"),
                "precip": m.get("precipTotal"), "obsTimeLocal": obs.get("obsTimeLocal")}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, IndexError, KeyError):
        return {}


def alert_signature(a):
    key = f"{a.get('level')}|{a.get('type')}|{a.get('validStart')}|{a.get('validEnd')}|{a.get('text','')[:80]}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def parse_dt(iso):
    try:
        return datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def find_covering_post(alert, state):
    """Že objavljena, še neuveljena objava za isti tip opozorila (če obstaja).
    ARSO vsakih nekaj minut znova postreže "isto" tekoče opozorilo z rahlo
    zamaknjenim besedilom/validStart, zato dedup po natančnem hashu (stara
    alert_signature) skoraj vsak tek zazna "novo" opozorilo. Namesto tega
    preverimo, ali za ta tip opozorila že obstaja objava, katere veljavnost
    (validEnd) še ni potekla — če da, gre za isto tekoče opozorilo."""
    t = alert.get("type")
    for rec in state.get("posted", {}).values():
        if t not in (rec.get("types") or []):
            continue
        end_dt = parse_dt(rec.get("validEnd"))
        if end_dt is None or end_dt <= datetime.datetime.now(datetime.timezone.utc):
            continue  # ta objava je za preteklo/že končano opozorilo -- ne šteje kot pokritje
        return rec
    return None


def ensure_og_fallback(slug):
    """Rezerva, če generate_custom_og spodaj ne uspe (npr. Pillow ni na voljo):
    blog/index.html vedno prikaže sličico na /og/{slug}.jpg, zato brez tega
    sličica na seznamu objav manjka."""
    src = os.path.join(ROOT, "og-image.jpg")
    dst = os.path.join(ROOT, "og", f"{slug}.jpg")
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copyfile(src, dst)


def generate_custom_og(slug, og_meta):
    """Ustvari OG sliko z dejansko kategorijo opozorila (ne generično og-image.jpg),
    da ima deljena povezava takoj berljivo vsebino v predogledu. Enak Pillow-vzorec
    kot tools/generate_og_images.py in tools/generate_storm_watch_post.py."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from generate_og_images import make_og
        make_og({"slug": slug, **og_meta})
        print(f"✓ OG slika: og/{slug}.jpg")
    except Exception as e:
        print(f"⚠ OG slika (Pillow) preskočena, uporabljam splošno: {e}")
        ensure_og_fallback(slug)


def build_post(alerts, current, now_utc):
    """alerts: seznam 1+ hkrati aktivnih, še neobjavljenih opozoril. Če jih je
    več (npr. nevihte + požarna ogroženost izdani v istem teku), se združijo
    v en sam zapis namesto v skoraj identične ločene objave po eno na
    opozorilo."""
    cats = [classify(a) for a in alerts]
    level_rank = {"red": 2, "orange": 1}
    worst_level = max((a.get("level") for a in alerts), key=lambda l: level_rank.get(l, 0))
    level_sl = {"orange": "oranžno", "red": "rdeče"}.get(worst_level, worst_level or "oranžno")
    date_str = fmtdate(now_utc.date().isoformat())
    time_local = now_utc.strftime("%H:%M")
    labels = [c["label"] for c in cats]
    label_txt = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " in " + labels[-1]
    # primarna kategorija za OG sliko/naslovno ikono: tista z najhujšo stopnjo
    primary_idx = max(range(len(alerts)), key=lambda i: level_rank.get(alerts[i].get("level"), 0))
    primary_cat = cats[primary_idx]
    icons = "".join(dict.fromkeys(c["icon"] for c in cats))  # brez podvojenih, v izvirnem vrstnem redu

    # Sufiks iz kombinirane signature zagotovi unikaten slug tudi, če je
    # alert.get("type") prazen/None (npr. dokler worker.js s tem poljem še ni
    # deployan) — brez njega bi dve različni hkratni opozorili (npr. nevihte +
    # požarna ogroženost) v istem teku dobili enak slug in druga bi prepisala prvo.
    types_for_slug = sorted({(a.get("type") or "opozorilo").lower() for a in alerts})
    combo_sig = hashlib.sha1("|".join(sorted(alert_signature(a) for a in alerts)).encode()).hexdigest()[:6]
    slug = f"arso-opozorilo-{'-'.join(types_for_slug)}-{now_utc:%Y-%m-%d-%H%M}-{combo_sig}"
    url = f"{SITE}/blog/{slug}.html"

    title = f"ARSO {level_sl} opozorilo — {label_txt}: kaj to pomeni za Zgornjo Savinjsko dolino"

    lead_parts = []
    for a, cat in zip(alerts, cats):
        lvl = {"orange": "oranžno", "red": "rdeče"}.get(a.get("level"), a.get("level", "oranžno"))
        valid_txt = f' (veljavno {a.get("timeStr")})' if a.get("timeStr") else ""
        lead_parts.append(f'{lvl} opozorilo ({cat["label"]}){valid_txt}')
    lead_joined = lead_parts[0] if len(lead_parts) == 1 else "; ".join(lead_parts[:-1]) + " ter " + lead_parts[-1]
    descs = " ".join(a.get("desc", "").strip() for a in alerts if a.get("desc", "").strip())
    lead = f'Agencija RS za okolje (ARSO) je izdala <strong>{lead_joined}</strong>. {descs}'.strip()

    now_parts = []
    if current.get("temp") is not None:
        now_parts.append(f'temperatura {num(current["temp"])} °C')
    if current.get("wind") is not None:
        gust_txt = f' (sunki {num(current.get("gust"))} km/h)' if current.get("gust") is not None else ""
        now_parts.append(f'veter {num(current["wind"])} km/h{gust_txt}')
    if current.get("precip") is not None:
        now_parts.append(f'padavine danes {num(current["precip"])} mm')
    now_txt = (f'Trenutno stanje na postaji IREICA1 v Rečici ob Savinji: {", ".join(now_parts)}.'
               if now_parts else "Trenutne meritve postaje si oglej na naslovni strani.")

    desc = re.sub("<[^>]+>", "", lead)
    short = desc if len(desc) <= 200 else desc[:197] + "…"
    tags = ["ARSO opozorilo"] + labels + ["IREICA1", str(now_utc.year)]

    if len(alerts) == 1:
        sections = (f"<h2>Kaj to pomeni za Zgornjo Savinjsko dolino</h2>\n"
                    f'    <p>{cats[0]["practical"]}</p>\n'
                    f'    <p><a href="{cats[0]["link_url"]}" style="color:var(--blue)">{cats[0]["link_label"]} →</a></p>')
    else:
        blocks = []
        for a, cat in zip(alerts, cats):
            lvl = {"orange": "oranžno", "red": "rdeče"}.get(a.get("level"), a.get("level", "oranžno"))
            blocks.append(f'    <h3>{cat["icon"]} {cat["label"].capitalize()} — {lvl} opozorilo</h3>\n'
                          f'    <p>{cat["practical"]}</p>\n'
                          f'    <p><a href="{cat["link_url"]}" style="color:var(--blue)">{cat["link_label"]} →</a></p>')
        sections = "<h2>Kaj to pomeni za Zgornjo Savinjsko dolino</h2>\n" + "\n".join(blocks)

    body_html = f'''<!DOCTYPE html>
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
<meta name="keywords" content="ARSO opozorilo, {', '.join(labels)}, Zgornja Savinjska dolina, IREICA1">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="Filip Eremita">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="Meteorec">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{short}">
<meta property="og:image" content="{SITE}/og/{slug}.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="sl_SI">
<meta property="article:published_time" content="{now_utc.isoformat()}">
<meta property="article:author" content="Filip Eremita">
<meta property="article:section" content="ARSO opozorilo">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{short}">
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
    <h1>{icons} {title}</h1>
    <p class="post-meta">{date_str} ob {time_local} · Filip Eremita · postaja IREICA1 · samodejni zapis ob ARSO opozorilu</p>
    <p class="lead">{lead}</p>
    {MARK_START}{MARK_END}
    <p>{now_txt}</p>
    {sections}
    <p>Za Zgornjo Savinjsko dolino ločeno uradno opozorilo pogosto ni izdano — regijska opozorila ARSO
    (severovzhodna Slovenija) le okvirno zajemajo tudi naš del države. Dogajanje pri nas se lahko razlikuje
    po času in intenzivnosti od tega, kar je navedeno za širšo regijo.</p>
    <p style="color:var(--muted);font-size:.9rem">To je hiter, samodejno ustvarjen zapis ob izdaji ARSO opozorila.
    Ko opozorilo preteče, ta stran dobi posodobitev z dejanskimi meritvami postaje za to obdobje.</p>
    <p style="color:var(--muted);font-size:.9rem">Trenutne meritve v živo: <a href="/" style="color:var(--blue)">meteorec.si</a>.
    Uradna opozorila: <a href="https://meteo.arso.gov.si/met/sl/warning/" target="_blank" rel="noopener" style="color:var(--blue)">ARSO</a>.</p>
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
        "date": now_utc.date().isoformat(), "summary": short, "tags": tags,
    }
    og_meta = {
        "title": f"ARSO {level_sl} opozorilo\n{label_txt}",
        "subtitle": f"Zgornja Savinjska dolina · {date_str}",
        "section": "ARSO opozorilo",
        "accent": primary_cat["accent"],
        "photo": primary_cat["photo"],
    }
    return slug, url, body_html, entry, og_meta


def resolve_pending(state, hist):
    """Fill in the ARSO-UPDATE marker on already-published posts whose alert
    window has ended and whose day is now finalized in history.json."""
    resolved = 0
    for rec in state.get("posted", {}).values():
        if rec.get("resolved"):
            continue
        valid_end = rec.get("validEnd")
        if not valid_end:
            continue
        try:
            end_date = valid_end[:10]
        except (TypeError, IndexError):
            continue
        if end_date not in hist:
            continue  # dan še ni zaključen/na voljo v history.json

        v = hist[end_date]
        parts = []
        if v.get("tempHigh") is not None:
            parts.append(f'najvišja temperatura {num(v["tempHigh"])} °C')
        if v.get("windgustHigh") is not None:
            parts.append(f'najmočnejši sunek vetra {num(v["windgustHigh"])} km/h')
        if v.get("precipTotal") is not None:
            parts.append(f'{num(v["precipTotal"])} mm padavin')
        if not parts:
            continue
        # "types" je seznam (od PR-a z združenimi hkratnimi opozorili); starejši
        # zapisi v .arso_newsjack_state.json imajo še en sam niz "type".
        rec_types = rec.get("types") or ([rec["type"]] if rec.get("type") else [])
        update_html = (f'  <div class="partial-note">📊 <strong>Posodobljeno:</strong> na dan opozorila '
                        f'({fmtdate(end_date)}) je postaja IREICA1 izmerila {", ".join(parts)}. '
                        f'Poglej <a href="/vreme/{end_date[:4]}/{end_date[5:7]}/{end_date[8:10]}/" '
                        f'style="color:var(--blue)">poln dnevni podatek</a>'
                        + (f' ali <a href="/toca/" style="color:var(--blue)">prijave toče v dolini</a>'
                           if "WarningTS" in rec_types else "") + '.</div>')

        path = os.path.join(ROOT, "blog", f"{rec['slug']}.html")
        if not os.path.exists(path):
            continue
        html = open(path, encoding="utf-8").read()
        if MARK_START not in html or MARK_END not in html:
            continue
        new_html = re.sub(re.escape(MARK_START) + ".*?" + re.escape(MARK_END),
                           MARK_START + update_html + MARK_END, html, flags=re.S)
        if new_html != html:
            open(path, "w", encoding="utf-8").write(new_html)
            resolved += 1
        rec["resolved"] = True
    return resolved


def main():
    wire = "--wire" in sys.argv
    force = "--force" in sys.argv

    state = load_json(STATE_FILE, {"posted": {}})
    state.setdefault("posted", {})
    hist = load_json(HIST_FILE, {})

    resolved = resolve_pending(state, hist)
    if resolved:
        print(f"✓ Posodobljenih {resolved} preteklih objav z dejanskimi meritvami.")

    try:
        alerts = fetch_alerts()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"⚠ ARSO opozorila nedosegljiva: {e}", file=sys.stderr)
        alerts = []

    significant = [a for a in alerts if a.get("level") in ("orange", "red")]
    now = datetime.datetime.now(datetime.timezone.utc)
    published = 0

    # Vsa nova (še neobjavljena) opozorila iz tega teka gredo v EN zapis, ne
    # enega na opozorilo — če ARSO hkrati izda npr. nevihte + požarno
    # ogroženost, bi ločeni objavi delili skoraj ves predlog (isto stanje
    # postaje, isto uvod/zaključek) in bi bili na blogu skoraj identični.
    #
    # "Novo" pomeni: za ta tip opozorila še ni žive (nepotekle) objave. Če ena
    # obstaja, samo raztegnemo njen zabeleženi validEnd, če ga je ARSO medtem
    # podaljšal, namesto da bi objavili skoraj identičen nov zapis.
    new_alerts = []
    for a in significant:
        if force:
            new_alerts.append(a)
            continue
        covering = find_covering_post(a, state)
        if covering is None:
            new_alerts.append(a)
        elif a.get("validEnd", "") > covering.get("validEnd", ""):
            covering["validEnd"] = a["validEnd"]

    if new_alerts:
        types_txt = ", ".join(a.get("type") or "?" for a in new_alerts)
        current = fetch_current()
        slug, url, html, entry, og_meta = build_post(new_alerts, current, now)

        if not wire:
            print(f"[preview] {slug} — {len(new_alerts)} opozoril: {types_txt}")
        else:
            out = os.path.join(ROOT, "blog", f"{slug}.html")
            open(out, "w", encoding="utf-8").write(html)
            generate_custom_og(slug, og_meta)
            wire_all(entry, url)
            rec = {
                "slug": slug,
                "types": [a.get("type", "") for a in new_alerts],
                "validEnd": max((a.get("validEnd", "") for a in new_alerts), default=""),
                "resolved": False,
                "publishedAt": now.isoformat(),
            }
            state["posted"][slug] = rec
            published = len(new_alerts)
            print(f"✓ objavljeno: blog/{slug}.html ({len(new_alerts)} opozoril: {types_txt})")

    if not significant:
        print("Ni aktivnih oranžnih/rdečih opozoril.")
    elif published == 0 and not resolved:
        print("Aktivna opozorila že imajo objavo — nič novega.")

    if wire:
        save_json(STATE_FILE, state)


if __name__ == "__main__":
    main()
