#!/usr/bin/env python3
"""
tools/content_health_audit.py — Izboljšaj / Konsolidiraj / Osveži / Pobriši
pregled blog arhiva

Search Console/GA4 podatkov ta skript nima (Claude oz. ta okolje nima
dostopa do njiju — glej "Pred začetkom" v vodiču za SEO) in jih ne poskuša
uganiti. Namesto tega uporabi signale, ki so na voljo v repozitoriju in na
javnem Workerju:

  - starost objave (datum / dateModified iz JSON-LD),
  - dolžina besedila (kazalnik "tanke" vsebine),
  - siroti članki — brez nobene vhodne povezave, statične ali prek
    blog/related.json (glej Section 05/08 kontrolni seznam v CLAUDE.md:
    "Nobene strani brez vsaj ene vhodne notranje povezave"),
  - kanibalizacija — TF-IDF kosinusna podobnost med objavami, ista logika
    kot `compute_related_posts.py` (uvožena, ne podvojena), samo z višjim
    pragom, namenjenim za "to sta skoraj ista članka",
  - ogledi (best-effort, živ klic na Worker /views — glej seed_view_counts.py
    za isti vzorec; če Worker ni dosegljiv, se ta signal tiho izpusti).

Arhivski tipi objav (dnevni podatkovni zapisi, mesečni povzetki) so
izločeni iz Izboljšaj/Konsolidiraj/Osveži/Pobriši priporočil — to je
merjena zgodovina postaje, ne generična vsebina, ki bi "zastarela". Zanje
se preverja samo, ali so siroti (to je tehnična napaka ne glede na tip).

To je samo pregled, ki nikoli ne popravlja ničesar in nikoli ne vrne
ne-nič izhoda — priporočila so vhodni podatek za človeško presojo, ne
ukaz. Preden kateri koli članek dejansko pobrišeš ali združiš, preveri
vezane povratne povezave in netipične poizvedbe, na katere morda še
vedno kaže (glej opozorilo v poglavju 11 vodiča) — enako kot velja za
12 ARSO objav, ki so bile pretvorjene v preusmeritve, ne izbrisane
(glej razdelek "Opozorila ARSO gredo na /nevihte/" v CLAUDE.md).

Zaženi:
  python3 tools/content_health_audit.py             # brez ogledov iz Workerja
  python3 tools/content_health_audit.py --views      # + živ klic na /views
"""
import datetime
import glob
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute_related_posts import cosine, extract_text, tfidf_vectors, tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
TODAY = datetime.date.today()
WORKER = os.environ.get("WORKER_BASE") or "https://weatherireica1.filip-eremita.workers.dev"

THIN_WORDS = 500          # samo za tip "evergreen" — arhivski tipi so kratki po zasnovi
STALE_DAYS = 240          # samo za tip "evergreen"
SIM_HIGH = 0.45           # nad tem pragom gre za verjetno kanibalizacijo, ne le "sorodno"

# Datumsko obarvan dnevni zapis: slug se konča na -MMDD z veljavnim mesecem/dnem
# (npr. "...-0814"). Preveri veljavnost, da se npr. "-2026" (leto) ne ujame pomotoma.
DAILY_SUFFIX_RE = re.compile(r"-(\d{2})(\d{2})$")
MONTHLY_PREFIXES = ("vremenski-povzetek-", "test-napovedi-", "makro-mesecni-")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def classify_type(post):
    slug = post["slug"]
    tags = set(post.get("tags", []))
    if tags & {"mesecni-pregled", "tedenski-pregled"} or slug.startswith(MONTHLY_PREFIXES):
        return "periodičen"
    m = DAILY_SUFFIX_RE.search(slug)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            return "dnevni"
    return "evergreen"


def load_post_html(slug):
    path = os.path.join(ROOT, "blog", f"{slug}.html")
    try:
        return read(path)
    except FileNotFoundError:
        return None


def date_modified(html, fallback_date):
    m = re.search(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})"', html or "")
    if m:
        return m.group(1)
    return fallback_date


def word_count(html):
    text = extract_text(html)
    return len(re.findall(r"[a-zA-ZščžćđŠČŽĆĐ]+", text))


def all_site_html_files():
    """Vse HTML datoteke na strani razen blog/*.html (te preverimo posebej,
    ker gredo tudi medsebojne povezave znotraj korpusa v obzir)."""
    files = []
    for path in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True):
        rel = os.path.relpath(path, ROOT)
        if rel.startswith((".git" + os.sep, "node_modules" + os.sep)):
            continue
        if rel.startswith("blog" + os.sep):
            continue
        files.append(path)
    return files


def fetch_views(slugs):
    """Best-effort živ klic na Worker /views?slugs=... — glej seed_view_counts.py.
    Ob kakršni koli napaki (ni omrežja, worker ne odgovori) tiho vrne None,
    signal se v poročilu preprosto izpusti."""
    out = {}
    try:
        for i in range(0, len(slugs), 80):
            chunk = slugs[i:i + 80]
            url = f"{WORKER}/views?slugs=" + urllib.parse.quote(",".join(chunk))
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = json.load(resp)
            out.update(data.get("views", {}))
        return out
    except Exception as e:
        print(f"⚠️  ogledi niso na voljo, worker ni dosegljiv ({e})", file=sys.stderr)
        return None


def audit(use_views=False):
    posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
    slugs = [p["slug"] for p in posts]

    html_by_slug = {s: load_post_html(s) for s in slugs}
    types = {p["slug"]: classify_type(p) for p in posts}
    modified = {
        p["slug"]: date_modified(html_by_slug[p["slug"]], p.get("date", TODAY.isoformat()))
        for p in posts
    }
    words = {s: (word_count(html_by_slug[s]) if html_by_slug[s] else 0) for s in slugs}

    # ── Siroti — statične povezave na drugih straneh + blog/related.json -----
    other_html = "\n".join(read(p) for p in all_site_html_files())
    related_path = os.path.join(ROOT, "blog", "related.json")
    related = json.load(open(related_path, encoding="utf-8")) if os.path.exists(related_path) else {}
    referenced_by_related = set()
    for src, targets in related.items():
        referenced_by_related.update(targets)

    blog_link_counts = {s: 0 for s in slugs}
    for s in slugs:
        html = html_by_slug[s]
        if not html:
            continue
        needle = f"/blog/{s}.html"
        for other_slug in slugs:
            if other_slug == s:
                continue
            other_html = html_by_slug[other_slug]
            if other_html and needle in other_html:
                blog_link_counts[s] += 1

    orphans = set()
    for s in slugs:
        inbound_static = other_html.count(f"/blog/{s}.html") + blog_link_counts[s]
        inbound_related = s in referenced_by_related
        if inbound_static == 0 and not inbound_related:
            orphans.add(s)

    # ── Kanibalizacija — TF-IDF kosinusna podobnost, visok prag -------------
    docs_tokens = [tokenize(extract_text(html_by_slug[s])) if html_by_slug[s] else [] for s in slugs]
    vectors = tfidf_vectors(docs_tokens)
    pairs = []
    for i in range(len(slugs)):
        for j in range(i + 1, len(slugs)):
            score = cosine(vectors[i], vectors[j])
            if score > SIM_HIGH:
                pairs.append((score, slugs[i], slugs[j]))
    pairs.sort(key=lambda x: -x[0])
    cannibal_slugs = {s for _, a, b in pairs for s in (a, b)}

    # ── Ogledi (neobvezno) ----------------------------------------------------
    views = fetch_views(slugs) if use_views else None

    # ── Klasifikacija ----------------------------------------------------------
    buckets = {"KONSOLIDIRAJ": [], "POBRIŠI/PRESMERI": [], "POVEŽI": [], "OSVEŽI": [], "IZBOLJŠAJ": [], "V REDU": []}
    orphan_archive = []  # arhivski tipi, ki so kljub temu siroti — vedno vredno popraviti

    for p in posts:
        s = p["slug"]
        t = types[s]
        age = (TODAY - datetime.date.fromisoformat(modified[s])).days
        is_orphan = s in orphans
        is_stale = age > STALE_DAYS
        is_thin = words[s] > 0 and words[s] < THIN_WORDS
        v = views.get(s) if views else None

        if t != "evergreen":
            if is_orphan:
                orphan_archive.append(s)
            continue

        if s in cannibal_slugs:
            buckets["KONSOLIDIRAJ"].append(s)
        elif is_orphan and is_stale and (v == 0 if v is not None else True):
            buckets["POBRIŠI/PRESMERI"].append(s)
        elif is_orphan:
            buckets["POVEŽI"].append(s)
        elif is_stale:
            buckets["OSVEŽI"].append(s)
        elif is_thin:
            buckets["IZBOLJŠAJ"].append(s)
        else:
            buckets["V REDU"].append(s)

    # ── Poročilo -----------------------------------------------------------
    lines = [f"# Pregled zdravja blog arhiva — {TODAY.isoformat()}", ""]
    lines.append(f"- Objav skupaj: **{len(posts)}** "
                 f"({sum(1 for t in types.values() if t == 'evergreen')} evergreen, "
                 f"{sum(1 for t in types.values() if t == 'periodičen')} periodičnih (tedenski/mesečni), "
                 f"{sum(1 for t in types.values() if t == 'dnevni')} dnevnih)")
    if views is None and use_views:
        lines.append("- Ogledi: **niso na voljo** (worker ni odgovoril)")
    elif views is not None:
        lines.append(f"- Ogledi: pridobljeni za {len(views)} objav")
    else:
        lines.append("- Ogledi: preskočeno (poženi z `--views` za živ klic na Worker)")
    lines.append("")
    lines.append("> Brez dostopa do Search Console/GA4 — signali spodaj so posredni "
                 "(starost, dolžina, notranje povezave, TF-IDF podobnost, ogledi). "
                 "**Preden kateri koli evergreen članek dejansko pobrišeš ali združiš, "
                 "ročno preveri povratne povezave in netipične poizvedbe** (Search Console), "
                 "na katere morda še vedno kaže — glej opozorilo v poglavju o meritvi in "
                 "prioritizaciji. Nič spodaj se ne zgodi samodejno.")

    for name in ("KONSOLIDIRAJ", "POBRIŠI/PRESMERI", "POVEŽI", "OSVEŽI", "IZBOLJŠAJ"):
        items = buckets[name]
        if not items:
            continue
        lines.append("")
        lines.append(f"## {name} ({len(items)})")
        for s in items:
            age = (TODAY - datetime.date.fromisoformat(modified[s])).days
            extra = f"{words[s]} besed, {age} dni od zadnje spremembe"
            if name == "KONSOLIDIRAJ":
                partner = next((b if a == s else a) for score, a, b in pairs if s in (a, b))
                score = next(score for score, a, b in pairs if s in (a, b))
                extra += f", podobnost {score:.2f} z `{partner}`"
            lines.append(f"- `{s}` — {extra}")

    if orphan_archive:
        lines.append("")
        lines.append(f"## Siroti arhivski zapisi ({len(orphan_archive)})")
        lines.append("Dnevni/mesečni zapisi brez nobene vhodne povezave — ni razlog za "
                     "brisanje (to je merjena zgodovina), a vredno dodati vsaj eno vhodno "
                     "povezavo (npr. iz sorodnega mesečnega povzetka).")
        for s in orphan_archive:
            lines.append(f"- `{s}`")

    ok_count = len(buckets["V REDU"])
    lines.append("")
    lines.append(f"✅ Brez opozorila: **{ok_count}** evergreen objav.")

    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(audit(use_views="--views" in sys.argv))
