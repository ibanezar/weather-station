#!/usr/bin/env python3
"""
tools/update_asset_versions.py — poravna `?v=<hash>` cache-busting parameter
za vse lokalne CSS/JS vire na VSEH .html straneh v repozitoriju z njihovo
trenutno vsebino.

Zakaj: GitHub Pages servira CSS/JS s `cache-control: max-age=31536000` (eno
leto) in ne podpira nastavljivih glav v repozitoriju -- edini način, da
sprememba blog.css/vreme.css/... doseže brskalnike vračajočih se
obiskovalcev, je sprememba URL-ja (?v=<hash>). tools/asset_version.py to reši
za strani, ki se redno pregenerirajo (SEO strani dnevno, tema strani ob
objavi) -- posamezni blog članki (dnevni/mesečni/nevihtni/ARSO/test-napovedi)
pa se po objavi praviloma nikoli več ne pregenerirajo, zato jim ?v= ostane
zamrznjen na dan objave. Ko se blog.css/vreme.css kasneje spremeni, imajo te
strani še vedno star hash -- 28. 8. 2026 je bilo tako 2539 od 2756 strani z
blog.css na starem hashu in 2709 od 2716 strani z vreme.css na starem hashu.

Ta skripta popravi obe stvari naenkrat: prehodi VSE .html datoteke v
repozitoriju in za vsak znan lokalni vir prepiše ?v= na trenutni hash --
ne glede na to, ali je bil prej pravilen, star ali ga sploh ni bilo.
Idempotentna je (varno jo je pognati kadarkoli); poganja jo tudi
.github/workflows/asset-versions.yml ob vsaki spremembi enega od virov, tako
da popravek doseže vse strani, ne le tiste, ki se pregenerirajo same.

Ujemanje je po IMENU datoteke (basename), ker strani vir referencirajo tako
z absolutno ("/blog/blog.css") kot relativno potjo ("blog.css", "likes.js") --
imena so v repozitoriju enolična, zato to ne potrebuje ločevanja po mapi.

Uporaba:
    python3 tools/update_asset_versions.py [--dry-run]
"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lokalni CSS/JS viri, ki jih strani po repozitoriju nalagajo prek <link>/<script>
# in ki NISO že pokriti prek tools/minify_assets.mjs (style.min.css/app.min.js,
# samo na index.html, s svojim ločenim mehanizmom).
ASSETS = [
    "fonts/fonts.css",
    "blog/blog.css",
    "vreme/vreme.css",
    "sola/sola.css",
    "igra/igra.css",
    "igra/igra.js",
    "meteogasilec/gasilec.js",
    "meteohmeljar/hmeljar.js",
    "blog/likes.js",
    "blog/views.js",
    "blog/comments.js",
    "blog/share-bar.js",
    "blog/article-enhance.js",
    "blog/subscribe.js",
    "blog/list-enhance.js",
]


def content_hash(rel):
    path = os.path.join(ROOT, rel)
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:8]


def build_patterns():
    patterns = []
    for rel in ASSETS:
        h = content_hash(rel)
        basename = os.path.basename(rel)
        # (href|src)="...ime.ext" ali "...ime.ext?v=star8hex" -> vedno "...ime.ext?v=trenuten"
        rx = re.compile(rf'((?:href|src)="[^"]*?{re.escape(basename)})(?:\?v=[0-9a-f]+)?(")')
        patterns.append((rx, h))
    return patterns


def main():
    dry_run = "--dry-run" in sys.argv
    patterns = build_patterns()

    changed_files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fname in filenames:
            if not fname.endswith(".html"):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath, encoding="utf-8") as f:
                html = f.read()
            orig = html
            for rx, h in patterns:
                html = rx.sub(rf'\g<1>?v={h}\g<2>', html)
            if html != orig:
                changed_files.append(os.path.relpath(fpath, ROOT))
                if not dry_run:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(html)

    verb = "bi popravil" if dry_run else "popravljenih"
    print(f"✓ {len(changed_files)} HTML datotek {verb} (?v= usklajen s trenutno vsebino vira).")
    if dry_run and changed_files:
        for f in changed_files[:20]:
            print(f"  {f}")
        if len(changed_files) > 20:
            print(f"  … in še {len(changed_files) - 20}")


if __name__ == "__main__":
    main()
