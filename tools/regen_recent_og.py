#!/usr/bin/env python3
"""
tools/regen_recent_og.py — ročno, enkratno orodje: regenerira OG naslovne
kartice zadnjih N člankov iz blog.json s pravo fotografijo (Google Drive
rotacija) namesto obstoječega generičnega ozadja.

Metapodatke (naslov, datum, sekcijo) prebere iz že zapisanega blog/<slug>.html
(meta og:title, article:section, article:published_time).

Usage:
  GDRIVE_FOLDER_ID=... GDRIVE_API_KEY=... GDRIVE_FOLDER_RESOURCE_KEY=... \
    python3 tools/regen_recent_og.py [--count N]
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_og_images import make_og
from fetch_drive_photo import fetch_random_photo

MES_GEN = {1: "januarja", 2: "februarja", 3: "marca", 4: "aprila", 5: "maja",
           6: "junija", 7: "julija", 8: "avgusta", 9: "septembra", 10: "oktobra",
           11: "novembra", 12: "decembra"}


def meta(html, prop):
    m = re.search(rf'<meta property="{re.escape(prop)}" content="([^"]*)"', html)
    return m.group(1) if m else None


def fmtdate(iso):
    y, m, d = iso.split("-")
    return f"{int(d)}. {MES_GEN[int(m)]} {y}"


def main():
    count = 10
    if "--count" in sys.argv:
        count = int(sys.argv[sys.argv.index("--count") + 1])

    posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
    for post in posts[:count]:
        slug = post["slug"]
        path = os.path.join(ROOT, "blog", f"{slug}.html")
        if not os.path.isfile(path):
            print(f"⚠ preskočeno (ni HTML datoteke): {slug}")
            continue
        html = open(path, encoding="utf-8").read()
        title = meta(html, "og:title") or post["title"]
        section = meta(html, "article:section") or "Analiza"
        pub = meta(html, "article:published_time") or post["date"]

        photo = fetch_random_photo()
        if not photo:
            print(f"⚠ ni fotke z Drive-a, preskakujem preostale.")
            break
        os.environ["DRIVE_PHOTO_PATH"] = photo

        make_og({
            "slug": slug,
            "title": title.split(":")[0][:40],
            "subtitle": f"Rečica ob Savinji · {fmtdate(pub)}",
            "section": section,
            "accent": (56, 189, 248),
            "photo": "weather-station",
        })
        print(f"✓ {slug}")


if __name__ == "__main__":
    main()
