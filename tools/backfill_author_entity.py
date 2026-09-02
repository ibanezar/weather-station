#!/usr/bin/env python3
"""
Enkratni popravek: poveže avtorsko entiteto v JSON-LD obstoječih blog objav.

tools/geo_audit.py je 2.9.2026 odkril, da ima vseh že objavljenih ~102 blog
objav v BlogPosting shemi gol avtorski zapis:

    "author": { "@type": "Person", "name": "Filip Eremita" }

brez povezave nazaj na osebo, ki jo index.html že pozna kot entiteto
(`#person`, s `sameAs` na GitHub/Wunderground). Generatorji (generate_daily_post.py
idr.) so za NOVE objave popravljeni v isti seji; ta skript isti popravek
zapiše še v že objavljene, committane datoteke.

Zamenja natanko besedilo zgoraj z različico, ki vsebuje `url` in `sameAs` —
enako besedilo, kot ga zdaj pišejo generatorji. Nič drugega na strani se ne
spremeni (ne vidna vsebina, ne drugi JSON-LD bloki).

    python3 tools/backfill_author_entity.py            # zapiše spremembe
    python3 tools/backfill_author_entity.py --dry-run   # samo poročilo

Idempotenten: droga zagona ne najde več starega zapisa in ne spremeni nič.
"""
import glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry-run" in sys.argv

OLD = '"author": { "@type": "Person", "name": "Filip Eremita" }'
NEW = ('"author": { "@type": "Person", "name": "Filip Eremita", '
       '"url": "https://meteorec.si/o-postaji.html", '
       '"sameAs": ["https://ibanezar.github.io", '
       '"https://www.wunderground.com/dashboard/pws/IREICA1"] }')


def main():
    changed = []
    for path in sorted(glob.glob(os.path.join(ROOT, "blog", "*.html"))):
        if os.path.basename(path) == "index.html":
            continue  # ločen, ročno pisan blogPost seznam — glej opombo spodaj
        html = open(path, encoding="utf-8").read()
        n = html.count(OLD)
        if n == 0:
            continue
        changed.append((path, n))
        if not DRY:
            open(path, "w", encoding="utf-8").write(html.replace(OLD, NEW))

    total = sum(n for _, n in changed)
    print(f"{'[DRY-RUN] ' if DRY else ''}Popravljenih datotek: {len(changed)}, zamenjav: {total}")
    for path, n in changed:
        print(f"  {os.path.relpath(path, ROOT)} ({n}×)" if n > 1 else f"  {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
