#!/usr/bin/env python3
"""
tools/inject_storm_map.py — vgradi dnevno nevihtno karto Slovenije na
/nevihte/.

Bere og/storm-map/latest.json (piše ga tools/generate_storm_map.py) in
zapiše blok med markerja WX-STORMMAP. Isti vzorec kot
tools/inject_arso_warnings.py: markerja mora na stran zapisati generator
(generate_nevihte_page.py) vnaprej, sicer skript javi napako in konča z 1.

Wired into: .github/workflows/storm-map.yml

Usage:
  python3 tools/inject_storm_map.py [--dry-run]
"""
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "nevihte", "index.html")
LATEST = os.path.join(ROOT, "og", "storm-map", "latest.json")
START = "<!-- WX-STORMMAP:START (auto: tools/inject_storm_map.py) -->"
END = "<!-- WX-STORMMAP:END -->"


def esc(s):
    return html.escape(str(s or ""), quote=True)


def build_block(meta):
    date = esc(meta.get("date", ""))
    level = esc(meta.get("national_level", "—"))
    place = esc(meta.get("national_place", "—"))
    image = esc(meta.get("image", ""))
    return (
        f'{START}\n'
        f'  <h2 id="karta">Nevihtna karta Slovenije — danes</h2>\n'
        f'  <p class="archive-intro">Najvišji nevihtni potencial danes je <strong>{level}</strong>, '
        f'pričakovan bliže {place}. Karta prikazuje oceno po vsej Sloveniji iz iste formule kot zgornji '
        f'indeksi (Open-Meteo) — ni uradno opozorilo ARSO, izdana je vsak dan ob 10:00.</p>\n'
        f'  <img src="{image}" alt="Nevihtna karta Slovenije, {date}" loading="lazy" '
        f'style="width:100%;max-width:720px;border-radius:16px;display:block;margin:0 auto">\n'
        f'  {END}'
    )


def main():
    dry = "--dry-run" in sys.argv[1:]
    if not os.path.exists(PAGE):
        print(f"ERROR: {PAGE} ne obstaja.", file=sys.stderr)
        return 1
    page = open(PAGE, encoding="utf-8").read()
    if START not in page or END not in page:
        print("ERROR: markerjev WX-STORMMAP ni v /nevihte/ — poženi najprej "
              "tools/generate_nevihte_page.py.", file=sys.stderr)
        return 1

    try:
        meta = json.load(open(LATEST, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Karta ni na voljo ({e}) — blok ostane nespremenjen.", file=sys.stderr)
        return 0

    block = build_block(meta)
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, page, flags=re.S)

    if dry:
        print(f"--dry-run: {meta.get('national_level')}; "
              f"{'sprememba' if new != page else 'brez sprememb'}")
        return 0
    if new != page:
        open(PAGE, "w", encoding="utf-8").write(new)
        print(f"nevihte/index.html: karta posodobljena ({meta.get('national_level')}).")
    else:
        print("nevihte/index.html: karta brez sprememb.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
