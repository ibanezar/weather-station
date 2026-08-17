#!/usr/bin/env python3
"""
tools/asset_version.py — `?v=<hash8>` za skupne CSS datoteke.

Zakaj: strežnik postreže CSS z `cache-control: max-age=31536000` (eno leto).
Brez verzije v URL-ju obiskovalec, ki je stran že obiskal, po spremembi sloga
še dolgo vidi staro različico — `vreme/vreme.css` je bil tako po popravku tabel
in barve povezav pri vračajočih se obiskovalcih še vedno star.

`index.html` to že rešuje prek tools/minify_assets.mjs (`style.min.css?v=…`),
generirane strani pa ne. Ista rešitev, en sam zapis: ovoje strani so trije
(generate_seo_pages.page_shell, generate_monthly_post, seo_smart_routine) in
vsak si je doslej vrstice s CSS pisal sam — trije prepisi bi se razšli, kot
sta se seznama v sitemapu.

Hash je vsebinski, zato se spremeni natanko takrat, ko se spremeni datoteka.
Strani, ki te pomočnike uporabljajo, se redno pregenerirajo (SEO strani dnevno,
tema strani ob vsaki objavi), zato nova verzija pride v HTML sama.
"""
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE = {}


def asset_href(rel):
    """`/blog/blog.css` → `/blog/blog.css?v=1a2b3c4d`.

    Ob manjkajoči datoteki vrne pot brez verzije, da generiranje ne pade zaradi
    predpomnilniške podrobnosti.
    """
    rel = rel.lstrip("/")
    if rel not in _CACHE:
        path = os.path.join(ROOT, rel)
        try:
            with open(path, "rb") as f:
                _CACHE[rel] = hashlib.sha256(f.read()).hexdigest()[:8]
        except OSError:
            _CACHE[rel] = None
    h = _CACHE[rel]
    return f"/{rel}?v={h}" if h else f"/{rel}"


def css_links(*rels):
    """Zaporedje <link rel="stylesheet"> vrstic z verzijo, ena na vrstico."""
    return "\n".join(f'<link rel="stylesheet" href="{asset_href(r)}">' for r in rels)


if __name__ == "__main__":
    for r in ("fonts/fonts.css", "blog/blog.css", "vreme/vreme.css", "style.css"):
        print(asset_href(r))
