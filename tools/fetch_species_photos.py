#!/usr/bin/env python3
"""
tools/fetch_species_photos.py — najdi in prenesi fotografije vrst z Wikimedia Commons

Za vsako vrsto iz species_rules.yaml, ki še nima slike, poišče prosto
licencirano fotografijo na Commons, jo shrani kot
gobarska-napoved/img/vrste/<id>.jpg in vpiše avtorja, licenco in vir v
CREDITS.json poleg nje (tabela virov na strani se izriše iz te datoteke).

Sprejme samo licence, ki dovoljujejo objavo z navedbo vira (CC0, javna domena,
CC BY, CC BY-SA, GFDL). Vse z NC ali ND zavrne — stran je javna in bi jih
kršila. Kjer primerne slike ni, datoteke ne naredi in kartica ostane pri
rezervnem prikazu; to ni napaka.

Uporaba:
  python3 tools/fetch_species_photos.py --dry-run      # samo izpiši, kaj bi vzel
  python3 tools/fetch_species_photos.py --limit 20     # prenesi prvih 20 manjkajočih
  python3 tools/fetch_species_photos.py --only boletus_edulis
  python3 tools/fetch_species_photos.py --recheck      # poskusi tudi tam, kjer slika že je
"""
import argparse
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import yaml
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "species_rules.yaml")
IMG_DIR = os.path.join(ROOT, "gobarska-napoved", "img", "vrste")
CREDITS_PATH = os.path.join(IMG_DIR, "CREDITS.json")

API = "https://commons.wikimedia.org/w/api.php"
UA = "MeteorecGobarskaNapoved/1.0 (https://meteorec.si; filip.eremita@gmail.com)"

TARGET_WIDTH = 640      # enako kot obstoječe slike
JPEG_QUALITY = 82
CANDIDATES_PER_SPECIES = 12

# Licence, ki dovoljujejo objavo z navedbo vira. Ključ je iskan v nizu licence
# iz extmetadata (velike črke), vrednost je zapis za tabelo virov.
LICENSE_OK = [
    ("CC0", "CC0"),
    ("PUBLIC DOMAIN", "javna domena"),
    ("PD-", "javna domena"),
    ("CC BY-SA 4.0", "CC BY-SA 4.0"), ("CC BY-SA 3.0", "CC BY-SA 3.0"),
    ("CC BY-SA 2.5", "CC BY-SA 2.5"), ("CC BY-SA 2.0", "CC BY-SA 2.0"),
    ("CC BY-SA 1.0", "CC BY-SA 1.0"),
    ("CC BY 4.0", "CC BY 4.0"), ("CC BY 3.0", "CC BY 3.0"),
    ("CC BY 2.5", "CC BY 2.5"), ("CC BY 2.0", "CC BY 2.0"),
    ("GFDL", "GFDL"),
]
LICENSE_BAD = ("-NC", "NONCOMMERCIAL", "-ND", "NODERIV", "FAIR USE")


# ── Commons API ──────────────────────────────────────────────────────────────

def api(params, tries=4):
    params = {**params, "format": "json", "formatversion": 2}
    url = f"{API}?{urllib.parse.urlencode(params)}"
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == tries - 1:
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def strip_html(s):
    """extmetadata polja so HTML ('<a href=…>Ime</a>') — tabela virov hoče besedilo."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


# Commons pri prenesenih slikah pogosto namesto imena vrne cel stavek
# ("This image was created by user X at Mushroom Observer …"); v tabeli virov
# hočemo ime avtorja, ne odstavka.
ARTIST_PREFIXES = re.compile(
    r"^(this (image|photo(graph)?) (was )?(created|taken|uploaded) by( user)?|"
    r"photo(graph)? by|image by|foto:|photo:|©)\s*", re.I)
ARTIST_TAIL = re.compile(r"\s*(,|\bat\b|\bfrom\b|\(|–|—|\|).*$", re.S)


def clean_artist(s):
    s = ARTIST_PREFIXES.sub("", strip_html(s)).strip()
    if len(s) > 40:                     # še vedno stavek — vzemi prvi del
        s = ARTIST_TAIL.sub("", s).strip()
    s = s.strip(" .,;:-")
    return s[:60] or "neznan avtor"


def license_of(meta):
    """(zapis licence, ali je uporabna) iz extmetadata."""
    raw = " ".join(strip_html((meta.get(k) or {}).get("value", "")).upper()
                   for k in ("LicenseShortName", "License", "UsageTerms"))
    if any(bad in raw for bad in LICENSE_BAD):
        return None
    for key, label in LICENSE_OK:
        if key in raw:
            return label
    return None


def search_images(name_lat):
    """Kandidatne slike za vrsto: najprej kategorija vrste (tam so slike
    določene do vrste), nato splošno iskanje po imenu."""
    out = []
    for params in (
        {"action": "query", "generator": "categorymembers",
         "gcmtitle": f"Category:{name_lat}", "gcmtype": "file",
         "gcmlimit": CANDIDATES_PER_SPECIES},
        {"action": "query", "generator": "search",
         "gsrsearch": f'filetype:bitmap "{name_lat}"', "gsrnamespace": 6,
         "gsrlimit": CANDIDATES_PER_SPECIES},
    ):
        d = api({**params, "prop": "imageinfo",
                 "iiprop": "url|extmetadata|size|mime",
                 "iiurlwidth": TARGET_WIDTH})
        for page in ((d or {}).get("query", {}) or {}).get("pages", []) or []:
            info = (page.get("imageinfo") or [{}])[0]
            if not info or not info.get("thumburl"):
                continue
            if info.get("mime") not in ("image/jpeg", "image/png"):
                continue
            if info.get("width", 0) < 320 or info.get("height", 0) < 240:
                continue
            out.append({"title": page.get("title", ""), "info": info})
    return out


def pick(name_lat, candidates):
    """Prva slika s sprejemljivo licenco, katere ime datoteke omenja vrsto —
    tako se izognemo slikam habitata ali druge vrste iz iste kategorije."""
    genus, _, epithet = name_lat.partition(" ")
    wanted = (epithet or genus).lower()
    scored = []
    for c in candidates:
        lic = license_of((c["info"].get("extmetadata") or {}))
        if not lic:
            continue
        title = c["title"].lower()
        score = 0
        if wanted and wanted in title:
            score += 2
        if genus.lower() in title:
            score += 1
        # Kvadratnejše slike se v okroglem izrezu na kartici obnesejo bolje.
        w, h = c["info"].get("width", 1), c["info"].get("height", 1)
        if 0.6 <= w / max(h, 1) <= 1.8:
            score += 1
        scored.append((score, c, lic))
    if not scored:
        return None
    scored.sort(key=lambda t: -t[0])
    best_score, best, lic = scored[0]
    if best_score < 1:      # nič ne kaže, da je slika res te vrste
        return None
    meta = best["info"].get("extmetadata") or {}
    return {
        "thumburl": best["info"]["thumburl"],
        "license": lic,
        "artist": clean_artist((meta.get("Artist") or {}).get("value")),
        "source_url": best["info"].get("descriptionurl") or "",
        "title": best["title"],
    }


def download_jpeg(url, dest):
    """Prenesi in shrani kot JPEG, širina TARGET_WIDTH (kot obstoječe slike)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    im = Image.open(io.BytesIO(data))
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    if im.width > TARGET_WIDTH:
        im = im.resize((TARGET_WIDTH, round(im.height * TARGET_WIDTH / im.width)), Image.LANCZOS)
    im.convert("RGB").save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return os.path.getsize(dest)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Prenesi fotografije vrst z Wikimedia Commons")
    ap.add_argument("--limit", type=int, default=0, help="največ toliko vrst (0 = brez omejitve)")
    ap.add_argument("--only", help="samo ta id vrste")
    ap.add_argument("--recheck", action="store_true", help="poskusi tudi tam, kjer slika že obstaja")
    ap.add_argument("--dry-run", action="store_true", help="samo izpiši, ne prenašaj")
    args = ap.parse_args()

    with open(RULES_PATH, encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    try:
        with open(CREDITS_PATH, encoding="utf-8") as f:
            credits = json.load(f)
    except (OSError, ValueError):
        credits = {}

    todo = []
    for sp in rules["species"]:
        if args.only and sp["id"] != args.only:
            continue
        dest = os.path.join(IMG_DIR, f"{sp['id']}.jpg")
        if os.path.exists(dest) and not args.recheck:
            continue
        todo.append(sp)
    if args.limit:
        todo = todo[:args.limit]

    print(f"Vrst brez fotografije: {len(todo)}")
    got = missed = 0
    for i, sp in enumerate(todo, 1):
        name_lat = sp["name_lat"]
        hit = pick(name_lat, search_images(name_lat))
        if not hit:
            missed += 1
            print(f"  [{i}/{len(todo)}] ✗ {name_lat} — ni proste slike")
            continue
        fn = f"{sp['id']}.jpg"
        if args.dry_run:
            got += 1
            print(f"  [{i}/{len(todo)}] → {name_lat}: {hit['license']}, {hit['artist'][:40]}")
            continue
        try:
            kb = download_jpeg(hit["thumburl"], os.path.join(IMG_DIR, fn)) / 1024
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            missed += 1
            print(f"  [{i}/{len(todo)}] ✗ {name_lat} — prenos ni uspel: {e}")
            continue
        credits[fn] = {"artist": hit["artist"], "latin": name_lat, "license": hit["license"],
                       "sl": sp["name_sl"], "source_url": hit["source_url"]}
        got += 1
        print(f"  [{i}/{len(todo)}] ✓ {sp['name_sl']} ({name_lat}) — {hit['license']}, {kb:.0f} kB")

    if not args.dry_run and got:
        with open(CREDITS_PATH, "w", encoding="utf-8") as f:
            json.dump(credits, f, ensure_ascii=False, indent=1, sort_keys=True)
        print(f"→ {CREDITS_PATH} ({len(credits)} vnosov)")
    print(f"\nPrevzetih: {got} · brez slike: {missed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
